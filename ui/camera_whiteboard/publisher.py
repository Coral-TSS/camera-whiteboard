"""把画布内容发布到共享帧文件，供媒体源读取。

协议见 specs/windows11/frame-protocol.md：64 字节头 + 序号锁 + Windows FILETIME 时间戳。
发布器按固定帧率重复写同一画面（内容没变也写），否则媒体源会因"帧太旧"回落到诊断图案。
"""

from __future__ import annotations

import math
import mmap
import os
import ctypes
import struct
import time
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

from . import paths
from .canvas import Canvas
from .render import render

MAGIC = 0x31425743  # 'CWB1'
HEADER_BYTES = 64
STATE_OK = 1
FORMAT_BGRA = 0

def default_frame_path() -> Path:
    """共享帧文件路径（与媒体源 DLL 的搜索顺序一致）。"""
    return paths.frames_path()


DEFAULT_PATH = default_frame_path()


def _filetime() -> int:
    return int((time.time() + 11644473600) * 10_000_000)


class FramePublisher:
    def __init__(
        self,
        canvas: Canvas,
        path: str | os.PathLike[str] | None = None,
        width: int = 1280,
        height: int = 960,
        background: tuple[int, int, int, int] | None = None,
    ) -> None:
        self.canvas = canvas
        self.path = Path(path) if path else DEFAULT_PATH
        self.width = width
        self.height = height
        self.background = background
        self.compositor = None      # 设了就用它合成（摄像头 + 笔迹）
        self.camera = None          # 需提供 latest() -> QImage | None
        self.stride = width * 4
        self._file = None
        self._map: mmap.mmap | None = None
        self._seq = 0
        self._frame_id = 0
        self._rendered_revision = -1
        self._cached_image: QImage | None = None
        self._blank_image: QImage | None = None
        self._payload_addr: int = 0
        self._bg_dirty = False
        self.active = True  # 视口关闭时置 False，输出空白帧（不送白板内容）
        self.last_error: str | None = None

    # ---- 生命周期 ----

    @property
    def total_bytes(self) -> int:
        return HEADER_BYTES + self.stride * self.height

    def open(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            need = self.total_bytes
            if not self.path.exists() or self.path.stat().st_size != need:
                with open(self.path, "wb") as f:
                    f.truncate(need)
            self._file = open(self.path, "r+b")
            self._map = mmap.mmap(self._file.fileno(), need)
        except OSError as exc:
            self.last_error = f"Could not open shared frame file: {exc}"
            return False

        self._payload_addr = ctypes.addressof(ctypes.c_char.from_buffer(self._map)) + HEADER_BYTES
        self._map[0:HEADER_BYTES] = struct.pack(
            "<IIIIIIIIQQQII",
            MAGIC, 1, HEADER_BYTES, self.width, self.height, self.stride, FORMAT_BGRA, 0,
            0, 0, 0, 0, 0,
        )
        self.last_error = None
        return True

    def close(self) -> None:
        if self._map is not None:
            self._map.close()
            self._map = None
        if self._file is not None:
            self._file.close()
            self._file = None

    @property
    def is_open(self) -> bool:
        return self._map is not None

    # ---- 发布 ----

    def set_compositor(self, compositor, camera=None) -> None:
        """接入合成器与摄像头；之后每帧都重新合成（摄像头画面每帧都在变）。"""
        self.compositor = compositor
        if camera is not None:
            self.camera = camera
        self._bg_dirty = True

    def _render_image(self) -> QImage:
        """返回这一帧的 QImage。写共享帧时直接从它的 buffer 拷，不做二次拷贝。"""
        if not self.active:
            if self._blank_image is None or self._bg_dirty:
                image = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(QColor(*self.background) if self.background else Qt.GlobalColor.transparent)
                self._blank_image = image
                self._bg_dirty = False
            return self._blank_image

        if self.compositor is not None:
            base = None
            if self.camera is not None:
                getter = getattr(self.camera, "latest_usable", None) or self.camera.latest
                base = getter()
            image = self.compositor.frame(base)
            self._rendered_revision = self.canvas.revision
            self._bg_dirty = False
            return image

        if (self._cached_image is None or self.canvas.revision != self._rendered_revision
                or self._bg_dirty):
            self._cached_image = render(self.canvas, self.width, self.height, self.background)
            self._rendered_revision = self.canvas.revision
            self._bg_dirty = False
        return self._cached_image

    def set_active(self, active: bool) -> None:
        """视口关闭后不再送白板内容，但仍持续发布空白帧（保持流新鲜）。"""
        self.active = active
        if active:
            self._rendered_revision = -1  # 重新渲染一次

    def set_background(self, background: tuple[int, int, int, int] | None) -> None:
        """切换输出底色（None = 透明）。接入合成器后由合成器决定底色。"""
        self.background = background
        if self.compositor is not None:
            self.compositor.set_background(background)
        self._bg_dirty = True

    def publish(self) -> bool:
        """写一帧。内容没变也会写入，用于维持"帧还新鲜"。"""
        if self._map is None and not self.open():
            return False

        try:
            image = self._render_image()
        except Exception as exc:  # noqa: BLE001 - 渲染失败不应拖垮界面
            self.last_error = f"Frame rendering failed: {exc}"
            return False

        assert self._map is not None
        self._seq += 1
        struct.pack_into("<Q", self._map, 32, self._seq)      # 奇数：写入中
        # 直接 memmove 一次，省掉 tobytes() 的整帧拷贝：
        # 写入期间消费方读到奇数序号会回落诊断图案，窗口越短闪得越少
        size = self.width * 4 * self.height
        try:
            src = ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))
            ctypes.memmove(self._payload_addr, src, size)
        except (TypeError, ValueError):
            # 拿不到缓冲区地址时退回普通赋值，慢一点但不会出错
            self._map[HEADER_BYTES:HEADER_BYTES + size] = image.constBits().tobytes()
        self._frame_id += 1
        struct.pack_into("<Q", self._map, 40, self._frame_id)
        struct.pack_into("<Q", self._map, 48, _filetime())
        struct.pack_into("<I", self._map, 56, STATE_OK)
        self._seq += 1
        struct.pack_into("<Q", self._map, 32, self._seq)      # 偶数：稳定
        return True

    # ---- 诊断 ----

    @property
    def frames_published(self) -> int:
        return self._frame_id

    def expected_fps(self, tick_ms: int) -> float:
        return 1000.0 / tick_ms if tick_ms > 0 else math.inf

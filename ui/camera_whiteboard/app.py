"""应用入口：透明悬浮层 + 工具栏 + 托盘 + 全局快捷键。

运行：.venv\\Scripts\\python.exe scripts\\run_ui.py
"""

from __future__ import annotations

import sys
import threading
import time

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .canvas import Canvas
from .geometry import union_rect
from .hotkeys import MOD_ALT, MOD_CONTROL, VK_F8, VK_F9, GlobalHotkeys
from .overlay import BrushSettings
from .camera import NullCamera, create_camera
from .config import load_config
from .log import log, set_log_path
from .virtualcam import VirtualCamera
from .compositor import Compositor
from .layout import ANCHORS, DEFAULT_ANCHOR, DEFAULT_RATIO, DEFAULT_SIZE, SIZES, clamp_ratio
from .publisher import DEFAULT_PATH as FRAMES_PATH
from . import i18n
from .palette import PALETTE, TOOLS, WIDTHS
from .publisher import FramePublisher
from .viewport import ViewportWindow

# 与媒体源协商的尺寸保持一致（VCamSampleSource/MediaStream.cpp 的 NUM_IMAGE_COLS/ROWS）
OUT_W, OUT_H = 1280, 720
TICK_MS = 33
WHITE = (255, 255, 255, 255)


def virtual_desktop_rect() -> tuple[int, int, int, int]:
    screens = QGuiApplication.screens()
    return union_rect([(s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height())
                       for s in screens])


def _tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.GlobalColor.red)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


class WhiteboardApp:
    def __init__(self, app: QApplication, vcam: VirtualCamera | None = None) -> None:
        self.app = app
        rect = virtual_desktop_rect()
        self.canvas = Canvas(viewport=(float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])))
        self.brush = BrushSettings()
        self._last_publish_error: str | None = None

        # 画布相关的所有设置都放进白板窗口标题栏的「菜单」，不再用悬浮工具栏
        # 白板窗口：白底画布，可拖动/缩放/关闭；关闭 = 停止送白板内容
        self.viewport = ViewportWindow(self.canvas, self.brush,
                                       QRect(rect[0] + 120, rect[1] + 110, 960, 720))
        self.viewport.closed.connect(self._on_viewport_closed)
        self.viewport.menu_requested.connect(self._on_menu_requested)
        self.viewport.geometry_changed.connect(self._on_viewport_moved)
        self.viewport.show()
        self.viewport.raise_()

        self.hotkeys = GlobalHotkeys()
        self.hotkeys.bridge.triggered.connect(self._on_hotkey)
        self.hotkey_status = {
            "passthrough": self.hotkeys.register("passthrough", MOD_CONTROL | MOD_ALT, VK_F8),
            "undo": self.hotkeys.register("undo", MOD_CONTROL | MOD_ALT, VK_F9),
        }
        failed = [name for name, ok in self.hotkey_status.items() if not ok]
        if failed:
            log(f"[hotkey] Registration failed: {', '.join(failed)} (possibly in use by another app)")

        t_start = time.perf_counter()
        self.config = load_config()
        i18n.set_language(self.config.language)
        set_log_path(FRAMES_PATH.parent / "app.log")
        log(f"Starting camera {self.config.device_name}; config: {self.config.source}")

        # 输出先跑起来：哪怕摄像头还没就绪，也先喂空白帧，
        # 否则会议软件那边会因为"帧停了 2 秒"回落成诊断图案（彩色闪屏）
        self.publisher = FramePublisher(self.canvas, width=OUT_W, height=OUT_H, background=WHITE)
        self.compositor = Compositor(self.canvas, OUT_W, OUT_H, background=WHITE,
                                     anchor=DEFAULT_ANCHOR, ratio=DEFAULT_RATIO)
        # 发送方向以远端画面为准，不补偿会议客户端的自拍镜像。
        self.compositor.set_mirror(False)
        self.publisher.set_compositor(self.compositor, None)
        self.output_ok = self.publisher.open()
        self.output_error = self.publisher.last_error
        self._timer = QTimer()
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)  # 默认 CoarseTimer 会被推迟，输出帧率不稳
        self._timer.timeout.connect(self._publish)  # type: ignore[arg-type]
        if self.output_ok:
            self._timer.start(TICK_MS)
        else:
            log(f"[publisher] {self.output_error}")
        self.app.aboutToQuit.connect(self.publisher.close)

        # 虚拟摄像头：优先用启动阶段已经建好的那个（exe 会提前创建，让设备更快出现在会议里）
        if vcam is not None:
            self.vcam = vcam
            self.vcam_ok = vcam.is_running
        else:
            self.vcam = VirtualCamera(self.config.device_name, self.config.media_source_clsid)
            self.vcam_ok = self.vcam.start_with_fallback()
            if self.vcam_ok:
                log(f"[vcam] Started {self.config.device_name} ({time.perf_counter() - t_start:.2f}s)"
                    f" (CLSID {self.vcam.clsid})"
                    + (f"; {self.vcam.last_error}" if self.vcam.last_error else ""))
            else:
                log(f"[vcam] Startup failed: {self.vcam.last_error}")
        self.app.aboutToQuit.connect(self.vcam.stop)

        # 摄像头按需占用：只在"画布打开且要叠加"时才抢，不用时让出去，
        # 免得别的程序（会议软件/相机应用）打不开物理摄像头
        self.camera = NullCamera()
        self.camera_overlay = True
        self._camera_owned = False
        self._camera_error: str | None = None
        self._cam_thread: threading.Thread | None = None
        self._cam_result = None
        self._camera_yielded = False
        self.background_white = True
        self._sync_camera()
        self.app.aboutToQuit.connect(self._release_camera)

        self._sync_panel_ratio()

        self._setup_tray()

    def _publish(self) -> None:
        if not self.publisher.publish() and self.publisher.last_error != self._last_publish_error:
            self._last_publish_error = self.publisher.last_error
            if self.publisher.last_error:
                log(f"[publisher] {self.publisher.last_error}")
            self._timer.stop()
            self.output_ok = False

    # ---- 动作 ----

    def toggle_passthrough(self) -> None:
        target = not self.viewport.passthrough
        self.viewport.set_passthrough(target)
        if hasattr(self, "_act_pass"):
            self._act_pass.setChecked(target)

    def undo(self) -> None:
        if self.canvas.undo():
            self.viewport.update()

    def clear(self) -> None:
        if self.canvas.clear():
            self.viewport.update()

    def _on_hotkey(self, name: str) -> None:
        if name == "passthrough":
            self.toggle_passthrough()
        elif name == "undo":
            self.undo()

    def set_anchor(self, anchor: str) -> None:
        self.compositor.set_layout(anchor=anchor)
        self.publisher._bg_dirty = True

    def set_panel_size(self, size: str) -> None:
        """预设改的是白板窗口大小，输出面板随之等比变化。"""
        self._size_key = size
        ratio = SIZES.get(size, SIZES[DEFAULT_SIZE])[1]
        self.viewport.resize_to_ratio(ratio)
        self._sync_panel_ratio()

    def _sync_panel_ratio(self) -> None:
        """输出面板的大小 = 白板窗口宽度 / 屏幕宽度，所见即所得。"""
        screen = QGuiApplication.primaryScreen()
        screen_w = screen.geometry().width() if screen else 1920
        ratio = clamp_ratio(self.viewport.width() / max(1, screen_w))
        self.compositor.set_layout(ratio=ratio)
        self.publisher._bg_dirty = True

    def _toggle_background(self, enabled: bool) -> None:
        self.background_white = enabled
        self.publisher.set_background(WHITE if enabled else None)

    def set_camera_yielded(self, yielded: bool) -> None:
        """显式让出/收回物理摄像头（给需要同时用真实摄像头的场景）。"""
        self._camera_yielded = yielded
        self._sync_camera()

    def toggle_camera(self, enabled: bool) -> None:
        """叠加摄像头画面 / 只看白板。关掉会立刻把物理摄像头让出去。"""
        self.camera_overlay = enabled
        self._sync_camera()

    # ---- 摄像头的占用与让出 ----

    @property
    def _need_camera(self) -> bool:
        # 关画布也要继续送摄像头画面（否则会议里就得换视频源，绝对不行），
        # 只有用户显式"让出摄像头"或关掉叠加才释放
        return self.camera_overlay and not self._camera_yielded

    def _sync_camera(self) -> None:
        if self._need_camera:
            self._acquire_camera()
        else:
            self._release_camera()
        self.viewport.update()

    def _acquire_camera(self) -> None:
        """在后台线程打开摄像头：ffmpeg 枚举+启动要好几秒，不能卡住界面。"""
        if self._camera_owned or self._cam_thread is not None:
            return
        self._cam_result = None
        self._cam_thread = threading.Thread(target=self._open_camera_bg, name="cam-open", daemon=True)
        self._cam_thread.start()
        if not hasattr(self, "_cam_poll"):
            self._cam_poll = QTimer(self.app)
            self._cam_poll.timeout.connect(self._check_camera)  # type: ignore[arg-type]
        self._cam_poll.start(150)

    def _open_camera_bg(self) -> None:
        self._cam_result = create_camera()

    def _check_camera(self) -> None:
        cam = self._cam_result
        if cam is None:
            return
        self._cam_result = None
        self._cam_poll.stop()
        self._cam_thread = None
        self._camera_error = cam.last_error
        if not cam.is_open:
            log(f"[camera] Cannot open camera: {cam.last_error}")
            self.camera = cam
            return
        if not self._need_camera:
            cam.close()  # 打开期间用户已经把画布关了
            return
        self.camera = cam
        self._camera_owned = True
        self.publisher.set_compositor(self.compositor, cam)
        log(f"[camera] Acquired {cam.width}x{cam.height}（{type(cam).__name__}）")
        if hasattr(self, "tray"):
            self.tray.setToolTip(i18n.t("tray.camera_on", w=cam.width, h=cam.height))

    def _release_camera(self) -> None:
        if self._cam_thread is not None:
            self._cam_result = None  # 后台还在开，等它自己检查 _need_camera 后关掉
        if not self._camera_owned:
            return
        self.camera.close()
        self.camera = NullCamera()
        self._camera_owned = False
        self.publisher.set_compositor(self.compositor, None)
        self.publisher._bg_dirty = True
        log("[camera] Released; available to other apps.")
        if hasattr(self, "tray"):
            self.tray.setToolTip(i18n.t("tray.camera_off"))

    # ---- 画布开关（程序常驻，画布随时开关） ----

    @property
    def board_visible(self) -> bool:
        return self.viewport.isVisible()

    def toggle_board(self, show: bool | None = None) -> None:
        """打开/关闭画布。

        打开 = 合成白板面板；关闭 = 只送摄像头画面（对面看到的普通摄像头），
        摄像头继续持有，会议软件不需要换视频源。
        """
        show = (not self.viewport.isVisible()) if show is None else show
        if show:
            self.viewport.show()
            self.viewport.raise_()
            self._sync_panel_ratio()
        else:
            self.viewport.hide()
        self.compositor.set_panel_visible(show)
        self.publisher._bg_dirty = True
        if hasattr(self, "_act_board"):
            self._act_board.setChecked(show)

    def show_viewport(self) -> None:
        self.toggle_board(True)

    def _on_viewport_moved(self) -> None:
        self.viewport.raise_()
        self._sync_panel_ratio()

    def _on_viewport_closed(self) -> None:
        # ✕ 只是关画布：程序继续跑、摄像头继续送，托盘再点一次就回来
        self.toggle_board(False)

    # ---- 画笔 ----

    def set_tool(self, tool: str) -> None:
        self.brush.tool = tool
        self.viewport.update()

    def set_color(self, color: tuple[int, int, int, int]) -> None:
        self.brush.color = color
        self.brush.tool = "pen"      # 选颜色通常是想画
        self.viewport.update()

    def set_width(self, width: float) -> None:
        self.brush.width = width
        self.viewport.update()

    def set_show_safe_area(self, enabled: bool) -> None:
        self.compositor.set_show_safe_area(enabled)
        self.publisher._bg_dirty = True

    def set_mirror(self, enabled: bool) -> None:
        """仅翻转发送的笔迹内容，不改变面板位置。"""
        self.compositor.set_mirror(enabled)
        self.publisher._bg_dirty = True
        log(f"[canvas] Mirror strokes: {'on' if enabled else 'off'}")

    def set_board_mirror(self, enabled: bool) -> None:
        """Reflect the board's placement and content; keep the camera unchanged."""
        self.compositor.set_board_mirror(enabled)
        self.publisher._bg_dirty = True
        if hasattr(self, '_act_board_mirror'):
            self._act_board_mirror.setChecked(enabled)
        log(f"[canvas] Mirror board position + strokes: {'on' if enabled else 'off'}")

    def _board_menu(self) -> QMenu:
        """白板窗口标题栏的「菜单」：画布相关设置都在这里，不再用悬浮工具栏。"""
        menu = QMenu(self.viewport)

        tool = menu.addMenu(i18n.t("menu.tool"))
        for key, _tool in TOOLS:
            act = tool.addAction(i18n.tool(key))
            act.setCheckable(True)
            act.setChecked(self.brush.tool == key)
            act.triggered.connect(lambda _=False, k=key: self.set_tool(k))
        color = tool.addMenu(i18n.t("menu.color"))
        for key, rgba in PALETTE:
            act = color.addAction(i18n.color(key))
            act.setCheckable(True)
            act.setChecked(tuple(self.brush.color) == rgba)
            act.triggered.connect(lambda _=False, c=rgba: self.set_color(c))
        width = tool.addMenu(i18n.t("menu.width"))
        for key, value in WIDTHS:
            act = width.addAction(i18n.width(key))
            act.setCheckable(True)
            act.setChecked(abs(self.brush.width - value) < 0.01)
            act.triggered.connect(lambda _=False, v=value: self.set_width(v))

        menu.addAction(i18n.t("menu.undo")).triggered.connect(self.undo)
        menu.addAction(i18n.t("menu.clear")).triggered.connect(self.clear)
        menu.addSeparator()

        pos = menu.addMenu(i18n.t("menu.position"))
        for key in ANCHORS:
            act = pos.addAction(i18n.anchor(key))
            act.setCheckable(True)
            act.setChecked(key == self.compositor.anchor)
            act.triggered.connect(lambda _=False, k=key: self.set_anchor(k))

        size = menu.addMenu(i18n.t("menu.size"))
        for key in SIZES:
            act = size.addAction(i18n.size(key))
            act.setCheckable(True)
            act.setChecked(key == self._size_key)
            act.triggered.connect(lambda _=False, k=key: self.set_panel_size(k))

        mirror = menu.addAction(i18n.t("menu.mirror"))
        mirror.setCheckable(True)
        mirror.setChecked(self.compositor.mirror)
        mirror.toggled.connect(self.set_mirror)

        board_mirror = menu.addAction(i18n.t("menu.board_mirror"))
        board_mirror.setCheckable(True)
        board_mirror.setChecked(self.compositor.board_mirror)
        board_mirror.toggled.connect(self.set_board_mirror)

        menu.addSeparator()
        cam = menu.addAction(i18n.t("menu.overlay"))
        cam.setCheckable(True)
        cam.setChecked(self.camera_overlay)
        cam.toggled.connect(self.toggle_camera)

        yield_cam = menu.addAction(i18n.t("menu.yield"))
        yield_cam.setCheckable(True)
        yield_cam.setChecked(self._camera_yielded)
        yield_cam.toggled.connect(self.set_camera_yielded)

        bg = menu.addAction(i18n.t("menu.background"))
        bg.setCheckable(True)
        bg.setChecked(self.background_white)
        bg.toggled.connect(self._toggle_background)

        passthrough = menu.addAction(i18n.t("menu.passthrough"))
        passthrough.setCheckable(True)
        passthrough.setChecked(self.viewport.passthrough)
        passthrough.toggled.connect(lambda v: self.toggle_passthrough() if v != self.viewport.passthrough else None)

        safe = menu.addAction(i18n.t("menu.safe_area"))
        safe.setCheckable(True)
        safe.setChecked(self.compositor.show_safe_area)
        safe.toggled.connect(self.set_show_safe_area)

        menu.addSeparator()
        menu.addAction(i18n.t("menu.close_board")).triggered.connect(lambda: self.toggle_board(False))
        return menu

    def _on_menu_requested(self, pos) -> None:
        self._board_menu().exec(pos)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_board()

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(_tray_icon(), self.app)
        menu = QMenu()
        self._act_board = QAction(i18n.t("tray.board"), menu)
        self._act_board.setCheckable(True)
        self._act_board.setChecked(self.viewport.isVisible())
        self._act_board.toggled.connect(self.toggle_board)
        act_pass = QAction(i18n.t("tray.passthrough"), menu)
        act_pass.triggered.connect(self.toggle_passthrough)
        act_undo = QAction(i18n.t("tray.undo"), menu)
        act_undo.triggered.connect(self.undo)
        act_clear = QAction(i18n.t("tray.clear"), menu)
        act_clear.triggered.connect(self.clear)
        act_region = QAction(i18n.t("tray.show_region"), menu)
        act_region.triggered.connect(self.show_viewport)
        pos_menu = QMenu("Board position (remote view)", menu)
        self._pos_group = QActionGroup(pos_menu)
        self._pos_group.setExclusive(True)
        for key in ANCHORS:
            a = QAction(i18n.anchor(key), pos_menu)
            a.setCheckable(True)
            a.setChecked(key == self.compositor.anchor)
            a.triggered.connect(lambda _=False, k=key: self.set_anchor(k))
            self._pos_group.addAction(a)
            pos_menu.addAction(a)

        size_menu = QMenu(i18n.t("menu.size"), menu)
        self._size_key = DEFAULT_SIZE
        self._size_group = QActionGroup(size_menu)
        self._size_group.setExclusive(True)
        for key in SIZES:
            a = QAction(i18n.size(key), size_menu)
            a.setCheckable(True)
            a.setChecked(key == self._size_key)
            a.triggered.connect(lambda _=False, k=key: self.set_panel_size(k))
            self._size_group.addAction(a)
            size_menu.addAction(a)

        act_yield = QAction(i18n.t("menu.yield"), menu)
        act_yield.setCheckable(True)
        act_yield.setChecked(False)
        act_yield.toggled.connect(self.set_camera_yielded)

        act_cam = QAction(i18n.t("menu.overlay"), menu)
        act_cam.setCheckable(True)
        act_cam.setChecked(self.camera_overlay)
        act_cam.toggled.connect(self.toggle_camera)
        act_bg = QAction(i18n.t("menu.background"), menu)
        act_bg.setCheckable(True)
        act_bg.setChecked(True)
        act_bg.toggled.connect(self._toggle_background)
        act_quit = QAction(i18n.t("tray.quit"), menu)
        act_quit.triggered.connect(self.app.quit)
        self._act_board_mirror = QAction(i18n.t("menu.board_mirror"), menu)
        self._act_board_mirror.setCheckable(True)
        self._act_board_mirror.setChecked(self.compositor.board_mirror)
        self._act_board_mirror.toggled.connect(self.set_board_mirror)
        for action in (self._act_board, act_pass, act_region, act_undo, act_clear,
                       act_cam, act_yield, act_bg, self._act_board_mirror):
            menu.addAction(action)
        menu.addSeparator()
        menu.addMenu(pos_menu)
        menu.addMenu(size_menu)
        menu.addSeparator()
        vcam_state = QAction(
            i18n.t("tray.vcam_state", name=self.config.device_name) if self.vcam_ok
            else i18n.t("tray.vcam_failed", error=self.vcam.last_error),
            menu,
        )
        vcam_state.setEnabled(False)
        menu.addAction(vcam_state)
        status = QAction(
            i18n.t("tray.output_ok") if self.output_ok
            else i18n.t("tray.output_failed", error=self.output_error or "-"), menu
        )
        status.setEnabled(False)
        menu.addAction(status)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Camera Whiteboard")
        self.tray.activated.connect(self._on_tray_activated)  # type: ignore[arg-type]
        self.tray.show()


_INSTANCE_HANDLE = []   # 保持互斥体句柄，防止被回收


def _claim_single_instance() -> bool:
    """只允许一个实例：两个实例会抢同一个虚拟摄像头/物理摄像头，画面会黑或闪。"""
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")
        handle = kernel32.CreateMutexW(None, False, "Global\\CameraWhiteboard.SingleInstance")
        already = kernel32.GetLastError() == 183   # ERROR_ALREADY_EXISTS
        if handle:
            _INSTANCE_HANDLE.append(handle)
        return not already
    except OSError:
        return True


def main(auto_quit: float = 0.0, vcam: VirtualCamera | None = None) -> int:
    """auto_quit > 0 时，若干秒后自动退出——用于打包后的无人值守冒烟。"""
    if vcam is None:
        # 源码运行路径：单实例检查 + 建虚拟摄像头都放在这里（exe 会在更早的阶段做完）
        from .bootstrap import claim_single_instance, start_virtual_camera

        if not claim_single_instance():
            set_log_path(FRAMES_PATH.parent / "app.log")
            log("Another instance is already running; exiting to avoid camera conflicts.")
            return 0
        vcam, _ = start_virtual_camera()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = WhiteboardApp(app, vcam=vcam)
    _ = window  # 保持引用
    if auto_quit > 0:
        QTimer.singleShot(int(auto_quit * 1000), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

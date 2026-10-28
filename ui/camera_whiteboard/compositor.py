"""合成：摄像头画面 + 一块带边界的白板面板。

面板位置与大小由 layout.py 决定（九宫格 9 个锚点 + 三分法 4 个交点）。
笔迹图层按 `Canvas.revision` 与面板尺寸缓存，只有变化时才重画。
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .canvas import Canvas
from .layout import DEFAULT_ANCHOR, DEFAULT_RATIO, MARGIN_RATIO, panel_rect
from .render import render

def draw_cover(painter: QPainter, base: QImage, target: QRect) -> None:
    """等比铺满并居中裁切。

    摄像头常见是 16:9，输出是 4:3；直接 drawImage(rect) 会把脸拉扁。
    这里按较大比例放大，再把多出来的部分裁掉。
    """
    bw, bh = base.width(), base.height()
    if bw <= 0 or bh <= 0 or target.width() <= 0 or target.height() <= 0:
        return
    scale = max(target.width() / bw, target.height() / bh)
    src_w = target.width() / scale
    src_h = target.height() / scale
    src = QRectF((bw - src_w) / 2, (bh - src_h) / 2, src_w, src_h)
    painter.drawImage(QRectF(target), base, src)


PANEL_BG = QColor(255, 255, 255)
PANEL_BORDER = QColor(90, 100, 120, 230)
PANEL_SHADOW = QColor(0, 0, 0, 70)


class Compositor:
    def __init__(
        self,
        canvas: Canvas,
        out_w: int = 1280,
        out_h: int = 960,
        background: tuple[int, int, int, int] | None = (255, 255, 255, 255),
        anchor: str = DEFAULT_ANCHOR,
        ratio: float = DEFAULT_RATIO,
        mirror: bool = False,
    ) -> None:
        self.canvas = canvas
        self.out_w = out_w
        self.out_h = out_h
        self.background = background
        self.anchor = anchor
        self.ratio = ratio
        # 画布关闭时只送摄像头画面（等于普通摄像头），面板与边框都不画
        self.panel_visible = True
        # 画布左右镜像：有些会议软件的自拍预览是镜像的，勾上后面看到的与手上一致
        self.mirror = mirror
        self.board_mirror = False  # Reflect only the board, never the camera.
        self.show_safe_area = False   # 调试：画出安全区边框，用来看客户端裁掉了多少边缘
        self._layer: QImage | None = None
        self._layer_key: tuple[int, int, int, int] | None = None
    # ---- 配置 ----

    def set_background(self, background: tuple[int, int, int, int] | None) -> None:
        self.background = background
        self.invalidate()

    def set_mirror(self, enabled: bool) -> None:
        if self.mirror != enabled:
            self.mirror = enabled
            self.invalidate()

    def set_show_safe_area(self, enabled: bool) -> None:
        self.show_safe_area = enabled
        self.invalidate()

    def set_board_mirror(self, enabled: bool) -> None:
        if self.board_mirror != enabled:
            self.board_mirror = enabled
            self.invalidate()

    def set_panel_visible(self, visible: bool) -> None:
        """画布开/关。关闭时输出就是摄像头画面本身，对面看不出我们存在。"""
        self.panel_visible = visible
        self.invalidate()

    def set_layout(self, anchor: str | None = None, ratio: float | None = None) -> None:
        if anchor and anchor != self.anchor:
            self.anchor = anchor
        if ratio is not None:
            self.ratio = ratio       # 保持选定锚点
        self.invalidate()

    def invalidate(self) -> None:
        self._layer = None
        self._layer_key = None

    # ---- 内部 ----

    def panel_rect(self) -> QRect:
        # Recompute the anchor, then optionally reflect the board across the video.
        rect = panel_rect(self.anchor, self.ratio, self.out_w, self.out_h)
        if self.board_mirror:
            rect.moveLeft(self.out_w - rect.x() - rect.width())
        return rect

    def _stroke_layer(self, panel: QRect) -> QImage:
        flip_strokes = self.mirror != self.board_mirror
        key = (self.canvas.revision, panel.width(), panel.height(), int(flip_strokes))
        if self._layer is None or self._layer_key != key:
            layer = render(self.canvas, panel.width(), panel.height())
            if flip_strokes:
                layer = layer.flipped(Qt.Orientation.Horizontal)
            self._layer = layer
            self._layer_key = key
        return self._layer

    # ---- 合成 ----

    def frame(self, base: QImage | None = None) -> QImage:
        """base 为摄像头画面；为 None 时用底色（白/透明）。"""
        out = QImage(self.out_w, self.out_h, QImage.Format.Format_ARGB32_Premultiplied)
        # 新建的 QImage 内容是未初始化的；透明色用 SourceOver 画上去等于没画，得先清空
        out.fill(Qt.GlobalColor.transparent)
        panel = self.panel_rect()

        painter = QPainter(out)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            if base is not None and not base.isNull():
                draw_cover(painter, base, out.rect())
            else:
                painter.fillRect(out.rect(),
                                 QColor(*self.background) if self.background else Qt.GlobalColor.transparent)

            if self.show_safe_area:
                mx = int(self.out_w * MARGIN_RATIO)
                my = int(self.out_h * MARGIN_RATIO)
                painter.setPen(QPen(QColor(255, 0, 255), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRect(mx, my, self.out_w - 2 * mx, self.out_h - 2 * my))

            if not self.panel_visible:
                return out

            # 面板阴影：让白板从画面里"浮"起来，边界更容易看清
            painter.fillRect(panel.translated(4, 6), PANEL_SHADOW)

            # 面板底 + 笔迹
            painter.fillRect(panel, PANEL_BG)
            painter.drawImage(panel, self._stroke_layer(panel))

            # 面板边界
            painter.setPen(QPen(PANEL_BORDER, 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(panel.adjusted(1, 1, -2, -2))
        finally:
            painter.end()
        return out

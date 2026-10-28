"""透明置顶悬浮层：在桌面上直接画，笔迹落在画布坐标里。

当前版本**未启用**：白板已改成白底窗口（见 viewport.py），本模块保留给将来的"桌面标注"
模式（在别人的窗口上直接圈画）。重新接入时注意：分层窗口里 alpha=0 的像素不参与命中测试，
空画布必须先铺一层 alpha=1 的底，否则点不中。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRegion
from PySide6.QtWidgets import QWidget

from .canvas import Canvas
from .clickthrough import set_click_through
from .geometry import Rect, widget_to_canvas

DEBUG_EVENTS = os.environ.get("CWB_UI_DEBUG") == "1"


@dataclass
class BrushSettings:
    color: tuple[int, int, int, int] = (255, 60, 60, 255)
    width: float = 6.0
    tool: str = "pen"


class OverlayWindow(QWidget):
    """覆盖整个虚拟桌面的透明窗口。"""

    def __init__(self, canvas: Canvas, origin: tuple[int, int], brush: BrushSettings | None = None) -> None:
        super().__init__(None)
        self.canvas = canvas
        self.origin = origin
        self.brush = brush or BrushSettings()
        self._drawing = False
        self._passthrough = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # 启动后短暂显示提示，顺便证明这层确实覆盖在桌面上
        self._hint_visible = True
        QTimer.singleShot(4000, self._hide_hint)

    # ---- 几何 ----

    def apply_virtual_geometry(self, rect: Rect) -> None:
        x, y, w, h = rect
        self.origin = (x, y)
        self.setGeometry(x, y, w, h)

    def set_draw_region(self, rect: Rect | None, exclude_top: int = 0) -> None:
        """把可绘制区域限制在白板窗口内；区域外输入直接落到桌面。

        setMask 同时限制绘制与命中，所以框外既画不了、也不挡其他窗口的操作。
        """
        if rect is None:
            self.setMask(QRegion())
            return
        x, y, w, h = rect
        local = QRect(int(x - self.origin[0]), int(y - self.origin[1]), int(w), int(h))
        if exclude_top > 0:
            local.setTop(local.top() + exclude_top)
            local.setHeight(local.height() - exclude_top)
        self.setMask(QRegion(local))

    def clear_draw_region(self) -> None:
        self.setMask(QRegion())

    # ---- 穿透 ----

    @property
    def passthrough(self) -> bool:
        return self._passthrough

    def set_passthrough(self, enabled: bool) -> bool:
        """穿透后鼠标事件交给下层窗口；此时只能靠全局快捷键切回来。"""
        self._passthrough = enabled
        ok = set_click_through(int(self.winId()), enabled)
        if enabled:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()
        return ok

    # ---- 鼠标 ----

    def _canvas_pos(self, event) -> tuple[float, float]:
        pos = event.position()
        return widget_to_canvas(pos.x(), pos.y(), self.origin)

    def _hide_hint(self) -> None:
        self._hint_visible = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if DEBUG_EVENTS:
            pos = event.position()
            print(f"[overlay] press at ({pos.x():.0f},{pos.y():.0f}) origin={self.origin}", flush=True)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = self._canvas_pos(event)
        if self.canvas.begin_stroke(x, y, color=self.brush.color, width=self.brush.width, tool=self.brush.tool):
            self._drawing = self.brush.tool != "eraser"
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        x, y = self._canvas_pos(event)
        if self.brush.tool == "eraser":
            if self.canvas.erase_at(x, y, self.brush.width):
                self.update()
            return
        if self._drawing and self.canvas.add_point(x, y):
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drawing:
            self.canvas.end_stroke()
            self._drawing = False
            self.update()

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            self.paint_content(painter)
        finally:
            painter.end()

    def paint_content(self, painter: QPainter) -> None:
        """绘制逻辑独立出来，便于在 QImage 上直接验证（不依赖窗口系统）。"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 关键：分层窗口里 alpha=0 的像素不参与命中测试，空画布会点不中。
        # 垫一层 alpha=1 的底，肉眼不可见，但整块区域都能接收鼠标。
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        for stroke in self.canvas.strokes:
            pen = QPen(QColor(*stroke.color))
            pen.setWidthF(max(0.5, stroke.width))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            points = [QPointF(x - self.origin[0], y - self.origin[1]) for x, y in stroke.points]
            if len(points) == 1:
                painter.drawPoint(points[0])
            elif points:
                painter.drawPolyline(points)

        if self._hint_visible:
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.setPen(QPen(QColor(255, 255, 255, 220)))
            text = "Ready to draw: hold the left mouse button. Ctrl+Alt+F8 toggles click-through."
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(text)
            x = (self.width() - width) // 2
            y = 60
            painter.fillRect(x - 16, y - 30, width + 32, 48, QColor(0, 0, 0, 150))
            painter.drawText(x, y, text)

        if self._passthrough:
            # 穿透状态下给一个极淡的边框提示，避免"看不见也点不着"的困惑
            painter.setPen(QPen(QColor(255, 255, 255, 40), 2))
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

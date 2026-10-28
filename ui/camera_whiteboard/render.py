"""把 Canvas 渲染成透明背景的 QImage。

映射关系见 specs/windows11/canvas-coordinate.md：
    输出帧坐标 = (画布坐标 - 视口原点) * s
视口等比贴入输出帧，比例不一致时留边，不拉伸。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .canvas import Canvas


def compute_scale(canvas: Canvas, out_w: int, out_h: int) -> tuple[float, float, float]:
    """返回 (scale, offset_x, offset_y)，保证等比且居中。"""
    _, _, vw, vh = canvas.viewport
    scale = min(out_w / vw, out_h / vh)
    offset_x = (out_w - vw * scale) / 2.0
    offset_y = (out_h - vh * scale) / 2.0
    return scale, offset_x, offset_y


def render(canvas: Canvas, out_w: int = 1280, out_h: int = 960,
           background: tuple[int, int, int, int] | None = None) -> QImage:
    """渲染为 ARGB32 预乘格式。background 为 None 时背景完全透明。"""
    image = QImage(out_w, out_h, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(*background) if background else Qt.GlobalColor.transparent)

    scale, offset_x, offset_y = compute_scale(canvas, out_w, out_h)
    vx, vy, _, _ = canvas.viewport

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        strokes = list(canvas.strokes)
        active = canvas.active_stroke
        if active is not None and active.points:
            strokes.append(active)  # 正在画的笔画也要出现在输出里
        for stroke in strokes:
            color = QColor(*stroke.color)
            pen = QPen(color)
            pen.setWidthF(max(0.5, stroke.width * scale))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            points = [
                QPointF((x - vx) * scale + offset_x, (y - vy) * scale + offset_y)
                for x, y in stroke.points
            ]
            if len(points) == 1:
                painter.drawPoint(points[0])
            else:
                painter.drawPolyline(points)
    finally:
        painter.end()

    return image


def visible_bounds(canvas: Canvas, out_w: int = 1280, out_h: int = 960) -> QRectF:
    """视口在输出帧里占的矩形（用于调试与后续合成）。"""
    scale, offset_x, offset_y = compute_scale(canvas, out_w, out_h)
    _, _, vw, vh = canvas.viewport
    return QRectF(offset_x, offset_y, vw * scale, vh * scale)

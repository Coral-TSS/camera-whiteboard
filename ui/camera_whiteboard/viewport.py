"""白板窗口：一块白底画布，同时也是送给虚拟摄像头的内容。

它是普通窗口：可拖动、可缩放、可关闭，关闭=停送白板。
框外不再是画笔——桌面照常可点，不会被这层挡住。

坐标：窗口左上角在屏幕上的位置即画布视口原点，窗口内坐标 + 窗口位置 = 画布坐标。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .canvas import Canvas
from .clickthrough import set_click_through
from .overlay import BrushSettings

BAR_H = 34
GRIP = 18
MIN_W = 320
MIN_H = 240
ASPECT = 3 / 4  # 输出是 1280x960，保持 4:3 不拉伸
PAPER = QColor(255, 255, 255)


class ViewportWindow(QWidget):
    geometry_changed = Signal()
    closed = Signal()
    menu_requested = Signal(QPoint)   # 参数是全局坐标，用来弹出菜单

    def __init__(self, canvas: Canvas, brush: BrushSettings | None = None, rect: QRect | None = None) -> None:
        super().__init__(None)
        self.canvas = canvas
        self.brush = brush or BrushSettings()
        self._mode: str | None = None
        self._drawing = False
        self._passthrough = False
        self._press_pos = QPoint()
        self._press_rect = QRect()

        # 不置顶：切到别的应用时白板应该让位（否则一直压在最上面很难用）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        # 窗口整体轻微透明，边缘不至于太硬；纸面仍是白色
        self.setWindowOpacity(0.98)

        if rect is None:
            rect = QRect(160, 120, 960, 720)
        size = self._fit(rect.width())
        self.setGeometry(rect.x(), rect.y(), size.width(), size.height())
        self._sync_canvas()

    # ---- 区域 ----

    def _body_size(self) -> tuple[int, int]:
        return (self.width(), max(1, self.height() - BAR_H))

    def _sync_canvas(self) -> None:
        # 画布是"纸"自己的坐标：纸 = 标题栏以下的区域，原点恒为 (0,0)。
        # 移动窗口不改变已有笔迹坐标，所以笔迹会跟着窗口一起走。
        bw, bh = self._body_size()
        self.canvas.set_viewport(0.0, 0.0, float(bw), float(bh))

    def set_region(self, rect: QRect) -> None:
        size = self._fit(rect.width())
        self.setGeometry(rect.x(), rect.y(), size.width(), size.height())
        self.raise_()
        self._sync_canvas()
        self.update()
        self.geometry_changed.emit()

    @staticmethod
    def _fit(width: int) -> QSize:
        """窗口高度 = 纸高 + 标题栏，保证纸面严格 4:3。"""
        width = max(MIN_W, int(width))
        return QSize(width, int(round(width * ASPECT)) + BAR_H)

    def resize_to_ratio(self, ratio: float, screen_w: int | None = None) -> None:
        """按"占屏幕宽度的比例"调整窗口大小（保持 4:3、位置不变）。"""
        if screen_w is None:
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            screen_w = screen.geometry().width() if screen else 1920
        size = self._fit(int(screen_w * ratio))
        g = self.geometry()
        self.set_region(QRect(g.x(), g.y(), size.width(), size.height()))

    def region(self) -> QRect:
        return self.geometry()

    def body_rect(self) -> QRect:
        return QRect(0, BAR_H, self.width(), self.height() - BAR_H)

    def _to_canvas(self, pos: QPoint) -> tuple[float, float]:
        """窗口内坐标 → 纸坐标（减去标题栏高度）。"""
        return (float(pos.x()), float(pos.y() - BAR_H))

    def _to_local(self, x: float, y: float) -> QPoint:
        return QPoint(int(x), int(y + BAR_H))

    # ---- 命中区域 ----

    def _close_rect(self) -> QRect:
        return QRect(self.width() - 34, 0, 34, BAR_H)

    def _menu_rect(self) -> QRect:
        return QRect(self.width() - 34 - 52, 0, 52, BAR_H)

    def _grip_rect(self) -> QRect:
        return QRect(self.width() - GRIP, self.height() - GRIP, GRIP, GRIP)

    # ---- 穿透 ----

    @property
    def passthrough(self) -> bool:
        return self._passthrough

    def set_passthrough(self, enabled: bool) -> bool:
        """穿透后整块白板不挡手，鼠标落到下面的窗口。"""
        self._passthrough = enabled
        ok = set_click_through(int(self.winId()), enabled)
        self.setCursor(Qt.CursorShape.ArrowCursor if enabled else Qt.CursorShape.CrossCursor)
        self.update()
        return ok

    # ---- 鼠标 ----

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if self._close_rect().contains(pos):
            self.hide()
            self.closed.emit()
            return
        if self._menu_rect().contains(pos):
            self.menu_requested.emit(self.mapToGlobal(pos))
            return
        if self._grip_rect().contains(pos):
            self._mode = "resize"
        elif pos.y() < BAR_H:
            self._mode = "move"
        elif self.body_rect().contains(pos):
            self._mode = "draw"
            x, y = self._to_canvas(pos)
            if self.canvas.begin_stroke(x, y, color=self.brush.color,
                                        width=self.brush.width, tool=self.brush.tool):
                self._drawing = self.brush.tool != "eraser"
                self.update()
            return
        else:
            return
        self._press_pos = event.globalPosition().toPoint()
        self._press_rect = self.geometry()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()

        if self._mode == "draw":
            x, y = self._to_canvas(pos)
            if self.brush.tool == "eraser":
                if self.canvas.erase_at(x, y, self.brush.width):
                    self.update()
            elif self._drawing and self.canvas.add_point(x, y):
                self.update()
            return

        if self._mode is None:
            if self._grip_rect().contains(pos):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif pos.y() < BAR_H:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            return

        delta = event.globalPosition().toPoint() - self._press_pos
        if self._mode == "move":
            self.setGeometry(self._press_rect.translated(delta))
        else:
            size = self._fit(self._press_rect.width() + delta.x())
            self.setGeometry(self._press_rect.x(), self._press_rect.y(), size.width(), size.height())

        self.raise_()
        self._sync_canvas()
        self.geometry_changed.emit()
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._mode == "draw" and self._drawing:
            self.canvas.end_stroke()
            self._drawing = False
            self.update()
        self._mode = None

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            self.paint_frame(painter)
        finally:
            painter.end()

    def paint_frame(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 纸面：白底（这就是送给摄像头的内容底）
        body = self.body_rect()
        painter.fillRect(body, PAPER)

        # 笔迹
        strokes = list(self.canvas.strokes)
        active = self.canvas.active_stroke
        if active is not None and active.points:
            strokes.append(active)
        for stroke in strokes:
            pen = QPen(QColor(*stroke.color))
            pen.setWidthF(max(0.5, stroke.width))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            points = [self._to_local(x, y) for x, y in stroke.points]
            if len(points) == 1:
                painter.drawPoint(points[0])
            elif points:
                painter.drawPolyline(points)

        # 标题栏
        painter.fillRect(0, 0, w, BAR_H, QColor(28, 30, 36, 235))
        font = QFont()
        font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei"])
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(225, 226, 232)))
        from .i18n import t

        hint = t("board.title_hint")
        if self._passthrough:
            hint = t("board.title_hint_passthrough")
        painter.drawText(
            QRect(12, 0, w - 100, BAR_H),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            f"{w} x {h}    {hint}",
        )

        # 菜单按钮
        menu = self._menu_rect()
        painter.setPen(QPen(QColor(210, 214, 224)))
        from .i18n import t

        painter.drawText(menu, int(Qt.AlignmentFlag.AlignCenter), t("board.menu_button"))

        # 关闭按钮
        close = self._close_rect()
        painter.setPen(QPen(QColor(235, 110, 110), 2))
        cx, cy = close.center().x(), close.center().y()
        painter.drawLine(cx - 6, cy - 6, cx + 6, cy + 6)
        painter.drawLine(cx - 6, cy + 6, cx + 6, cy - 6)

        # 纸面边框
        painter.setPen(QPen(QColor(120, 130, 148), 1))
        painter.drawRect(QRect(0, BAR_H, w - 1, h - BAR_H - 1))

        # 右下角缩放抓手
        grip = self._grip_rect()
        painter.fillRect(grip, QColor(90, 170, 255, 210))
        painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
        for i in range(3):
            offset = 4 + i * 5
            painter.drawLine(
                grip.right() - offset, grip.bottom() - 2,
                grip.right() - 2, grip.bottom() - offset,
            )

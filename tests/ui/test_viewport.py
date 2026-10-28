"""白板窗口测试：纸坐标模型、白底、绘制、拖动/缩放、关闭。

运行：QT_QPA_PLATFORM=offscreen python tests/ui/test_viewport.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QEvent, QPointF, QRect, Qt  # noqa: E402
from PySide6.QtGui import QImage, QMouseEvent, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.camera_whiteboard.canvas import Canvas  # noqa: E402
from ui.camera_whiteboard.overlay import BrushSettings  # noqa: E402
from ui.camera_whiteboard.viewport import BAR_H, ViewportWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def _evt(kind, x, y, buttons=Qt.MouseButton.LeftButton, button=Qt.MouseButton.LeftButton):
    local = QPointF(x, y)
    glob = QPointF(x + 400, y + 300)
    return QMouseEvent(kind, local, glob, button, buttons, Qt.KeyboardModifier.NoModifier)


def press(view, x, y):
    view.mousePressEvent(_evt(QEvent.Type.MouseButtonPress, x, y))


def move(view, x, y):
    view.mouseMoveEvent(_evt(QEvent.Type.MouseMove, x, y))


def release(view, x, y):
    view.mouseReleaseEvent(_evt(QEvent.Type.MouseButtonRelease, x, y, Qt.MouseButton.NoButton,
                                Qt.MouseButton.NoButton))


class PaperCoordinateTests(unittest.TestCase):
    """画布 = 纸自己的坐标，窗口只是纸的视口。"""

    def setUp(self):
        self.canvas = Canvas((0, 0, 1920, 1080))
        self.view = ViewportWindow(self.canvas, BrushSettings(), QRect(100, 200, 800, 600))

    def test_viewport_origin_is_paper_origin(self):
        self.assertEqual(self.canvas.viewport, (0.0, 0.0, 800.0, 600.0),
                         "视口原点恒为 (0,0)，与窗口在屏幕上的位置无关")

    def test_body_is_4_3(self):
        _, _, vw, vh = self.canvas.viewport
        self.assertAlmostEqual(vh / vw, 3 / 4, places=2)

    def test_draw_uses_paper_coords(self):
        press(self.view, 50, BAR_H + 100)      # 纸内 (50,100)
        release(self.view, 50, BAR_H + 100)
        self.assertEqual(self.canvas.strokes[0].points[0], (50.0, 100.0))

    def test_moving_window_does_not_change_existing_stroke(self):
        press(self.view, 50, BAR_H + 100)
        move(self.view, 150, BAR_H + 200)
        release(self.view, 150, BAR_H + 200)
        before = list(self.canvas.strokes[0].points)

        self.view.set_region(QRect(700, 500, 800, 600))   # 窗口挪到别处

        self.assertEqual(list(self.canvas.strokes[0].points), before,
                         "移动窗口不能改动笔迹坐标，否则内容会被留在原地")
        self.assertEqual(self.canvas.viewport, (0.0, 0.0, 800.0, 600.0))

    def test_same_spot_after_move_draws_same_paper_point(self):
        press(self.view, 40, BAR_H + 40)
        release(self.view, 40, BAR_H + 40)
        self.view.set_region(QRect(600, 400, 800, 600))
        press(self.view, 40, BAR_H + 40)
        release(self.view, 40, BAR_H + 40)
        self.assertEqual(self.canvas.strokes[0].points[0], self.canvas.strokes[1].points[0],
                         "窗口移动后，同一个窗口位置仍是同一处纸")


class WindowBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas((0, 0, 1920, 1080))
        self.view = ViewportWindow(self.canvas, BrushSettings(), QRect(100, 200, 800, 600))

    def test_drag_bar_moves_window_not_paper(self):
        press(self.view, 200, 10)
        move(self.view, 260, 60)
        release(self.view, 260, 60)
        self.assertEqual(self.view.geometry().topLeft().x(), 160)
        self.assertEqual(self.view.geometry().topLeft().y(), 250)
        self.assertEqual(self.canvas.viewport, (0.0, 0.0, 800.0, 600.0))

    def test_resize_grip_keeps_paper_4_3(self):
        w0 = self.view.width()
        gx, gy = w0 - 5, self.view.height() - 5
        press(self.view, gx, gy)
        move(self.view, gx + 120, gy + 90)
        release(self.view, gx + 120, gy + 90)
        _, _, vw, vh = self.canvas.viewport
        self.assertGreater(vw, w0)
        self.assertAlmostEqual(vh / vw, 3 / 4, places=2, msg="纸面必须严格 4:3，避免输出拉伸")

    def test_press_on_bar_does_not_draw(self):
        press(self.view, 100, 10)
        release(self.view, 100, 10)
        self.assertEqual(self.canvas.stroke_count, 0, "标题栏用来拖动，不应落笔")


class PaintTests(unittest.TestCase):
    def _paint(self, view):
        image = QImage(view.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        view.paint_frame(painter)
        painter.end()
        return image

    def test_body_is_white_paper(self):
        view = ViewportWindow(Canvas((0, 0, 1920, 1080)), BrushSettings(), QRect(0, 0, 600, 450))
        color = self._paint(view).pixelColor(300, BAR_H + 100)
        self.assertEqual((color.red(), color.green(), color.blue(), color.alpha()),
                         (255, 255, 255, 255), "纸面必须是白底不透明")

    def test_title_bar_is_dark(self):
        view = ViewportWindow(Canvas((0, 0, 1920, 1080)), BrushSettings(), QRect(0, 0, 600, 450))
        color = self._paint(view).pixelColor(300, 3)
        self.assertLess(color.lightness(), 120, "标题栏应是深色，和纸面区分开")

    def test_stroke_drawn_at_paper_position(self):
        canvas = Canvas((0, 0, 1920, 1080))
        brush = BrushSettings(color=(255, 0, 0, 255), width=12.0)
        view = ViewportWindow(canvas, brush, QRect(0, 0, 600, 450))
        press(view, 100, BAR_H + 100)
        move(view, 300, BAR_H + 100)
        release(view, 300, BAR_H + 100)
        image = self._paint(view)
        on_line = image.pixelColor(200, BAR_H + 100)
        self.assertGreater(on_line.red(), 200, "笔迹应画在纸坐标对应的位置上")
        self.assertLess(on_line.green(), 100)


class EraserTests(unittest.TestCase):
    def test_eraser_removes_stroke(self):
        canvas = Canvas((0, 0, 1920, 1080))
        brush = BrushSettings(color=(0, 0, 0, 255), width=8.0)
        view = ViewportWindow(canvas, brush, QRect(0, 0, 800, 600))
        press(view, 50, BAR_H + 100)
        move(view, 300, BAR_H + 100)
        release(view, 300, BAR_H + 100)
        self.assertEqual(canvas.stroke_count, 1)

        brush.tool = "eraser"
        brush.width = 20.0
        press(view, 170, BAR_H + 100)
        release(view, 170, BAR_H + 100)
        self.assertEqual(canvas.stroke_count, 0)


class LifecycleTests(unittest.TestCase):
    def test_close_button_hides_and_emits(self):
        view = ViewportWindow(Canvas((0, 0, 1920, 1080)), BrushSettings(), QRect(0, 0, 800, 600))
        fired = []
        view.closed.connect(lambda: fired.append(True))
        view.show()
        press(view, view.width() - 10, BAR_H // 2)
        self.assertFalse(view.isVisible())
        self.assertEqual(fired, [True])

    def test_passthrough_flag_toggles(self):
        view = ViewportWindow(Canvas((0, 0, 1920, 1080)), BrushSettings(), QRect(0, 0, 800, 600))
        self.assertFalse(view.passthrough)
        view.set_passthrough(True)
        self.assertTrue(view.passthrough)
        view.set_passthrough(False)
        self.assertFalse(view.passthrough)


if __name__ == "__main__":
    unittest.main(verbosity=2)

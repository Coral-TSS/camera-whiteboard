"""悬浮层交互测试（离屏）。运行：
    set QT_QPA_PLATFORM=offscreen && python tests/ui/test_overlay.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.camera_whiteboard.canvas import ERASER  # noqa: E402
from ui.camera_whiteboard.overlay import BrushSettings, OverlayWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def mouse_event(kind, x, y, buttons=Qt.MouseButton.LeftButton):
    local = QPointF(x, y)
    try:
        return QMouseEvent(kind, local, local, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
    except TypeError:  # 不同 Qt 版本构造签名差异
        return QMouseEvent(
            kind, local, local, local,
            Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier,
        )


def press(overlay, x, y):
    overlay.mousePressEvent(mouse_event(QEvent.Type.MouseButtonPress, x, y))


def move(overlay, x, y):
    overlay.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, x, y))


def release(overlay, x, y):
    overlay.mouseReleaseEvent(mouse_event(QEvent.Type.MouseButtonRelease, x, y, Qt.MouseButton.NoButton))


class DrawTests(unittest.TestCase):
    def setUp(self):
        from ui.camera_whiteboard.canvas import Canvas
        self.canvas = Canvas((0, 0, 1280, 960))
        self.brush = BrushSettings(color=(0, 255, 0, 255), width=6.0)
        self.overlay = OverlayWindow(self.canvas, (0, 0), self.brush)

    def test_drag_creates_stroke_with_widget_coords(self):
        press(self.overlay, 100, 120)
        move(self.overlay, 150, 160)
        move(self.overlay, 200, 220)
        release(self.overlay, 200, 220)

        self.assertEqual(self.canvas.stroke_count, 1)
        stroke = self.canvas.strokes[0]
        self.assertEqual(stroke.points[0], (100.0, 120.0))
        self.assertEqual(stroke.points[-1], (200.0, 220.0))
        self.assertEqual(stroke.color, (0, 255, 0, 255))
        self.assertEqual(stroke.width, 6.0)

    def test_negative_origin_offsets_to_canvas(self):
        from ui.camera_whiteboard.canvas import Canvas
        canvas = Canvas((-1920, 0, 4480, 1440))
        overlay = OverlayWindow(canvas, (-1920, 0), self.brush)
        press(overlay, 10, 20)
        release(overlay, 10, 20)
        self.assertEqual(canvas.strokes[0].points[0], (-1910.0, 20.0))

    def test_out_of_viewport_press_is_dropped(self):
        from ui.camera_whiteboard.canvas import Canvas
        canvas = Canvas((0, 0, 100, 100))
        overlay = OverlayWindow(canvas, (-50, -50), self.brush)   # 窗口比视口大
        press(overlay, 10, 10)                                    # 画布 (-40,-40) 在视口外
        release(overlay, 10, 10)
        self.assertEqual(canvas.stroke_count, 0)

    def test_eraser_tool_erases_on_drag(self):
        press(self.overlay, 100, 100)
        move(self.overlay, 300, 100)
        release(self.overlay, 300, 100)
        self.assertEqual(self.canvas.stroke_count, 1)

        self.brush.tool = ERASER
        self.brush.width = 20.0
        press(self.overlay, 200, 100)
        release(self.overlay, 200, 100)
        self.assertEqual(self.canvas.stroke_count, 0)


class PassthroughTests(unittest.TestCase):
    def test_flag_toggles(self):
        from ui.camera_whiteboard.canvas import Canvas
        overlay = OverlayWindow(Canvas((0, 0, 800, 600)), (0, 0), BrushSettings())
        self.assertFalse(overlay.passthrough)
        overlay.set_passthrough(True)
        self.assertTrue(overlay.passthrough)
        overlay.set_passthrough(False)
        self.assertFalse(overlay.passthrough)


class HitTestBaseTests(unittest.TestCase):
    """分层窗口里 alpha=0 的像素收不到鼠标，空画布必须垫 alpha>=1 的底。"""

    def _paint_to_image(self, overlay):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt as QtNS
        image = QImage(overlay.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QtNS.GlobalColor.transparent)
        painter = QPainter(image)
        overlay.paint_content(painter)
        painter.end()
        return image

    def test_empty_canvas_has_nonzero_alpha_everywhere(self):
        from ui.camera_whiteboard.canvas import Canvas
        overlay = OverlayWindow(Canvas((0, 0, 400, 300)), (0, 0), BrushSettings())
        overlay._hide_hint()          # 去掉提示条，只验证底色
        image = self._paint_to_image(overlay)
        for x, y in [(1, 1), (200, 150), (398, 298)]:
            self.assertGreater(image.pixelColor(x, y).alpha(), 0,
                               f"({x},{y}) 若是全透明，鼠标会穿透到桌面，无法起笔")

    def test_base_alpha_stays_low_enough_to_be_invisible(self):
        from ui.camera_whiteboard.canvas import Canvas
        overlay = OverlayWindow(Canvas((0, 0, 400, 300)), (0, 0), BrushSettings())
        overlay._hide_hint()
        image = self._paint_to_image(overlay)
        self.assertLessEqual(image.pixelColor(200, 150).alpha(), 8, "底色必须几乎不可见")

    def test_stroke_painted_over_base(self):
        from ui.camera_whiteboard.canvas import Canvas
        canvas = Canvas((0, 0, 400, 300))
        overlay = OverlayWindow(canvas, (0, 0), BrushSettings())
        overlay._hide_hint()
        press(overlay, 20, 20)
        move(overlay, 200, 20)
        release(overlay, 200, 20)
        image = self._paint_to_image(overlay)
        self.assertGreater(image.pixelColor(100, 20).alpha(), 100, "笔画应明显可见")


if __name__ == "__main__":
    unittest.main(verbosity=2)

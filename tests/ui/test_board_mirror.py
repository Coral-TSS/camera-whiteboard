"""Board reflection must never reflect the physical camera layer."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from ui.camera_whiteboard.canvas import Canvas
from ui.camera_whiteboard.compositor import Compositor


class BoardMirrorTests(unittest.TestCase):
    def make_compositor(self):
        canvas = Canvas((0, 0, 400, 300))
        canvas.begin_stroke(40, 70, color=(255, 0, 0, 255), width=20)
        canvas.add_point(40, 230)
        canvas.end_stroke()
        return Compositor(canvas, 1280, 720, anchor='tl', ratio=.3)

    def enable(self, comp, enabled=True):
        self.assertTrue(callable(getattr(comp, 'set_board_mirror', None)),
                        'The board needs an independent position-and-strokes mirror control')
        comp.set_board_mirror(enabled)

    def test_board_moves_to_reflected_position_and_returns(self):
        comp = self.make_compositor()
        before = comp.panel_rect()
        self.enable(comp)
        self.assertEqual(comp.panel_rect().getRect(), (858, 21, 384, 288))
        self.enable(comp, False)
        self.assertEqual(comp.panel_rect(), before)

    def test_strokes_flip_with_board_without_changing_camera_pixels(self):
        comp = self.make_compositor()
        base = QImage(1280, 720, QImage.Format.Format_RGB888)
        base.fill(QColor(10, 100, 220))
        painter = QPainter(base)
        painter.fillRect(0, 0, 640, 720, QColor(20, 200, 30))
        painter.end()
        normal = comp.frame(base)
        self.enable(comp)
        mirrored = comp.frame(base)
        # Bottom corners are camera-only and must retain their left/right colors.
        for image in (normal, mirrored):
            self.assertEqual(image.pixelColor(10, 700), QColor(20, 200, 30))
            self.assertEqual(image.pixelColor(1270, 700), QColor(10, 100, 220))
        panel = comp.panel_rect()
        right = mirrored.pixelColor(panel.right() - 38, panel.y() + 140)
        left = mirrored.pixelColor(panel.x() + 38, panel.y() + 140)
        self.assertGreater(right.red() - right.green(), 150)
        self.assertLess(left.red() - left.green(), 20)

    def test_hidden_board_never_changes_camera_when_mirror_toggled(self):
        comp = self.make_compositor()
        base = QImage(1280, 720, QImage.Format.Format_RGB888)
        base.fill(QColor(7, 80, 210))
        painter = QPainter(base)
        painter.fillRect(0, 0, 300, 720, QColor(100, 20, 30))
        painter.end()
        comp.set_panel_visible(False)
        before = comp.frame(base)
        self.enable(comp)
        self.assertEqual(comp.frame(base), before)

    def test_centered_board_stays_centered_and_stroke_flip_can_combine(self):
        comp = self.make_compositor()
        comp.set_layout(anchor='c')
        before = comp.panel_rect()
        comp.set_mirror(True)
        self.enable(comp)
        self.assertEqual(comp.panel_rect(), before)
        # Two explicit stroke reflections cancel, but position reflection still applies.
        image = comp.frame()
        pixel = image.pixelColor(before.x() + 38, before.y() + 140)
        self.assertGreater(pixel.red() - pixel.green(), 150)


if __name__ == '__main__':
    unittest.main()

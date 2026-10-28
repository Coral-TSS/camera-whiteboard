"""Output coordinates describe the unmirrored video received by other people."""
import unittest
from ui.camera_whiteboard.canvas import Canvas
from ui.camera_whiteboard.compositor import Compositor
from ui.camera_whiteboard.layout import panel_rect


class OutputPlacementTests(unittest.TestCase):
    def test_video_corners_use_small_equal_insets(self):
        expected = {"tl": (38, 21), "tr": (858, 21),
                    "bl": (38, 411), "br": (858, 411)}
        for anchor, xy in expected.items():
            with self.subTest(anchor=anchor):
                rect = panel_rect(anchor, .3, 1280, 720)
                self.assertEqual((rect.x(), rect.y()), xy)

    def test_resizing_keeps_selected_bottom_right_anchor(self):
        comp = Compositor(Canvas((0, 0, 640, 480)), 1280, 720, anchor="br", ratio=.3)
        comp.panel_rect()
        comp.set_layout(ratio=.5)
        self.assertEqual(comp.panel_rect().getRect(), (602, 219, 640, 480))

    def test_mirror_after_resize_never_moves_output_panel(self):
        comp = Compositor(Canvas((0, 0, 640, 480)), 1280, 720, anchor="br", ratio=.3)
        comp.panel_rect()
        comp.set_layout(ratio=.5)
        before = comp.panel_rect()
        comp.set_mirror(True)
        self.assertEqual(comp.panel_rect(), before)

    def test_default_output_keeps_left_stroke_on_left(self):
        canvas = Canvas((0, 0, 400, 300))
        canvas.begin_stroke(40, 80, color=(255, 0, 0, 255), width=20)
        canvas.add_point(40, 220)
        canvas.end_stroke()
        comp = Compositor(canvas, 1280, 720, anchor="tl", ratio=.3)
        frame = comp.frame()
        r = comp.panel_rect()
        left = frame.pixelColor(r.x() + 38, r.y() + 140)
        right = frame.pixelColor(r.right() - 38, r.y() + 140)
        self.assertGreater(left.red() - left.green(), 150)
        self.assertLess(right.red() - right.green(), 20)


if __name__ == "__main__":
    unittest.main()

"""坐标换算测试（不依赖窗口系统）。运行：python tests/ui/test_geometry.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.camera_whiteboard.geometry import (  # noqa: E402
    canvas_to_widget,
    clamp_viewport,
    union_rect,
    widget_to_canvas,
)


class UnionTests(unittest.TestCase):
    def test_single_screen(self):
        self.assertEqual(union_rect([(0, 0, 1920, 1080)]), (0, 0, 1920, 1080))

    def test_two_screens_left_negative(self):
        # 副屏在主屏左侧，坐标是负的
        rects = [(-1920, 0, 1920, 1080), (0, 0, 2560, 1440)]
        self.assertEqual(union_rect(rects), (-1920, 0, 4480, 1440))

    def test_stacked_screens(self):
        rects = [(0, 0, 1920, 1080), (0, 1080, 1280, 1024)]
        self.assertEqual(union_rect(rects), (0, 0, 1920, 2104))

    def test_empty(self):
        self.assertEqual(union_rect([]), (0, 0, 0, 0))


class MappingTests(unittest.TestCase):
    def test_roundtrip_with_negative_origin(self):
        origin = (-1920, 100)
        cx, cy = widget_to_canvas(300, 40, origin)
        self.assertEqual((cx, cy), (-1620, 140))
        self.assertEqual(canvas_to_widget(cx, cy, origin), (300, 40))

    def test_zero_origin_is_identity(self):
        self.assertEqual(widget_to_canvas(12.5, 7.5, (0, 0)), (12.5, 7.5))


class ViewportTests(unittest.TestCase):
    def test_min_size_enforced(self):
        self.assertEqual(clamp_viewport((10, 10, 0, -5), 64), (10, 10, 64, 64))

    def test_normal_rect_untouched(self):
        self.assertEqual(clamp_viewport((10, 10, 800, 600)), (10, 10, 800, 600))


if __name__ == "__main__":
    unittest.main(verbosity=2)

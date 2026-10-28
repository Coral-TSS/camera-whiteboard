"""版式计算测试：13 个锚点都在画面内、面板保持 4:3、三分法交点对齐。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.camera_whiteboard.layout import ANCHORS, SIZES, panel_rect  # noqa: E402

RATIOS = (0.3, 0.5, 0.7)

W, H = 1280, 960


class AnchorSetTests(unittest.TestCase):
    def test_thirteen_anchors(self):
        self.assertEqual(len(ANCHORS), 13)
        for key in ("tl", "tc", "tr", "cl", "c", "cr", "bl", "bc", "br"):
            self.assertIn(key, ANCHORS, "九宫格 9 个锚点必须齐")
        for key in ("t1l", "t1r", "t2l", "t2r"):
            self.assertIn(key, ANCHORS, "三分法 4 个交点必须齐")


class GeometryTests(unittest.TestCase):
    def test_all_anchors_stay_inside_frame(self):
        for key in ANCHORS:
            for ratio in RATIOS:
                r = panel_rect(key, ratio, W, H)
                self.assertGreaterEqual(r.x(), 0, f"{key}/{ratio} 左越界")
                self.assertGreaterEqual(r.y(), 0, f"{key}/{ratio} 上越界")
                self.assertLessEqual(r.right(), W - 1, f"{key}/{ratio} 右越界")
                self.assertLessEqual(r.bottom(), H - 1, f"{key}/{ratio} 下越界")

    def test_panel_keeps_4_3(self):
        for key in ANCHORS:
            r = panel_rect(key, 0.5, W, H)
            self.assertAlmostEqual(r.height() / r.width(), 0.75, places=2)

    def test_sizes_are_ordered(self):
        small = panel_rect("c", SIZES["s"][1], W, H).width()
        medium = panel_rect("c", SIZES["m"][1], W, H).width()
        large = panel_rect("c", SIZES["l"][1], W, H).width()
        self.assertLess(small, medium)
        self.assertLess(medium, large)

    def test_grid_positions_relative_order(self):
        tl = panel_rect("tl", 0.3, W, H)
        tr = panel_rect("tr", 0.3, W, H)
        bl = panel_rect("bl", 0.3, W, H)
        self.assertLess(tl.x(), tr.x())
        self.assertLess(tl.y(), bl.y())
        self.assertLessEqual(tl.y(), panel_rect("c", 0.3, W, H).y())


class ThirdsTests(unittest.TestCase):
    def test_thirds_anchor_centers_on_intersections(self):
        for key, fx, fy in (("t1l", 1 / 3, 1 / 3), ("t1r", 2 / 3, 1 / 3),
                            ("t2l", 1 / 3, 2 / 3), ("t2r", 2 / 3, 2 / 3)):
            r = panel_rect(key, 0.3, W, H)
            cx = r.x() + r.width() / 2
            cy = r.y() + r.height() / 2
            self.assertAlmostEqual(cx, W * fx, delta=2, msg=f"{key} 水平方向没对准三分线")
            self.assertAlmostEqual(cy, H * fy, delta=2, msg=f"{key} 垂直方向没对准三分线")

    def test_center_anchor_is_centered(self):
        r = panel_rect("c", 0.5, W, H)
        self.assertAlmostEqual(r.x() + r.width() / 2, W / 2, delta=2)
        self.assertAlmostEqual(r.y() + r.height() / 2, H / 2, delta=2)


class RatioTests(unittest.TestCase):
    def test_ratio_drives_panel_width(self):
        a = panel_rect("br", 0.3, W, H).width()
        b = panel_rect("br", 0.6, W, H).width()
        self.assertAlmostEqual(b, a * 2, delta=4, msg="面板宽度应随比例同步变化")

    def test_ratio_is_clamped(self):
        self.assertEqual(panel_rect("c", 0.01, W, H).width(), panel_rect("c", 0.20, W, H).width())
        self.assertEqual(panel_rect("c", 5.0, W, H).width(), panel_rect("c", 0.90, W, H).width())


if __name__ == "__main__":
    unittest.main(verbosity=2)

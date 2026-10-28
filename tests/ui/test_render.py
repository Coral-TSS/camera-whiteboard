"""渲染测试：透明背景、笔画可见、缩放影响线宽。

运行：.venv\\Scripts\\python.exe tests\\ui\\test_render.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtGui import QImage  # noqa: E402

from ui.camera_whiteboard.canvas import Canvas  # noqa: E402
from ui.camera_whiteboard.render import compute_scale, render  # noqa: E402


def column_thickness(image: QImage, x: int, threshold: int = 20) -> int:
    count = 0
    for y in range(image.height()):
        if image.pixelColor(x, y).alpha() > threshold:
            count += 1
    return count


def alpha_at(image: QImage, x: int, y: int) -> int:
    return image.pixelColor(x, y).alpha()


class TransparencyTests(unittest.TestCase):
    def test_empty_canvas_is_fully_transparent(self):
        image = render(Canvas((0, 0, 1280, 960)), 1280, 960)
        self.assertEqual(image.format(), QImage.Format.Format_ARGB32_Premultiplied)
        for x, y in [(0, 0), (640, 480), (1279, 959)]:
            self.assertEqual(alpha_at(image, x, y), 0, f"({x},{y}) 应为全透明")

    def test_background_stays_transparent_around_stroke(self):
        canvas = Canvas((0, 0, 1280, 960))
        canvas.begin_stroke(100, 480, color=(255, 0, 0, 255), width=10)
        canvas.add_point(1180, 480)
        canvas.end_stroke()

        image = render(canvas, 1280, 960)
        self.assertGreater(alpha_at(image, 640, 480), 200)   # 笔画处不透明
        self.assertEqual(alpha_at(image, 640, 100), 0)      # 远离笔画仍透明
        self.assertEqual(alpha_at(image, 10, 10), 0)


class ScaleTests(unittest.TestCase):
    def test_scale_factor_computed_by_fit_and_center(self):
        scale, ox, oy = compute_scale(Canvas((0, 0, 640, 480)), 1280, 960)
        self.assertAlmostEqual(scale, 2.0)
        self.assertAlmostEqual(ox, 0.0)
        self.assertAlmostEqual(oy, 0.0)

    def test_letterbox_when_aspect_differs(self):
        # 视口 4:3 贴进 16:9 输出，应上下留边
        scale, ox, oy = compute_scale(Canvas((0, 0, 1280, 960)), 1280, 720)
        self.assertAlmostEqual(scale, 0.75)
        self.assertAlmostEqual(ox, 160.0)
        self.assertAlmostEqual(oy, 0.0)

    def test_zoom_thickens_rendered_stroke(self):
        """同一条 8 单位线，视口缩小一半（s 变 2）后屏幕线宽应翻倍。"""
        def thickness_for(viewport):
            _, _, vw, vh = viewport
            canvas = Canvas(viewport)
            # 两端都在视口内，避免被"越界丢弃"规则裁掉
            canvas.begin_stroke(0, vh / 2, color=(0, 0, 255, 255), width=8)
            canvas.add_point(vw, vh / 2)
            canvas.end_stroke()
            image = render(canvas, 1280, 960)
            # 两种视口下这条线都渲染在输出帧 y=480 处
            return column_thickness(image, 640)

        wide = thickness_for((0, 0, 1280, 960))     # s = 1
        zoomed = thickness_for((0, 0, 640, 480))    # s = 2
        self.assertGreater(wide, 0, "s=1 时应该能看到线")
        self.assertGreater(zoomed, wide * 1.6, f"s 加倍后线宽应明显变粗：{wide} -> {zoomed}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

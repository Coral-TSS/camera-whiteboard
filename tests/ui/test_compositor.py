"""合成器测试：白板面板的位置/边界、摄像头打底、笔迹盖在面板上。

运行：QT_QPA_PLATFORM=offscreen python tests/ui/test_compositor.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.camera_whiteboard.canvas import Canvas  # noqa: E402
from ui.camera_whiteboard.compositor import Compositor  # noqa: E402

app = QApplication.instance() or QApplication([])

W, H = 320, 240


def solid(width, height, rgb):
    image = QImage(width, height, QImage.Format.Format_RGB888)
    image.fill(QColor(*rgb))
    return image


def rgb_at(image, x, y):
    c = image.pixelColor(x, y)
    return (c.red(), c.green(), c.blue())


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas((0, 0, W, H))
        self.comp = Compositor(self.canvas, W, H, background=(255, 255, 255, 255), anchor="br", ratio=0.3)

    def test_camera_visible_outside_panel(self):
        base = solid(160, 120, (10, 200, 30))
        out = self.comp.frame(base)
        self.assertFalse(self.comp.panel_rect().contains(10, 10))
        self.assertEqual(rgb_at(out, 10, 10), (10, 200, 30), "面板外应能看到摄像头画面")

    def test_panel_is_white(self):
        base = solid(160, 120, (10, 200, 30))
        out = self.comp.frame(base)
        center = self.comp.panel_rect().center()
        self.assertEqual(rgb_at(out, center.x(), center.y()), (255, 255, 255), "面板内部应是白底")

    def test_panel_has_visible_border(self):
        base = solid(160, 120, (10, 200, 30))
        out = self.comp.frame(base)
        panel = self.comp.panel_rect()
        edge = out.pixelColor(panel.x() + 2, panel.y() + 2)
        self.assertLess(edge.lightness(), 250, "面板边界必须画出来，否则看不出范围")
        self.assertNotEqual((edge.red(), edge.green(), edge.blue()), (10, 200, 30))

    def test_stroke_inside_panel(self):
        self.canvas.begin_stroke(20, H // 2, color=(255, 0, 0, 255), width=16)
        self.canvas.add_point(W - 20, H // 2)
        self.canvas.end_stroke()
        out = self.comp.frame(solid(160, 120, (30, 40, 50)))
        center = self.comp.panel_rect().center()
        c = out.pixelColor(center.x(), center.y())
        self.assertGreater(c.red(), 180, "笔迹应画在面板内部")

    def test_no_camera_falls_back_to_background(self):
        out = self.comp.frame(None)
        self.assertEqual(rgb_at(out, 10, 10), (255, 255, 255))

    def test_transparent_background_outside_panel(self):
        comp = Compositor(self.canvas, W, H, background=None, anchor="br", ratio=0.3)
        out = comp.frame(None)
        self.assertEqual(out.pixelColor(5, 5).alpha(), 0, "透明底时面板外应全透明")
        self.assertEqual(out.pixelColor(comp.panel_rect().center()).alpha(), 255)


class AspectTests(unittest.TestCase):
    """摄像头常是 16:9，输出是 4:3：必须等比裁切，不能拉扁。"""

    def _square_size_in_output(self, base_w, base_h, out_w, out_h, square):
        canvas = Canvas((0, 0, out_w, out_h))
        comp = Compositor(canvas, out_w, out_h, background=(255, 255, 255, 255))
        comp.set_panel_visible(False)   # 只看摄像头铺满时的几何，别被白板面板盖住
        base = QImage(base_w, base_h, QImage.Format.Format_RGB888)
        base.fill(QColor(30, 30, 30))
        painter = QPainter(base)
        painter.fillRect((base_w - square) // 2, (base_h - square) // 2, square, square, QColor(255, 0, 0))
        painter.end()

        out = comp.frame(base)
        xs, ys = [], []
        for y in range(0, out_h, 2):
            for x in range(0, out_w, 2):
                c = out.pixelColor(x, y)
                if c.red() > 180 and c.green() < 80:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return 0, 0
        return max(xs) - min(xs), max(ys) - min(ys)

    def test_16_9_camera_not_stretched_into_4_3(self):
        w, h = self._square_size_in_output(480, 270, 320, 240, 90)
        self.assertGreater(w, 0, "应该能找到红色方块")
        self.assertAlmostEqual(w, h, delta=3, msg="方块被拉成长方形，说明画面变形了")

    def test_same_aspect_fills_completely(self):
        canvas = Canvas((0, 0, 320, 240))
        comp = Compositor(canvas, 320, 240)
        comp.set_panel_visible(False)
        base = QImage(640, 480, QImage.Format.Format_RGB888)
        base.fill(QColor(10, 200, 30))
        out = comp.frame(base)
        # 四角都应是摄像头颜色（面板在右下，取左上、右上角）
        self.assertEqual(rgb_at(out, 2, 2), (10, 200, 30))
        self.assertEqual(rgb_at(out, 317, 2), (10, 200, 30))


class PanelVisibilityTests(unittest.TestCase):
    """画布关闭时，输出必须退回纯摄像头画面（对面看不出我们存在）。"""

    def setUp(self):
        self.canvas = Canvas((0, 0, W, H))
        self.comp = Compositor(self.canvas, W, H, background=(255, 255, 255, 255), anchor="br", ratio=0.3)

    def test_panel_hidden_shows_camera_everywhere(self):
        self.comp.set_panel_visible(False)
        out = self.comp.frame(solid(160, 120, (10, 200, 30)))
        panel = self.comp.panel_rect()
        self.assertEqual(rgb_at(out, panel.center().x(), panel.center().y()), (10, 200, 30),
                         "画布关闭后不该再出现白板面板")
        self.assertEqual(rgb_at(out, 10, 10), (10, 200, 30))

    def test_panel_hidden_ignores_strokes(self):
        self.canvas.begin_stroke(20, H // 2, color=(255, 0, 0, 255), width=20)
        self.canvas.add_point(W - 20, H // 2)
        self.canvas.end_stroke()
        self.comp.set_panel_visible(False)
        out = self.comp.frame(solid(160, 120, (10, 200, 30)))
        panel = self.comp.panel_rect()
        self.assertEqual(rgb_at(out, panel.center().x(), panel.center().y()), (10, 200, 30),
                         "画布关闭后笔迹也不该送出去")

    def test_panel_can_be_turned_back_on(self):
        self.comp.set_panel_visible(False)
        self.comp.set_panel_visible(True)
        out = self.comp.frame(solid(160, 120, (10, 200, 30)))
        center = self.comp.panel_rect().center()
        self.assertEqual(rgb_at(out, center.x(), center.y()), (255, 255, 255))


class LayoutSwitchTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas((0, 0, W, H))
        self.comp = Compositor(self.canvas, W, H, background=(255, 255, 255, 255), anchor="br", ratio=0.3)

    def test_anchor_change_moves_panel(self):
        before = self.comp.panel_rect()
        self.comp.set_layout(anchor="tl")
        after = self.comp.panel_rect()
        self.assertLess(after.x(), before.x())
        self.assertLess(after.y(), before.y())

    def test_size_change_enlarges_panel(self):
        before = self.comp.panel_rect().width()
        self.comp.set_layout(ratio=0.7)
        self.assertGreater(self.comp.panel_rect().width(), before)

    def test_layout_change_rebuilds_stroke_layer(self):
        base = solid(160, 120, (1, 2, 3))
        self.comp.frame(base)
        layer = self.comp._layer
        self.comp.set_layout(anchor="tl")
        self.comp.frame(base)
        self.assertIsNot(self.comp._layer, layer, "换版式后笔迹层要按新尺寸重画")


class MirrorTests(unittest.TestCase):
    """镜像：笔迹左右翻转；用户选的方位不变（镜像会换落位锚点，视图里才对得上）。"""

    def setUp(self):
        self.canvas = Canvas((0, 0, W, H))
        self.comp = Compositor(self.canvas, W, H, background=(255, 255, 255, 255),
                               anchor="tl", ratio=0.4)
        # 只在画布左侧画一条红线
        self.canvas.begin_stroke(20, H // 2, color=(255, 0, 0, 255), width=14)
        self.canvas.add_point(W * 0.3, H // 2)
        self.canvas.end_stroke()

    def _red_center(self, image):
        panel = self.comp.panel_rect()
        xs = []
        for y in range(panel.top(), panel.bottom(), 2):
            for x in range(panel.left(), panel.right(), 2):
                c = image.pixelColor(x, y)
                if c.red() > 180 and c.green() < 90:
                    xs.append(x)
        if not xs:
            return None
        return sum(xs) / len(xs), panel

    def test_mirror_flips_content_inside_panel(self):
        base = solid(160, 120, (10, 10, 10))
        normal = self._red_center(self.comp.frame(base))
        self.comp.set_mirror(True)
        flipped = self._red_center(self.comp.frame(base))
        self.assertIsNotNone(normal)
        self.assertIsNotNone(flipped)

        nx, npanel = normal
        fx, fpanel = flipped
        # 各自相对自己面板的位置：不镜像在左半，镜像在右半
        self.assertLess(nx, npanel.left() + npanel.width() / 2, "不镜像时笔迹在左半")
        self.assertGreater(fx, fpanel.left() + fpanel.width() / 2, "镜像后笔迹在右半")

    def test_mirror_does_not_change_panel_size(self):
        before = self.comp.panel_rect()
        self.comp.set_mirror(True)
        after = self.comp.panel_rect()
        self.assertEqual((before.width(), before.height()), (after.width(), after.height()))

    def test_mirror_does_not_move_panel(self):
        """锚点位置不许跟着镜像翻：选哪儿就在哪儿。"""
        before = self.comp.panel_rect()
        self.comp.set_mirror(True)
        after = self.comp.panel_rect()
        self.assertEqual(before, after, "镜像只能翻内容，不能翻位置")

    def test_center_anchor_unaffected_by_mirror(self):
        comp = Compositor(self.canvas, W, H, anchor="c", ratio=0.4, mirror=True)
        with_mirror = comp.panel_rect()
        comp2 = Compositor(self.canvas, W, H, anchor="c", ratio=0.4)
        without = comp2.panel_rect()
        self.assertEqual(with_mirror, without, "居中锚点镜像前后位置应一致")


class CacheTests(unittest.TestCase):
    def test_stroke_layer_reused_until_canvas_changes(self):
        canvas = Canvas((0, 0, W, H))
        comp = Compositor(canvas, W, H)
        base = solid(160, 120, (1, 2, 3))
        comp.frame(base)
        layer = comp._layer
        comp.frame(base)
        self.assertIs(comp._layer, layer)

        canvas.begin_stroke(10, 10)
        canvas.end_stroke()
        comp.frame(base)
        self.assertIsNot(comp._layer, layer)


if __name__ == "__main__":
    unittest.main(verbosity=2)

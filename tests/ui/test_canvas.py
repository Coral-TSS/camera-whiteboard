"""笔迹模型行为测试。运行：.venv\\Scripts\\python.exe tests\\ui\\test_canvas.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.camera_whiteboard.canvas import ERASER, PEN, Canvas  # noqa: E402


class ViewportTests(unittest.TestCase):
    def test_outside_viewport_rejected(self):
        canvas = Canvas((0, 0, 100, 100))
        self.assertFalse(canvas.begin_stroke(-5, 50))     # 左边界外
        self.assertFalse(canvas.begin_stroke(50, 101))    # 下边界外
        self.assertEqual(canvas.stroke_count, 0)

    def test_stroke_keeps_only_inbounds_points(self):
        canvas = Canvas((0, 0, 100, 100))
        self.assertTrue(canvas.begin_stroke(50, 50))
        self.assertTrue(canvas.add_point(60, 50))
        self.assertFalse(canvas.add_point(500, 50))       # 越界，丢弃
        self.assertTrue(canvas.add_point(70, 50))         # 回到界内，继续
        self.assertTrue(canvas.end_stroke())

        stroke = canvas.strokes[0]
        self.assertEqual(stroke.points, [(50.0, 50.0), (60.0, 50.0), (70.0, 50.0)])

    def test_viewport_move_keeps_strokes(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(10, 10)
        canvas.end_stroke()
        canvas.set_viewport(500, 500, 100, 100)
        self.assertEqual(canvas.stroke_count, 1)           # 移动视口不删笔画

    def test_single_point_stroke_is_kept(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(5, 5)
        self.assertTrue(canvas.end_stroke())
        self.assertEqual(len(canvas.strokes[0].points), 1)


class WidthTests(unittest.TestCase):
    def test_zoom_does_not_touch_stored_width(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(10, 10, width=8.0)
        canvas.end_stroke()
        canvas.set_viewport(0, 0, 200, 200)               # 相当于缩小
        self.assertEqual(canvas.strokes[0].width, 8.0)    # 画布单位不变


class UndoTests(unittest.TestCase):
    def test_undo_add(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(10, 10)
        canvas.end_stroke()
        self.assertEqual(canvas.stroke_count, 1)
        self.assertTrue(canvas.undo())
        self.assertEqual(canvas.stroke_count, 0)
        self.assertFalse(canvas.undo())                   # 栈空

    def test_undo_clear(self):
        canvas = Canvas((0, 0, 100, 100))
        for x in (10, 20, 30):
            canvas.begin_stroke(x, 10)
            canvas.end_stroke()
        self.assertTrue(canvas.clear())
        self.assertEqual(canvas.stroke_count, 0)
        self.assertTrue(canvas.undo())
        self.assertEqual(canvas.stroke_count, 3)

    def test_clear_on_empty_returns_false(self):
        self.assertFalse(Canvas((0, 0, 100, 100)).clear())


class EraserTests(unittest.TestCase):
    def test_erase_removes_whole_stroke(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(10, 10)
        canvas.add_point(90, 10)
        canvas.end_stroke()

        removed = canvas.erase_at(50, 12, 5)
        self.assertEqual(removed, 1)
        self.assertEqual(canvas.stroke_count, 0)

    def test_erase_miss_keeps_stroke(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(10, 10)
        canvas.end_stroke()
        self.assertEqual(canvas.erase_at(80, 80, 5), 0)
        self.assertEqual(canvas.stroke_count, 1)

    def test_undo_erase_restores_position(self):
        canvas = Canvas((0, 0, 100, 100))
        for x in (10, 30, 50):
            canvas.begin_stroke(x, 10)
            canvas.add_point(x + 2, 10)
            canvas.end_stroke()

        canvas.erase_at(30, 10, 3)                        # 删中间那条
        self.assertEqual(canvas.stroke_count, 2)
        self.assertTrue(canvas.undo())
        self.assertEqual(canvas.stroke_count, 3)
        self.assertEqual(canvas.strokes[1].points[0], (30.0, 10.0))  # 回到原索引

    def test_eraser_tool_via_begin_stroke(self):
        canvas = Canvas((0, 0, 100, 100))
        canvas.begin_stroke(10, 10)
        canvas.end_stroke()
        self.assertTrue(canvas.begin_stroke(10, 10, tool=ERASER, width=6))
        self.assertEqual(canvas.stroke_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

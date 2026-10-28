"""摄像头状态测试：暗帧判定、没画面时不把黑帧送出去。

运行：QT_QPA_PLATFORM=offscreen python tests/ui/test_camera.py
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.camera_whiteboard.canvas import Canvas  # noqa: E402
from ui.camera_whiteboard.camera import NullCamera, is_dark_frame  # noqa: E402
from ui.camera_whiteboard.compositor import Compositor  # noqa: E402
from ui.camera_whiteboard.publisher import FramePublisher  # noqa: E402

app = QApplication.instance() or QApplication([])


class DarkFrameTests(unittest.TestCase):
    def test_black_frame_is_dark(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertTrue(is_dark_frame(frame))

    def test_normal_brightness_is_not_dark(self):
        frame = np.full((480, 640, 3), 110, dtype=np.uint8)
        self.assertFalse(is_dark_frame(frame))

    def test_dim_but_visible_is_not_dark(self):
        # 昏暗室内大致 30~60，不能误判成"没画面"
        frame = np.full((480, 640, 3), 35, dtype=np.uint8)
        self.assertFalse(is_dark_frame(frame))

    def test_threshold_boundary(self):
        self.assertTrue(is_dark_frame(np.full((60, 80, 3), 5, dtype=np.uint8)))
        self.assertFalse(is_dark_frame(np.full((60, 80, 3), 10, dtype=np.uint8)))


class NullCameraTests(unittest.TestCase):
    def test_null_camera_never_gives_frame(self):
        cam = NullCamera()
        self.assertFalse(cam.is_open)
        self.assertIsNone(cam.latest())
        self.assertIsNone(cam.latest_usable())
        self.assertTrue(cam.is_dark)


class DarkFallbackTests(unittest.TestCase):
    """摄像头没画面时，输出应是白底 + 笔迹，而不是一片黑。"""

    class DarkCamera:
        width, height = 640, 480
        is_open = True
        last_error = None
        measured_fps = 0.0
        is_dark = True

        def latest(self):
            black = QImage(self.width, self.height, QImage.Format.Format_RGB888)
            black.fill(QColor(0, 0, 0))
            return black

        def latest_usable(self):
            return None  # 暗帧不交给合成器

    def test_dark_camera_falls_back_to_white(self):
        canvas = Canvas((0, 0, 320, 240))
        comp = Compositor(canvas, 320, 240, background=(255, 255, 255, 255))
        pub = FramePublisher(canvas, None, 320, 240, background=(255, 255, 255, 255))
        pub.set_compositor(comp, self.DarkCamera())

        image = pub._render_image()
        c = image.pixelColor(300, 200)
        self.assertEqual((c.red(), c.green(), c.blue(), c.alpha()), (255, 255, 255, 255),
                         "暗帧时不能输出黑底")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""发布器测试：头部合法、像素正确、内容不变也持续发布。

运行：QT_QPA_PLATFORM=offscreen python tests/ui/test_publisher.py
"""

import os
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.camera_whiteboard.canvas import Canvas  # noqa: E402
from ui.camera_whiteboard.publisher import HEADER_BYTES, MAGIC, FramePublisher  # noqa: E402

W, H = 1280, 960


def read_header(path):
    with open(path, "rb") as f:
        return struct.unpack("<IIIIIIIIQQQII", f.read(HEADER_BYTES))


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "frames.bin")
        self.canvas = Canvas((0, 0, W, H))
        self.pub = FramePublisher(self.canvas, self.path, W, H)

    def tearDown(self):
        self.pub.close()
        self.tmp.cleanup()

    def test_header_and_size(self):
        self.assertTrue(self.pub.publish())
        magic, ver, hb, w, h, stride, fmt, _r, seq, fid, ts, state, _r2 = read_header(self.path)
        self.assertEqual((magic, ver, hb), (MAGIC, 1, HEADER_BYTES))
        self.assertEqual((w, h, stride), (W, H, W * 4))
        self.assertEqual(fmt, 0)                      # BGRA
        self.assertEqual(seq % 2, 0, "写完后 seq 必须是偶数")
        self.assertGreater(fid, 0)
        self.assertEqual(state, 1)
        self.assertEqual(os.path.getsize(self.path), HEADER_BYTES + stride * h)

    def test_timestamp_is_fresh_filetime(self):
        self.assertTrue(self.pub.publish())
        *_, ts, _state, _r2 = read_header(self.path)
        now = int((time.time() + 11644473600) * 10_000_000)
        self.assertLess(abs(now - ts), 5 * 10_000_000, "时间戳应是近 5 秒内的 FILETIME")

    def test_pixels_are_bgra_and_contain_stroke(self):
        self.canvas.begin_stroke(100, 100, color=(255, 0, 0, 255), width=20)
        self.canvas.add_point(300, 100)
        self.canvas.end_stroke()
        self.assertTrue(self.pub.publish())

        with open(self.path, "rb") as f:
            f.seek(HEADER_BYTES + 100 * W * 4 + 200 * 4)
            b, g, r, a = f.read(4)
        self.assertEqual((b, g, r, a), (0, 0, 255, 255), "纯红不透明在 BGRA 里应是 0,0,255,255")

    def test_empty_area_stays_transparent(self):
        self.assertTrue(self.pub.publish())
        with open(self.path, "rb") as f:
            f.seek(HEADER_BYTES + 900 * W * 4 + 1200 * 4)
            _b, _g, _r, a = f.read(4)
        self.assertEqual(a, 0, "没画东西的地方必须全透明")

    def test_republish_without_change_keeps_stream_fresh(self):
        self.pub.publish()
        _, _, _, _, _, _, _, _, _, fid1, ts1, _, _ = read_header(self.path)
        time.sleep(0.05)
        self.pub.publish()
        _, _, _, _, _, _, _, _, _, fid2, ts2, _, _ = read_header(self.path)
        self.assertGreater(fid2, fid1, "frameId 必须递增")
        self.assertGreater(ts2, ts1, "时间戳必须更新，否则媒体源会判定帧过期")

    def test_render_cached_when_canvas_unchanged(self):
        self.pub.publish()
        first = id(self.pub._cached_image)
        self.pub.publish()
        self.assertEqual(id(self.pub._cached_image), first, "画布没变就不该重复渲染")

    def test_render_refreshed_after_change(self):
        self.pub.publish()
        before = self.pub._cached_image
        self.canvas.begin_stroke(10, 10, width=8)
        self.canvas.end_stroke()
        self.pub.publish()
        self.assertIsNot(self.pub._cached_image, before, "画布变化后必须重新渲染")

    def test_background_fill_is_opaque(self):
        self.pub.set_background((24, 26, 32, 255))
        self.assertTrue(self.pub.publish())
        with open(self.path, "rb") as f:
            f.seek(HEADER_BYTES + 900 * W * 4 + 1200 * 4)
            b, g, r, a = f.read(4)
        # QColor 的入参是 RGB(24,26,32)，在内存里按 BGRA 排列就是 B=32,G=26,R=24
        self.assertEqual((b, g, r, a), (32, 26, 24, 255), "深色底应写成不透明 BGRA")

    def test_viewport_change_triggers_rerender(self):
        self.canvas.begin_stroke(100, 100, width=8)
        self.canvas.end_stroke()
        self.pub.publish()
        before = self.pub._cached_image
        self.canvas.set_viewport(50, 50, 1000, 700)
        self.pub.publish()
        self.assertIsNot(self.pub._cached_image, before, "移动视口也应重新渲染")


if __name__ == "__main__":
    unittest.main(verbosity=2)

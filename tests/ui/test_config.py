"""配置与虚拟摄像头生命周期测试。

运行：QT_QPA_PLATFORM=offscreen python tests/ui/test_config.py
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.camera_whiteboard.config import DEFAULT_CLSID, DEFAULT_DEVICE_NAME, load_config  # noqa: E402
from ui.camera_whiteboard.virtualcam import SAMPLE_CLSID, VirtualCamera  # noqa: E402


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "app.json")

    def tearDown(self):
        os.environ.pop("CWB_CONFIG", None)
        self.tmp.cleanup()

    def _write(self, payload):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

    def test_reads_device_name_and_clsid(self):
        self._write({"mediaSourceClsid": "{11111111-2222-3333-4444-555555555555}",
                     "deviceName": "我的白板"})
        os.environ["CWB_CONFIG"] = self.path
        cfg = load_config()
        self.assertEqual(cfg.device_name, "我的白板")
        self.assertEqual(cfg.media_source_clsid, "{11111111-2222-3333-4444-555555555555}")

    def test_missing_file_falls_back_to_defaults(self):
        os.environ["CWB_CONFIG"] = os.path.join(self.tmp.name, "nope.json")
        cfg = load_config()
        self.assertEqual(cfg.device_name, DEFAULT_DEVICE_NAME)
        self.assertEqual(cfg.media_source_clsid, DEFAULT_CLSID)

    def test_broken_json_falls_back_to_defaults(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ not json")
        os.environ["CWB_CONFIG"] = self.path
        cfg = load_config()
        self.assertEqual(cfg.device_name, DEFAULT_DEVICE_NAME)

    def test_repo_config_has_product_identity(self):
        """仓库自带的 config/app.json 应该是产品身份，不是样例。"""
        os.environ.pop("CWB_CONFIG", None)
        cfg = load_config()
        self.assertNotEqual(cfg.device_name, "VCamSample")
        self.assertNotEqual(cfg.media_source_clsid.lower(), SAMPLE_CLSID.lower())


class FallbackTests(unittest.TestCase):
    """产品 CLSID 没注册时要自动退回样例 CLSID，而不是直接不可用。"""

    def test_falls_back_to_sample_clsid(self):
        cam = VirtualCamera("摄像头1", "{11111111-2222-3333-4444-555555555555}")
        calls = []

        def fake_start():
            calls.append(cam.clsid)
            return cam.clsid.lower() == SAMPLE_CLSID.lower()

        cam.start = fake_start  # type: ignore[method-assign]
        self.assertTrue(cam.start_with_fallback())
        self.assertEqual(len(calls), 2, "应该先试配置的 CLSID，再试样例 CLSID")
        self.assertEqual(cam.clsid.lower(), SAMPLE_CLSID.lower())
        self.assertIn("sample CLSID fallback", cam.last_error or "")

    def test_reports_failure_when_both_fail(self):
        cam = VirtualCamera("摄像头1", "{11111111-2222-3333-4444-555555555555}")
        cam.start = lambda: False  # type: ignore[method-assign]
        self.assertFalse(cam.start_with_fallback())
        self.assertIsNotNone(cam.last_error)

    def test_no_fallback_when_already_sample(self):
        cam = VirtualCamera("摄像头1", SAMPLE_CLSID)
        calls = []

        def fake_start():
            calls.append(1)
            return False

        cam.start = fake_start  # type: ignore[method-assign]
        self.assertFalse(cam.start_with_fallback())
        self.assertEqual(len(calls), 1, "已经用样例 CLSID 就不该重复尝试")


if __name__ == "__main__":
    unittest.main(verbosity=2)

import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ui.camera_whiteboard import bootstrap


class BundleCheckTests(unittest.TestCase):
    def test_bundle_check_loads_dependencies_without_registering_or_capturing(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'report.json'
            entry = Path(__file__).resolve().parents[2] / 'packaging/entry.py'
            outcome = None
            with patch.object(sys, 'argv', [str(entry), '--check-bundle', str(report)]), \
                 patch.object(bootstrap, 'start_virtual_camera', side_effect=AssertionError('must not register')), \
                 patch.object(bootstrap, 'claim_single_instance', return_value=True):
                try:
                    runpy.run_path(str(entry), run_name='__main__')
                except (SystemExit, AssertionError) as exc:
                    outcome = exc
            self.assertIsInstance(outcome, SystemExit, 'Dependency check must bypass normal camera startup')
            self.assertEqual(outcome.code, 0)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(data['ok'])
            self.assertIn('native_factory', data)
            self.assertIn('ffmpeg', data)


if __name__ == '__main__':
    unittest.main()

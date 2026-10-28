import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXPORTER = Path(__file__).resolve().parents[2] / 'scripts/export_release.py'


class ReleaseExportTests(unittest.TestCase):
    def test_export_contains_source_and_app_without_developer_caches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'repo'
            files = {
                'README.md': 'source readme', 'LICENSE': 'project license',
                'ui/app.py': 'print(1)', '.venv/private.txt': 'private',
                '.run/frames.bin': 'private frame', '.git/config': 'private remote',
                'third_party/vcamsample/packages/cache.bin': 'cache',
                'third_party/vcamsample/LICENSE': 'upstream license',
                'third_party/vcamsample/x64/Release/VCamSampleSource.dll': 'native dll',
                'packaging/install.ps1': 'installer', 'packaging/uninstall.ps1': 'uninstaller',
                'packaging/USER_GUIDE.md': 'guide', 'config/app.json': '{}',
                'packaging/dist/CameraWhiteboard/CameraWhiteboard.exe': 'application',
                'packaging/dist/CameraWhiteboard/_internal/python313.dll': 'runtime',
                'packaging/licenses/NOTICE.txt': 'notices',
            }
            for name, value in files.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(value, encoding='utf-8')
            out = Path(folder) / 'bundle'
            result = subprocess.run([sys.executable, str(EXPORTER), '--root', str(root),
                                     '--output', str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / 'source/ui/app.py').is_file())
            self.assertFalse((out / 'source/.venv').exists())
            self.assertFalse((out / 'source/.run').exists())
            self.assertFalse((out / 'source/.git').exists())
            self.assertFalse((out / 'source/third_party/vcamsample/packages').exists())
            self.assertTrue((out / 'app/CameraWhiteboard.exe').is_file())
            self.assertTrue((out / 'app/native/CameraWhiteboardSource.dll').is_file())
            self.assertTrue((out / 'app/_internal/python313.dll').is_file())
            self.assertTrue((out / 'SHA256SUMS.txt').is_file())

    def test_missing_native_binary_fails_before_creating_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / 'bundle'
            result = subprocess.run([sys.executable, str(EXPORTER), '--root', str(root),
                                     '--output', str(out)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()

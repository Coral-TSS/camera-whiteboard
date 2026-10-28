import ctypes
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from ui.camera_whiteboard import paths


class DistributionTests(unittest.TestCase):
    def test_frozen_app_does_not_discover_developer_run_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.run').mkdir()
            app_dir = root / 'application'
            app_dir.mkdir()
            with patch.object(paths.sys, 'frozen', True, create=True), \
                 patch.object(paths.sys, 'executable', str(app_dir / 'CameraWhiteboard.exe')), \
                 patch.dict(os.environ, {'ProgramData': str(root / 'data'), 'CWB_FRAME_FILE': ''}):
                self.assertEqual(paths.frames_path(), root / 'data' / 'CameraWhiteboard' / 'frames.bin')

    def test_native_dll_accepts_product_clsid_without_sample_registration(self):
        dll_path = Path(__file__).resolve().parents[2] / 'third_party/vcamsample/x64/Release/VCamSampleSource.dll'
        self.assertTrue(dll_path.exists(), 'Build the native source before release tests')
        dll = ctypes.WinDLL(str(dll_path))
        clsid = ctypes.create_string_buffer(uuid.UUID('2B28F238-082E-4FE4-8142-3141306593D0').bytes_le)
        iid = ctypes.create_string_buffer(uuid.UUID('00000001-0000-0000-C000-000000000046').bytes_le)
        factory = ctypes.c_void_p()
        get_factory = dll.DllGetClassObject
        get_factory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        get_factory.restype = ctypes.c_long
        result = get_factory(clsid, iid, ctypes.byref(factory))
        self.assertEqual(result & 0xffffffff, 0, 'Product CLSID must activate without sample fallback')
        if factory.value:
            table = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(factory)


if __name__ == '__main__':
    unittest.main()

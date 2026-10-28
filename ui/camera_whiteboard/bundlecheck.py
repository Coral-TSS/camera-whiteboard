"""Read-only bundle smoke check: no camera capture or device registration."""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import uuid
from pathlib import Path


def check_bundle(report_path: str) -> int:
    result = {'ok': False, 'python': sys.version, 'frozen': bool(getattr(sys, 'frozen', False))}
    try:
        import cv2
        import numpy
        import imageio_ffmpeg
        from PySide6 import __version__ as qt_version
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        from . import i18n
        from .config import load_config
        config = load_config()
        result['language'] = i18n.set_language(config.language)
        result['device_name'] = config.device_name
        result['position_menu'] = i18n.t('menu.position')
        from .canvas import Canvas
        from .compositor import Compositor

        result.update(qt=qt_version, opencv=cv2.__version__, numpy=numpy.__version__)
        app = QApplication.instance() or QApplication([])
        result['platform_plugin'] = app.platformName()
        image = QImage(20, 20, QImage.Format.Format_RGB888)
        image.fill(QColor(20, 100, 180))
        compositor = Compositor(Canvas((0, 0, 400, 300)), 1280, 720)
        output = compositor.frame(image)
        before = compositor.panel_rect()
        compositor.set_board_mirror(True)
        after = compositor.panel_rect()
        if after.x() != 1280 - before.x() - before.width():
            raise RuntimeError('Board-only reflection check failed')
        compositor.set_panel_visible(False)
        reflected_camera = compositor.frame(image)
        compositor.set_board_mirror(False)
        if compositor.frame(image) != reflected_camera:
            raise RuntimeError('Board mirror changed the hidden-board camera image')
        result['board_mirror_control'] = 'Mirror board position + strokes'
        if output.isNull() or output.size().width() != 1280 or output.size().height() != 720:
            raise RuntimeError('Qt compositor output failed')
        result['output'] = [output.width(), output.height()]
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        proc = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True, timeout=10,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if proc.returncode:
            raise RuntimeError('Bundled FFmpeg failed to run')
        result['ffmpeg'] = proc.stdout.splitlines()[0]
        if getattr(sys, 'frozen', False):
            dll_path = Path(sys.executable).parent / 'native/CameraWhiteboardSource.dll'
        else:
            dll_path = Path(__file__).resolve().parents[2] / 'third_party/vcamsample/x64/Release/VCamSampleSource.dll'
        dll = ctypes.WinDLL(str(dll_path))
        clsid = ctypes.create_string_buffer(uuid.UUID('2B28F238-082E-4FE4-8142-3141306593D0').bytes_le)
        iid = ctypes.create_string_buffer(uuid.UUID('00000001-0000-0000-C000-000000000046').bytes_le)
        factory = ctypes.c_void_p()
        get_factory = dll.DllGetClassObject
        get_factory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        get_factory.restype = ctypes.c_long
        hr = get_factory(clsid, iid, ctypes.byref(factory))
        if hr < 0 or not factory.value:
            raise RuntimeError(f'Product factory failed: {hr & 0xffffffff:08X}')
        table = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(factory)
        result['native_factory'] = 'product CLSID accepted'
        result['ok'] = True
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    Path(report_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1

"""English defaults and real menus must work without cameras or registration."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from ui.camera_whiteboard import i18n
from ui.camera_whiteboard.app import WhiteboardApp
from ui.camera_whiteboard.canvas import Canvas
from ui.camera_whiteboard.compositor import Compositor
from ui.camera_whiteboard.config import AppConfig, load_config
from ui.camera_whiteboard.overlay import BrushSettings
from ui.camera_whiteboard.viewport import ViewportWindow
from ui.camera_whiteboard.virtualcam import VirtualCamera

app = QApplication.instance() or QApplication([])


def action_texts(menu):
    for action in menu.actions():
        yield action.text()
        if action.menu():
            yield from action_texts(action.menu())


class EnglishTests(unittest.TestCase):
    def test_missing_config_defaults_to_english_camera_name(self):
        with patch.dict(os.environ, {'CWB_CONFIG': 'nonexistent-english-config.json'}):
            cfg = load_config()
        self.assertEqual(cfg.language, 'en')
        self.assertEqual(cfg.device_name, 'Camera Whiteboard')
        self.assertEqual(i18n.set_language(None), 'en')
        self.assertEqual(i18n.t('tray.quit'), 'Quit')

    def test_broken_config_defaults_to_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            p.write_text('{broken', encoding='utf-8')
            with patch.dict(os.environ, {'CWB_CONFIG': str(p)}):
                self.assertEqual(load_config().language, 'en')

    def test_tray_and_board_menus_are_english(self):
        i18n.set_language('en')
        board = WhiteboardApp.__new__(WhiteboardApp)
        board.app = app
        board.canvas = Canvas((0, 0, 640, 480))
        board.brush = BrushSettings()
        board.viewport = ViewportWindow(board.canvas, board.brush)
        board.compositor = Compositor(board.canvas)
        board.publisher = SimpleNamespace(_bg_dirty=False)
        board.camera_overlay = True
        board._camera_yielded = False
        board.background_white = True
        board.config = AppConfig()
        board.vcam_ok = False
        board.vcam = SimpleNamespace(last_error='Run Install.cmd first')
        board.output_ok = False
        board.output_error = 'Waiting for frames'
        try:
            board._setup_tray()
            tray = list(action_texts(board.tray.contextMenu()))
            menu = board._board_menu()
            labels = tray + list(action_texts(menu))
            self.assertIn('Mirror board position + strokes', tray)
            board_mirror = next(a for a in menu.actions() if a.text() == 'Mirror board position + strokes')
            before = board.compositor.panel_rect()
            board_mirror.trigger()
            self.assertNotEqual(board.compositor.panel_rect(), before)
            self.assertIn('Board position (remote view)', tray)
            self.assertIn('Top left', labels)
            self.assertIn('Bottom right', labels)
            for label in labels:
                self.assertFalse(any('\u4e00' <= ch <= '\u9fff' for ch in label), label)
        finally:
            if hasattr(board, 'tray'):
                board.tray.hide()
            board.viewport.close()

    def test_virtual_camera_failure_is_english(self):
        camera = VirtualCamera('Camera Whiteboard', '{00000000-0000-0000-0000-000000000000}')
        camera.start = lambda: False
        self.assertFalse(camera.start_with_fallback())
        self.assertFalse(any('\u4e00' <= c <= '\u9fff' for c in camera.last_error))


if __name__ == '__main__':
    unittest.main()

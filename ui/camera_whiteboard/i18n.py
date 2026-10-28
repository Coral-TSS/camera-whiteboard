"""English interface strings. Unknown or legacy language codes fall back to English."""

from __future__ import annotations

_EN = {
    "menu.tool": "Brush",
    "menu.color": "Color",
    "menu.width": "Width",
    "menu.undo": "Undo (Ctrl+Alt+F9)",
    "menu.clear": "Clear",
    "menu.position": "Board position (remote view)",
    "menu.size": "Board size",
    "menu.mirror": "Mirror strokes only (off by default)",
    "menu.board_mirror": "Mirror board position + strokes",
    "menu.overlay": "Overlay camera",
    "menu.yield": "Release camera (let other apps use it)",
    "menu.background": "White background (uncheck = transparent)",
    "menu.passthrough": "Click-through (mouse passes through)",
    "menu.safe_area": "Show safe-area frame (calibration)",
    "menu.close_board": "Close board",
    "tool.pen": "Pen",
    "tool.eraser": "Eraser",
    "color.red": "Red",
    "color.yellow": "Yellow",
    "color.green": "Green",
    "color.blue": "Blue",
    "color.black": "Black",
    "width.thin": "Thin",
    "width.medium": "Medium",
    "width.thick": "Thick",
    "size.small": "Small",
    "size.medium": "Medium",
    "size.large": "Large",
    "anchor.tl": "Top left", "anchor.tc": "Top center", "anchor.tr": "Top right",
    "anchor.cl": "Middle left", "anchor.c": "Center", "anchor.cr": "Middle right",
    "anchor.bl": "Bottom left", "anchor.bc": "Bottom center", "anchor.br": "Bottom right",
    "anchor.t1l": "Thirds top left", "anchor.t1r": "Thirds top right",
    "anchor.t2l": "Thirds bottom left", "anchor.t2r": "Thirds bottom right",
    "board.title_hint": "Drag the title bar to move · drag the bottom-right corner to resize · ✕ hides the board; video keeps streaming",
    "board.title_hint_passthrough": "Click-through on: the board ignores the mouse · Ctrl+Alt+F8 to restore",
    "board.menu_button": "Menu ☰",
    "tray.board": "Board",
    "tray.passthrough": "Toggle click-through",
    "tray.undo": "Undo",
    "tray.clear": "Clear",
    "tray.show_region": "Show board window",
    "tray.quit": "Quit",
    "tray.camera_on": "Camera Whiteboard — camera {w}x{h}",
    "tray.camera_off": "Camera Whiteboard — camera released",
    "tray.vcam_state": "Virtual camera: {name}",
    "tray.vcam_failed": "Virtual camera: not running ({error})",
    "tray.output_ok": "Output: streaming",
    "tray.output_failed": "Output: failed ({error})",
}

_TABLES = {"en": _EN}
_LANG = "en"


def set_language(code: str | None) -> str:
    global _LANG
    code = (code or "en").lower()
    _LANG = code if code in _TABLES else "en"
    return _LANG


def language() -> str:
    return _LANG


def t(key: str, **kwargs) -> str:
    table = _TABLES.get(_LANG, _EN)
    text = table.get(key) or _EN.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def anchor(key: str) -> str:
    return t(f"anchor.{key}")


_SIZE_KEYS = {"s": "small", "m": "medium", "l": "large"}


def size(key: str) -> str:
    return t(f"size.{_SIZE_KEYS.get(key, key)}")


def tool(key: str) -> str:
    return t(f"tool.{key}")


def color(key: str) -> str:
    return t(f"color.{key}")


def width(key: str) -> str:
    return t(f"width.{key}")

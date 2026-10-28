"""Windows 点击穿透（WS_EX_TRANSPARENT）。

只做一件事：给窗口加/去扩展样式。失败不抛异常，返回 bool 供界面提示。
"""

from __future__ import annotations

import ctypes
import sys

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def _user32():
    if sys.platform != "win32":
        return None
    return ctypes.WinDLL("user32", use_last_error=True)


def _get_style(hwnd: int) -> int:
    user32 = _user32()
    if not user32:
        return 0
    get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    get_long.restype = ctypes.c_longlong if getattr(user32, "GetWindowLongPtrW", None) else ctypes.c_long
    get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
    return int(get_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE))


def _set_style(hwnd: int, style: int) -> bool:
    user32 = _user32()
    if not user32:
        return False
    set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    set_long.restype = ctypes.c_longlong if getattr(user32, "SetWindowLongPtrW", None) else ctypes.c_long
    set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong if getattr(user32, "SetWindowLongPtrW", None) else ctypes.c_long]
    set_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE, style)
    return ctypes.get_last_error() == 0


def set_click_through(hwnd: int, enabled: bool) -> bool:
    """开启后鼠标事件穿透到下层窗口。"""
    if not hwnd:
        return False
    style = _get_style(hwnd)
    base = style | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if enabled:
        base |= WS_EX_TRANSPARENT
    else:
        base &= ~WS_EX_TRANSPARENT
    return _set_style(hwnd, base)


def is_click_through(hwnd: int) -> bool:
    return bool(_get_style(hwnd) & WS_EX_TRANSPARENT)

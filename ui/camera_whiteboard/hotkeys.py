"""全局快捷键。用 RegisterHotKey + 独立消息循环线程，不依赖 Qt 原生事件过滤器。

线程里收到 WM_HOTKEY 后通过 Qt 信号（队列连接）回到主线程，避免跨线程直接操作界面。
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

VK_F8 = 0x77
VK_F9 = 0x78
VK_Z = 0x5A


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class HotkeyBridge(QObject):
    """把线程里的按键事件转成 Qt 信号。"""

    triggered = Signal(str)


class GlobalHotkeys:
    """注册若干组合键；回调在主线程执行。"""

    def __init__(self) -> None:
        self.bridge = HotkeyBridge()
        self._threads: list[threading.Thread] = []
        self._ready = False
        self._register_result: dict[str, bool] = {}

    def register(self, name: str, modifiers: int, vk: int) -> bool:
        if sys.platform != "win32":
            return False

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        result: dict[str, bool] = {}
        ready = threading.Event()

        def worker() -> None:
            hotkey_id = abs(hash(name)) % 0xBFFF + 1
            ok = bool(user32.RegisterHotKey(None, hotkey_id, modifiers, vk))
            result["ok"] = ok
            self._register_result[name] = ok
            ready.set()
            if not ok:
                return
            msg = _MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    self.bridge.triggered.emit(name)
            user32.UnregisterHotKey(None, hotkey_id)

        thread = threading.Thread(target=worker, name=f"hotkey-{name}", daemon=True)
        thread.start()
        ready.wait(1.0)  # 只等注册结果，不等消息循环结束
        self._threads.append(thread)
        return result.get("ok", False)

    @property
    def registered(self) -> dict[str, bool]:
        return dict(self._register_result)

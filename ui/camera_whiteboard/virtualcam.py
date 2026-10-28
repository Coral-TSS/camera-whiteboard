"""虚拟摄像头的生命周期：创建 / 启动 / 停止 / 移除。

为什么应用要自己创建：Windows 11 的虚拟摄像头是"谁创建、谁持有"——
设备显示名是 `MFCreateVirtualCamera` 的入参，不是 DLL 里的常量。
应用不创建的话，会议室里看到的设备名取决于上一次是谁把它建起来的（早期脚本测试
留下的是样例名 `VCamSample`）。

所以正式形态：**应用启动时按 config/app.json 创建并 Start，退出时 Stop + Remove**。
"""

from __future__ import annotations

import ctypes
from ctypes import POINTER, byref, c_long, c_ulong, c_void_p, c_wchar_p

# 与媒体源 DLL 里的 vtable 槽位一致（见 specs/windows11/ 的实测记录）
SLOT_START = 36
SLOT_STOP = 37
SLOT_REMOVE = 38

MFSTARTUP_VERSION = 0x00020070

SAMPLE_CLSID = "{3CAD447D-F283-4AF4-A3B2-6F5363309F52}"


def _hr(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"


def _ok(value: int) -> bool:
    return (value & 0x80000000) == 0


def _method(ptr: int, slot: int, restype, argtypes: list):
    """取 vtable 槽位上的方法，调用时不用再传 this。

    注意：接口指针指向的是"指向 vtable 的指针"，必须先解引用一次，
    直接做 ptr + slot*8 是错的（会访问到非法地址）。
    """
    vtable = ctypes.cast(ptr, POINTER(c_void_p))[0]
    addr = ctypes.cast(vtable, POINTER(c_void_p))[slot]
    raw = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(addr)
    return lambda *args: raw(ptr, *args)


class VirtualCamera:
    def __init__(self, device_name: str, clsid: str = SAMPLE_CLSID) -> None:
        self.device_name = device_name
        self.clsid = clsid
        self._vcam = c_void_p()
        self._mf_started = False
        self.last_error: str | None = None

    # ---- 生命周期 ----

    def start(self) -> bool:
        ole32 = ctypes.WinDLL("ole32")
        mfplat = ctypes.WinDLL("mfplat")
        try:
            sensor = ctypes.WinDLL("mfsensorgroup")
        except OSError:
            self.last_error = "Virtual cameras are unavailable: mfsensorgroup.dll is missing"
            return False

        ole32.CoInitializeEx.restype = c_long
        ole32.CoInitializeEx.argtypes = [c_void_p, c_ulong]
        ole32.CoInitializeEx(None, 0)

        mfplat.MFStartup.restype = c_long
        mfplat.MFStartup.argtypes = [c_ulong, c_ulong]
        if not _ok(mfplat.MFStartup(MFSTARTUP_VERSION, 0)):
            self.last_error = "MFStartup failed"
            return False
        self._mf_started = True

        sensor.MFCreateVirtualCamera.restype = c_long
        sensor.MFCreateVirtualCamera.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, c_wchar_p, c_wchar_p,
            c_void_p, c_ulong, POINTER(c_void_p),
        ]
        r = sensor.MFCreateVirtualCamera(0, 0, 0, self.device_name, self.clsid, None, 0,
                                         byref(self._vcam))
        if not _ok(r) or not self._vcam.value:
            self.last_error = f"MFCreateVirtualCamera failed: {_hr(r)} (run Install.cmd to register the media source)"
            return False

        # IMFVirtualCamera::Start(IMFAsyncCallback*, IUnknown*) —— 传空表示同步启动
        fn = _method(self._vcam.value, SLOT_START, c_long, [c_void_p, c_void_p])
        r = fn(None, None)
        if not _ok(r):
            self.last_error = f"Virtual camera startup failed: {_hr(r)}"
            self._vcam = c_void_p()
            return False
        return True

    def stop(self) -> None:
        if not self._vcam.value:
            return
        try:
            fn = _method(self._vcam.value, SLOT_STOP, c_long, [])
            fn()
        except Exception:  # noqa: BLE001
            pass
        try:
            fn = _method(self._vcam.value, SLOT_REMOVE, c_long, [])
            fn()
        except Exception:  # noqa: BLE001
            pass
        self._vcam = c_void_p()

    @property
    def is_running(self) -> bool:
        return bool(self._vcam.value)

    # ---- 供上层调用 ----

    def start_with_fallback(self) -> bool:
        """产品 CLSID 没注册时退回样例 CLSID，保证能用。"""
        if self.start():
            return True
        first_error = self.last_error
        if self.clsid.lower() != SAMPLE_CLSID.lower():
            self.clsid = SAMPLE_CLSID
            if self.start():
                self.last_error = f"{first_error}; using the sample CLSID fallback"
                return True
        self.last_error = f"{first_error}; the sample CLSID fallback also failed" if first_error else "Startup failed"
        return False

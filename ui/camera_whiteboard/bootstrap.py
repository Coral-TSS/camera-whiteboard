"""早期启动：在导入 PySide6/cv2 之前把虚拟摄像头建好。

打包成 exe 后，加载 Qt 和 opencv 要好几秒。如果等界面起来再建摄像头，
用户双击后要在会议里等很久才看得到「摄像头1」。这里只用标准库 + ctypes，
几百毫秒就能把设备挂上去。
"""

from __future__ import annotations

import ctypes

from .config import load_config
from .log import log, set_log_path
from .paths import log_path
from .virtualcam import VirtualCamera


_INSTANCE_HANDLE: list[int] = []


def claim_single_instance() -> bool:
    """只允许一个实例：两个实例会抢同一个虚拟摄像头/物理摄像头，画面会黑或闪。"""
    try:
        kernel32 = ctypes.WinDLL("kernel32")
        handle = kernel32.CreateMutexW(None, False, "Global\\CameraWhiteboard.SingleInstance")
        already = kernel32.GetLastError() == 183   # ERROR_ALREADY_EXISTS
        if handle:
            _INSTANCE_HANDLE.append(handle)
        return not already
    except OSError:
        return True


def start_virtual_camera() -> tuple[VirtualCamera, bool]:
    set_log_path(log_path())
    config = load_config()
    vcam = VirtualCamera(config.device_name, config.media_source_clsid)
    ok = vcam.start_with_fallback()
    if ok:
        log(f"[vcam] Started {config.device_name} (CLSID {vcam.clsid})"
            + (f"; {vcam.last_error}" if vcam.last_error else ""))
    else:
        log(f"[vcam] Startup failed: {vcam.last_error}")
    return vcam, ok

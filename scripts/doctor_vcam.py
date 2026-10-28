"""虚拟摄像头诊断探针（P0 临时工具，后续并入 native/manager 的 doctor）。

用 ctypes 依次执行 CoInitializeEx -> MFStartup -> MFCreateVirtualCamera -> Start -> Remove，
把每一步的 HRESULT 打印出来。不改系统状态，结束时移除创建的设备。

用法：
    .venv\\Scripts\\python.exe scripts\\doctor_vcam.py
    .venv\\Scripts\\python.exe scripts\\doctor_vcam.py --duration 20   # 保持设备存在 20 秒，便于观察
"""

import argparse
import ctypes
import time
from ctypes import POINTER, byref, c_long, c_ulong, c_void_p, c_wchar_p

MF_VERSION = 0x00020070
COINIT_APARTMENTTHREADED = 0x2

MFVirtualCameraType_SoftwareCameraSource = 0
MFVirtualCameraLifetime_Session = 0
MFVirtualCameraAccess_CurrentUser = 0

# IMFVirtualCamera 继承 IMFAttributes（不是 IUnknown），槽位由 mfvirtualcamera.h 数出：
# 0 QueryInterface / 33 AddDeviceSourceInfo / 36 Start / 37 Stop / 38 Remove / 43 Shutdown
SLOT_RELEASE = 2
SLOT_START = 36
SLOT_REMOVE = 38


def hr(code: int) -> str:
    code &= 0xFFFFFFFF
    return f"0x{code:08X}"


def hresult_ok(code: int) -> bool:
    return (code & 0x80000000) == 0


def fmt_message(code: int) -> str:
    code &= 0xFFFFFFFF
    buf = ctypes.create_unicode_buffer(512)
    n = ctypes.windll.kernel32.FormatMessageW(
        0x1000 | 0x200,  # FROM_SYSTEM | IGNORE_INSERTS
        None,
        code,
        0,
        buf,
        len(buf),
        None,
    )
    text = buf.value.strip() if n else ""
    return text or "(无系统消息)"


def call_vtable(ptr: int, slot: int, restype, argtypes, *args):
    vtable = ctypes.cast(ptr, POINTER(c_void_p))[0]
    addr = ctypes.cast(vtable, POINTER(c_void_p))[slot]
    fn = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(addr)
    return fn(c_void_p(ptr), *args)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clsid", default="{3CAD447D-F283-4AF4-A3B2-6F5363309F52}",
                    help="媒体源 CLSID，默认用 VCamSample 样例")
    ap.add_argument("--name", default="诊断摄像头", help="设备显示名")
    ap.add_argument("--duration", type=int, default=0, help="创建成功后保持的秒数")
    args = ap.parse_args()

    ole32 = ctypes.WinDLL("ole32")
    mfplat = ctypes.WinDLL("mfplat")
    sensor = ctypes.WinDLL("mfsensorgroup")

    sensor.MFCreateVirtualCamera.restype = c_long
    sensor.MFCreateVirtualCamera.argtypes = [
        ctypes.c_int,        # type
        ctypes.c_int,        # lifetime
        ctypes.c_int,        # access
        c_wchar_p,           # friendlyName
        c_wchar_p,           # sourceId
        c_void_p,            # categories
        c_ulong,             # categoryCount
        POINTER(c_void_p),   # out
    ]
    mfplat.MFStartup.restype = c_long
    mfplat.MFStartup.argtypes = [c_ulong, c_ulong]
    mfplat.MFShutdown.restype = c_long
    ole32.CoInitializeEx.restype = c_long
    ole32.CoInitializeEx.argtypes = [c_void_p, c_ulong]
    ole32.CoUninitialize.restype = None

    print("== 1. CoInitializeEx ==")
    r = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    print(f"   {hr(r)} {fmt_message(r) if not hresult_ok(r) else 'OK'}")

    print("== 2. MFStartup ==")
    r = mfplat.MFStartup(MF_VERSION, 0)
    print(f"   {hr(r)} {fmt_message(r) if not hresult_ok(r) else 'OK'}")
    if not hresult_ok(r):
        return 1

    vcam = c_void_p()
    print("== 3. MFCreateVirtualCamera ==")
    print(f"   clsid={args.clsid}  name={args.name}  lifetime=Session  access=CurrentUser")
    r = sensor.MFCreateVirtualCamera(
        MFVirtualCameraType_SoftwareCameraSource,
        MFVirtualCameraLifetime_Session,
        MFVirtualCameraAccess_CurrentUser,
        args.name,
        args.clsid,
        None,
        0,
        byref(vcam),
    )
    print(f"   {hr(r)} {fmt_message(r) if not hresult_ok(r) else 'OK'}")
    if not hresult_ok(r):
        mfplat.MFShutdown()
        ole32.CoUninitialize()
        return 2

    print("== 4. IMFVirtualCamera::Start ==")
    try:
        r = call_vtable(vcam.value, SLOT_START, c_long, [c_void_p], None)
        print(f"   {hr(r)} {fmt_message(r) if not hresult_ok(r) else 'OK'}")
    except Exception as exc:  # noqa: BLE001
        print(f"   调用失败：{exc}")

    if args.duration:
        print(f"   设备保持 {args.duration} 秒，现在可以打开相机应用查看")
        time.sleep(args.duration)

    print("== 5. 清理 ==")
    try:
        r = call_vtable(vcam.value, SLOT_REMOVE, c_long, [])
        print(f"   Remove: {hr(r)}")
        call_vtable(vcam.value, SLOT_RELEASE, c_ulong, [])
        print("   Release: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"   清理失败：{exc}")

    mfplat.MFShutdown()
    ole32.CoUninitialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

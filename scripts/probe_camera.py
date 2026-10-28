"""物理摄像头采集探针：验证"能否在 Python 进程里抓真实摄像头"。

用于评估 P3（我的人 + 手上的笔迹）是否可行：
- 能否打开、协商到什么格式
- 连续取帧的实际帧率与单帧耗时
- --hold 指定秒数让设备保持打开，便于测"第二个进程能否同时打开"

用法：
    .venv\\Scripts\\python.exe scripts/probe_camera.py --frames 60
    .venv\\Scripts\\python.exe scripts/probe_camera.py --hold 15
"""

import argparse
import ctypes
import statistics
import struct
import sys
import time
from ctypes import POINTER, byref, c_long, c_longlong, c_ubyte, c_uint, c_ulong, c_ushort, c_void_p, c_wchar_p

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

from read_vcam import (  # noqa: E402  复用 vtable 与 GUID 工具
    FIRST_VIDEO_STREAM,
    GUID,
    MFVideoFormat_NV12,
    MFVideoFormat_RGB32,
    MFMediaType_Video,
    MF_MT_MAJOR_TYPE,
    MF_MT_SUBTYPE,
    MF_MT_FRAME_SIZE,
    SLOT_BUFFER_LOCK,
    SLOT_BUFFER_UNLOCK,
    SLOT_GETGUID,
    SLOT_GETUINT64,
    SLOT_SAMPLE_CONTTIGUOUS,
    SLOT_SR_GETCURRENTMEDIATYPE,
    SLOT_SR_READSAMPLE,
    SLOT_SR_SETCURRENTMEDIATYPE,
    guid,
    hr,
    method,
    ok,
    release,
    set_guid,
)

# 摄像头设备 KSCATEGORY_CAPTURE 接口 GUID
KSCAPTURE = "{E5323777-F976-4F5B-9B55-B94699C46E44}"
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = guid("C60AC5FE-252A-478F-A0EF-BC8FA5F7CAD3")
MFSourceType_Video = guid("8EA575ED-F080-4566-BA72-E6D0C7F1B0B7")
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK = guid("58F0AAD8-22BF-4F8A-BB3D-D2C4978C6E2F")
IID_IMFMediaSource = guid("279A808D-AEC7-40C8-9C6B-A6B492C78A66")
SLOT_SETSTRING = 25  # IMFAttributes::SetString（26 是 SetBlob，传字符串会崩）


def set_string(ptr: int, key: GUID, value: str) -> int:
    fn, self_ = method(ptr, SLOT_SETSTRING, c_long, [POINTER(GUID), c_wchar_p])
    return fn(self_, byref(key), value)


def symbolic_link(instance_id: str) -> str:
    """PnP 实例 ID -> MF 设备符号链接（大小写必须与设备接口名一致）。"""
    body = instance_id.replace("\\", "#")
    return f"\\\\?\\{body}#{KSCAPTURE}"


def discover_links() -> list[str]:
    """从注册表读真实的设备接口路径，避免自己拼大小写拼错。"""
    import winreg

    base = rf"SYSTEM\CurrentControlSet\Control\DeviceClasses\{KSCAPTURE}"
    out: list[str] = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
    except OSError:
        return out
    for i in range(winreg.QueryInfoKey(key)[0]):
        name = winreg.EnumKey(key, i)
        if name.startswith("##?#"):
            out.append("\\\\?\\" + name[4:])
    return out


def open_camera(link: str, prefer_rgb: bool = True):
    mfplat = ctypes.WinDLL("mfplat")
    mf = ctypes.WinDLL("mf")
    mfreadwrite = ctypes.WinDLL("mfreadwrite")

    atts = c_void_p()
    mfplat.MFCreateAttributes(byref(atts), 2)
    r = set_guid(atts.value, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE, MFSourceType_Video)
    r2 = set_string(atts.value, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK, link)
    print(f"  SetGUID={hr(r)} SetString={hr(r2)}")

    mf.MFCreateDeviceSourceActivate.restype = c_long
    mf.MFCreateDeviceSourceActivate.argtypes = [c_void_p, POINTER(c_void_p)]
    activate = c_void_p()
    r = mf.MFCreateDeviceSourceActivate(atts, byref(activate))
    print(f"  MFCreateDeviceSourceActivate = {hr(r)}")
    if not ok(r) or not activate.value:
        return None

    fn, self_ = method(activate.value, 33, c_long, [POINTER(GUID), POINTER(c_void_p)])  # ActivateObject
    source = c_void_p()
    r = fn(self_, byref(IID_IMFMediaSource), byref(source))
    print(f"  ActivateObject = {hr(r)}")
    if not ok(r):
        return None

    mfreadwrite.MFCreateSourceReaderFromMediaSource.restype = c_long
    mfreadwrite.MFCreateSourceReaderFromMediaSource.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]
    reader = c_void_p()
    r = mfreadwrite.MFCreateSourceReaderFromMediaSource(source, None, byref(reader))
    print(f"  MFCreateSourceReader = {hr(r)}")
    if not ok(r):
        return None

    mfplat.MFCreateMediaType.restype = c_long
    mfplat.MFCreateMediaType.argtypes = [POINTER(c_void_p)]
    mt = c_void_p()
    mfplat.MFCreateMediaType(byref(mt))
    set_guid(mt.value, MF_MT_MAJOR_TYPE, MFMediaType_Video)
    set_guid(mt.value, MF_MT_SUBTYPE, MFVideoFormat_RGB32 if prefer_rgb else MFVideoFormat_NV12)
    fn, self_ = method(reader.value, SLOT_SR_SETCURRENTMEDIATYPE, c_long, [c_ulong, c_void_p, c_void_p])
    r = fn(self_, c_ulong(FIRST_VIDEO_STREAM & 0xFFFFFFFF), None, mt)
    print(f"  SetCurrentMediaType({'RGB32' if prefer_rgb else 'NV12'}) = {hr(r)}")

    # 打印实际生效格式
    fnget, selfg = method(reader.value, SLOT_SR_GETCURRENTMEDIATYPE, c_long, [c_ulong, POINTER(c_void_p)])
    cur = c_void_p()
    if ok(fnget(selfg, c_ulong(FIRST_VIDEO_STREAM & 0xFFFFFFFF), byref(cur))) and cur.value:
        fng, selfng = method(cur.value, SLOT_GETGUID, c_long, [POINTER(GUID), POINTER(GUID)])
        sub = GUID()
        fng(selfng, byref(MF_MT_SUBTYPE), byref(sub))
        fn64, self64 = method(cur.value, SLOT_GETUINT64, c_long, [POINTER(GUID), POINTER(c_longlong)])
        size = c_longlong(0)
        fn64(self64, byref(MF_MT_FRAME_SIZE), byref(size))
        w, h = (size.value >> 32) & 0xFFFFFFFF, size.value & 0xFFFFFFFF
        name = {0x00000016: "RGB32", 0x3231564E: "NV12", 0x30323449: "I420", 0x47504A4D: "MJPEG"}.get(sub.Data1, f"0x{sub.Data1:08X}")
        print(f"  实际格式 = {name}  {w}x{h}")
        release(cur.value)

    return reader, source, activate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default=r"USB\VID_046D&PID_0825&MI_00\6&3B2D2E99&0&0000")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--hold", type=float, default=0.0, help="保持设备打开的秒数")
    ap.add_argument("--nv12", action="store_true")
    args = ap.parse_args()

    ole32 = ctypes.WinDLL("ole32")
    mfplat = ctypes.WinDLL("mfplat")
    ole32.CoInitializeEx(None, 0)
    mfplat.MFStartup.restype = c_long
    mfplat.MFStartup(0x00020070, 0)

    links = discover_links()
    if links:
        print("发现设备接口：")
        for item in links:
            print(f"  {item}")
        link = links[0]
    else:
        link = symbolic_link(args.instance)
    print(f"\n使用：{link}")
    print("打开设备：")
    opened = open_camera(link, prefer_rgb=not args.nv12)
    if not opened:
        print("打开失败")
        return 1
    reader, source, activate = opened

    actual = c_ulong(0)
    flags = c_ulong(0)
    ts = c_longlong(0)
    fnread, selfread = method(
        reader.value, SLOT_SR_READSAMPLE, c_long,
        [c_ulong, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(c_longlong), POINTER(c_void_p)],
    )

    stamps = []
    costs = []
    carried = 0.0
    t0 = time.perf_counter()
    while len(stamps) < args.frames and (time.perf_counter() - t0) < 30:
        sample = c_void_p()
        c0 = time.perf_counter()
        r = fnread(selfread, c_ulong(FIRST_VIDEO_STREAM & 0xFFFFFFFF), c_ulong(0),
                   byref(actual), byref(flags), byref(ts), byref(sample))
        carried += time.perf_counter() - c0
        if not ok(r) or not sample.value:
            break
        stamps.append(ts.value)

        # 摸一下像素（模拟合成时必然要做的拷贝）
        fnbuf, selfs = method(sample.value, SLOT_SAMPLE_CONTTIGUOUS, c_long, [POINTER(c_void_p)])
        buf = c_void_p()
        if ok(fnbuf(selfs, byref(buf))):
            fnlock, selfb = method(buf.value, SLOT_BUFFER_LOCK, c_long,
                                   [POINTER(c_void_p), POINTER(c_ulong), POINTER(c_ulong)])
            p = c_void_p()
            maxlen = c_ulong(0)
            curlen = c_ulong(0)
            if ok(fnlock(selfb, byref(p), byref(maxlen), byref(curlen))):
                _ = ctypes.string_at(p, curlen.value)
                fnunlock, selfu = method(buf.value, SLOT_BUFFER_UNLOCK, c_long, [])
                fnunlock(selfu)
            release(buf.value)
        release(sample.value)

    elapsed = time.perf_counter() - t0
    n = len(stamps)
    print("\n== 采集结果 ==")
    print(f"  帧数         : {n}")
    print(f"  耗时         : {elapsed:.2f} s")
    print(f"  实测帧率     : {n / elapsed:.2f} fps" if elapsed else "")
    print(f"  平均取帧阻塞 : {carried / n * 1000:.1f} ms/帧" if n else "")
    if n >= 2:
        span = (stamps[-1] - stamps[0]) / 1e7
        print(f"  时间戳跨度   : {span:.2f} s（平均间隔 {span / (n - 1) * 1000:.1f} ms）")

    if args.hold:
        print(f"\n保持设备打开 {args.hold}s，可在另一进程尝试同时打开…")
        time.sleep(args.hold)
        print("  保持结束")

    release(reader.value)
    release(source.value)
    release(activate.value)
    mfplat.MFShutdown()
    ole32.CoUninitialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""独立读取器：验证虚拟摄像头持续输出动态帧（P0.3 验收工具）。

流程：自己创建 Session 级虚拟摄像头 -> Start -> 通过 IMFVirtualCamera::GetMediaSource
拿到媒体源 -> IMFSourceReader 连续取帧 -> 统计帧数 / 时间戳单调性 / 内容变化 / 实际帧率
-> 移除设备。

说明：这条路径在**本进程内**直接读媒体源，验证的是帧生成与时序；Frame Server 的
跨进程链路已由腾讯会议实测覆盖（见 validation/p0.1-baseline.md）。
设备枚举接口 MFEnumDeviceSources 在本机返回 E_INVALIDARG，故不走枚举。

用法：
    .venv\\Scripts\\python.exe scripts\\read_vcam.py
    .venv\\Scripts\\python.exe scripts\\read_vcam.py --frames 300 --format nv12
"""

import argparse
import ctypes
import hashlib
import time
from ctypes import POINTER, byref, c_long, c_longlong, c_ubyte, c_uint, c_ulong, c_ushort, c_void_p, c_wchar_p

FIRST_VIDEO_STREAM = -4
MFSTARTUP_VERSION = 0x00020070
COINIT_MULTITHREADED = 0x0

SLOT_RELEASE = 2
SLOT_QUERYINTERFACE = 0

SLOT_SETGUID = 24          # IMFAttributes
SLOT_GETSTRINGLEN = 11
SLOT_GETSTRING = 12

SLOT_VCAM_GETMEDIASOURCE = 39
SLOT_VCAM_START = 36
SLOT_VCAM_REMOVE = 38

SLOT_SR_GETCURRENTMEDIATYPE = 6
SLOT_SR_SETCURRENTMEDIATYPE = 7
SLOT_SR_READSAMPLE = 9
SLOT_GETGUID = 10
SLOT_SAMPLE_CONTTIGUOUS = 41
SLOT_BUFFER_LOCK = 3
SLOT_BUFFER_UNLOCK = 4


class GUID(ctypes.Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", c_ulong)]


def guid(text: str) -> GUID:
    p = text.strip("{}").split("-")
    g = GUID(int(p[0], 16), int(p[1], 16), int(p[2], 16))
    tail = p[3] + p[4]
    for i in range(8):
        g.Data4[i] = int(tail[2 * i: 2 * i + 2], 16)
    return g


MFMediaType_Video = guid("73646976-0000-0010-8000-00AA00389B71")
MFVideoFormat_NV12 = guid("3231564E-0000-0010-8000-00AA00389B71")
MFVideoFormat_RGB32 = guid("00000016-0000-0010-8000-00AA00389B71")
MF_MT_MAJOR_TYPE = guid("48EBA18E-F8C9-4687-BF11-0A74C9F96A8F")
MF_MT_SUBTYPE = guid("F7E34C9A-42E8-4714-B74B-CB29D72C35E5")
MF_MT_FRAME_SIZE = guid("1652C33D-D6B2-4012-B834-72030849A37D")
SLOT_GETUINT64 = 8


def _save_png(raw: bytes, path: str, width: int, height: int) -> None:
    """把 BGRA 帧存成 PNG（用 PySide6，避免引入额外依赖）。"""
    from PySide6.QtGui import QImage
    img = QImage(raw, width, height, width * 4, QImage.Format.Format_ARGB32_Premultiplied)
    img.save(path)
    print(f"  首帧已保存：{path}  ({width}x{height})")
IID_IMFMediaSource = guid("279A808D-AEC7-40C8-9C6B-A6B492C78A66")


def hr(code: int) -> str:
    return f"0x{code & 0xFFFFFFFF:08X}"


def ok(code: int) -> bool:
    return (code & 0x80000000) == 0


def method(ptr: int, slot: int, restype, argtypes):
    vtable = ctypes.cast(ptr, POINTER(c_void_p))[0]
    addr = ctypes.cast(vtable, POINTER(c_void_p))[slot]
    return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(addr), c_void_p(ptr)


def release(ptr: int) -> None:
    fn, self_ = method(ptr, SLOT_RELEASE, c_ulong, [])
    fn(self_)


def set_guid(ptr: int, key: GUID, value: GUID) -> int:
    fn, self_ = method(ptr, SLOT_SETGUID, c_long, [POINTER(GUID), POINTER(GUID)])
    return fn(self_, byref(key), byref(value))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="读取器自测")
    ap.add_argument("--clsid", default="{3CAD447D-F283-4AF4-A3B2-6F5363309F52}")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--format", default="nv12", choices=["nv12", "rgb32"])
    ap.add_argument("--save-png", default=None, help="把第一帧存成 PNG，便于肉眼核对")
    args = ap.parse_args()

    ole32 = ctypes.WinDLL("ole32")
    mfplat = ctypes.WinDLL("mfplat")
    mfreadwrite = ctypes.WinDLL("mfreadwrite")
    sensor = ctypes.WinDLL("mfsensorgroup")

    ole32.CoInitializeEx.restype = c_long
    ole32.CoInitializeEx.argtypes = [c_void_p, c_ulong]
    ole32.CoInitializeEx(None, COINIT_MULTITHREADED)

    mfplat.MFStartup.restype = c_long
    mfplat.MFStartup.argtypes = [c_ulong, c_ulong]
    r = mfplat.MFStartup(MFSTARTUP_VERSION, 0)
    print(f"MFStartup                     : {hr(r)}")
    if not ok(r):
        return 1

    sensor.MFCreateVirtualCamera.restype = c_long
    sensor.MFCreateVirtualCamera.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, c_wchar_p, c_wchar_p,
        c_void_p, c_ulong, POINTER(c_void_p),
    ]
    vcam = c_void_p()
    r = sensor.MFCreateVirtualCamera(0, 0, 0, args.name, args.clsid, None, 0, byref(vcam))
    print(f"MFCreateVirtualCamera         : {hr(r)}")
    if not ok(r):
        return 2

    fn, self_ = method(vcam.value, SLOT_VCAM_START, c_long, [c_void_p])
    r = fn(self_, None)
    print(f"IMFVirtualCamera::Start       : {hr(r)}")
    if not ok(r):
        return 3

    fn, self_ = method(vcam.value, SLOT_VCAM_GETMEDIASOURCE, c_long, [POINTER(c_void_p)])
    source = c_void_p()
    r = fn(self_, byref(source))
    print(f"GetMediaSource                : {hr(r)}")
    if not ok(r):
        return 4

    mfreadwrite.MFCreateSourceReaderFromMediaSource.restype = c_long
    mfreadwrite.MFCreateSourceReaderFromMediaSource.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]
    reader = c_void_p()
    r = mfreadwrite.MFCreateSourceReaderFromMediaSource(source, None, byref(reader))
    print(f"MFCreateSourceReader          : {hr(r)}")
    if not ok(r):
        return 5

    mfplat.MFCreateMediaType.restype = c_long
    mfplat.MFCreateMediaType.argtypes = [POINTER(c_void_p)]
    mt = c_void_p()
    mfplat.MFCreateMediaType(byref(mt))
    set_guid(mt.value, MF_MT_MAJOR_TYPE, MFMediaType_Video)
    set_guid(mt.value, MF_MT_SUBTYPE, MFVideoFormat_NV12 if args.format == "nv12" else MFVideoFormat_RGB32)

    fn, self_ = method(reader.value, SLOT_SR_SETCURRENTMEDIATYPE, c_long, [c_ulong, c_void_p, c_void_p])
    r = fn(self_, c_ulong(FIRST_VIDEO_STREAM & 0xFFFFFFFF), None, mt)
    print(f"SetCurrentMediaType({args.format})   : {hr(r)}")
    if not ok(r):
        print("  指定格式被拒，改用媒体源的原生类型继续")

    # 打印当前实际生效的媒体类型，便于判定走的是 NV12 还是 RGB32
    width_val, height_val = 1280, 960
    fnget, selfg = method(reader.value, SLOT_SR_GETCURRENTMEDIATYPE, c_long, [c_ulong, POINTER(c_void_p)])
    current = c_void_p()
    if ok(fnget(selfg, c_ulong(FIRST_VIDEO_STREAM & 0xFFFFFFFF), byref(current))) and current.value:
        fng, selfng = method(current.value, SLOT_GETGUID, c_long, [POINTER(GUID), POINTER(GUID)])
        sub = GUID()
        if ok(fng(selfng, byref(MF_MT_SUBTYPE), byref(sub))):
            fourcc = bytes([(sub.Data1 >> (8 * i)) & 0xFF for i in (3, 2, 1, 0)]).decode("ascii", "replace")
            print(f"  实际子类型   : {sub.Data1:08X} ('{fourcc}')")
        fn64, self64 = method(current.value, SLOT_GETUINT64, c_long, [POINTER(GUID), POINTER(c_longlong)])
        size = c_longlong(0)
        if ok(fn64(self64, byref(MF_MT_FRAME_SIZE), byref(size))):
            width_val = (size.value >> 32) & 0xFFFFFFFF
            height_val = size.value & 0xFFFFFFFF
            print(f"  实际尺寸     : {width_val} x {height_val}")
        release(current.value)

    saved = False

    actual_index = c_ulong(0)
    flags = c_ulong(0)
    ts = c_longlong(0)
    fnread, selfread = method(
        reader.value, SLOT_SR_READSAMPLE, c_long,
        [c_ulong, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(c_longlong), POINTER(c_void_p)],
    )

    print(f"\n== 读取 {args.frames} 帧 ==")
    hashes = set()
    stamps = []
    non_mono = 0
    t0 = time.time()
    while len(stamps) < args.frames and (time.time() - t0) < args.timeout:
        actual_index.value = 0
        flags.value = 0
        ts.value = 0
        sample = c_void_p()
        r = fnread(selfread, c_ulong(FIRST_VIDEO_STREAM & 0xFFFFFFFF), c_ulong(0),
                   byref(actual_index), byref(flags), byref(ts), byref(sample))
        if not ok(r):
            print(f"  ReadSample: {hr(r)}")
            break
        if flags.value & 1:
            print("  流结束")
            break
        if not sample.value:
            continue

        if stamps and ts.value <= stamps[-1]:
            non_mono += 1
        stamps.append(ts.value)

        fnbuf, selfs = method(sample.value, SLOT_SAMPLE_CONTTIGUOUS, c_long, [POINTER(c_void_p)])
        buf = c_void_p()
        if ok(fnbuf(selfs, byref(buf))):
            fnlock, selfb = method(buf.value, SLOT_BUFFER_LOCK, c_long,
                                   [POINTER(c_void_p), POINTER(c_ulong), POINTER(c_ulong)])
            p = c_void_p()
            maxlen = c_ulong(0)
            curlen = c_ulong(0)
            if ok(fnlock(selfb, byref(p), byref(maxlen), byref(curlen))):
                raw = ctypes.string_at(p, curlen.value)
                hashes.add(hashlib.blake2b(raw, digest_size=8).hexdigest())
                if args.save_png and not saved:
                    _save_png(raw, args.save_png, width_val, height_val)
                    saved = True
                fnunlock, selfu = method(buf.value, SLOT_BUFFER_UNLOCK, c_long, [])
                fnunlock(selfu)
            release(buf.value)
        release(sample.value)

    elapsed = time.time() - t0
    n = len(stamps)
    print("\n== 结果 ==")
    print(f"  帧数         : {n}")
    print(f"  耗时         : {elapsed:.2f} s")
    print(f"  实测帧率     : {(n / elapsed) if elapsed else 0:.2f} fps")
    print(f"  不同画面数   : {len(hashes)}")
    print(f"  时间戳单调   : {'是' if non_mono == 0 else f'否（{non_mono} 次倒退或重复）'}")
    if n >= 2:
        span = (stamps[-1] - stamps[0]) / 1e7
        print(f"  时间戳跨度   : {span:.3f} s")
        print(f"  平均帧间隔   : {span / (n - 1) * 1000:.2f} ms")

    release(reader.value)
    release(source.value)
    fn, self_ = method(vcam.value, SLOT_VCAM_REMOVE, c_long, [])
    print(f"\n  Remove       : {hr(fn(self_))}")
    release(vcam.value)
    mfplat.MFShutdown()
    ole32.CoUninitialize()

    passed = n >= args.frames and non_mono == 0 and len(hashes) > 1
    print(f"  判定（>= {args.frames} 帧 且 时间戳单调 且 内容变化）: {'通过' if passed else '未通过'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

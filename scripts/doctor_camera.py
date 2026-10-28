"""摄像头体检：一眼看出"摄像头到底有没有画面、为什么"。

顺序排查这几件事，并给出结论：
1. 设备能不能打开
2. 协商到的分辨率和格式
3. 实际帧率与画面亮度（亮度 ~0 说明传感器没收到光，不是软件问题）
4. 当前有哪些常见程序可能占着摄像头

用法：
    .venv\\Scripts\\python.exe scripts/doctor_camera.py
"""

from __future__ import annotations

import statistics
import sys
import time

KNOWN_HOLDERS = [
    "wemeetapp", "WeChat", "Weixin", "Zoom", "Teams", "ms-teams",
    "WindowsCamera", "Camera", "obs64", "YouCam", "skype",
]


def holders() -> list[str]:
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        found: list[str] = []
        arr = (wintypes.DWORD * 4096)()
        need = wintypes.DWORD()
        if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(need)):
            return found
        PROCESS_QUERY_LIMITED = 0x1000
        for i in range(need.value // ctypes.sizeof(wintypes.DWORD)):
            pid = arr[i]
            h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
            if not h:
                continue
            try:
                size = wintypes.DWORD(260)
                buf = ctypes.create_unicode_buffer(260)
                if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    name = buf.value.rsplit("\\", 1)[-1].lower().replace(".exe", "")
                    if any(k.lower() in name for k in KNOWN_HOLDERS):
                        found.append(f"{buf.value.rsplit(chr(92), 1)[-1]} (pid {pid})")
            finally:
                k32.CloseHandle(h)
        return sorted(set(found))
    except Exception:  # noqa: BLE001
        return []


def main() -> int:
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("缺少 opencv-python-headless")
        return 1

    print("== 设备 ==")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    print(f"  能否打开 : {'是' if cap.isOpened() else '否'}")
    if not cap.isOpened():
        print("  结论：摄像头被占用或驱动异常。先退出会议软件，再不行重插 USB。")
        return 2

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    code = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    print(f"  分辨率   : {w}x{h}   格式 : {fourcc!r}")

    print("\n== 取帧（8 帧） ==")
    delays: list[float] = []
    brightness: list[float] = []
    for i in range(8):
        t0 = time.perf_counter()
        ok, frame = cap.read()
        delays.append(time.perf_counter() - t0)
        if not ok or frame is None:
            print(f"  第{i + 1}帧读取失败")
            continue
        b = float(np.mean(frame))
        brightness.append(b)
        print(f"  第{i + 1}帧: 阻塞 {delays[-1] * 1000:.0f} ms  亮度 {b:.1f}")
    cap.release()

    if not brightness:
        print("\n  结论：一帧都读不到。重插 USB 或换一个 USB 口。")
        return 3

    fps = 1.0 / statistics.median(delays) if delays else 0.0
    avg = statistics.mean(brightness)
    print("\n== 结论 ==")
    print(f"  帧率 {fps:.1f} fps   平均亮度 {avg:.1f}/255")

    if avg < 3:
        print("  画面是黑的：传感器几乎没收到光，或者设备卡死。")
        print("  按顺序排查：")
        print("   1) 镜头是否被盖子/贴纸挡住、是否正对墙面或桌面")
        print("   2) 是否有程序占着摄像头（见下）")
        print("   3) 以上都不是 → 设备可能卡死：拔插 USB；")
        print('      或管理员运行 pnputil /restart-device "USB\\VID_046D&PID_0825&MI_00\\6&3B2D2E99&0&0000"')
        print("      （进程被强杀后，驱动可能停在只出黑帧的状态）")
    elif fps < 10:
        print("  画面有内容但帧率过低：多半是光线偏暗，自动曝光把帧时间拉长了。")
        print("  → 提高环境亮度，或把摄像头朝向光源。")
    else:
        print(f"  摄像头正常：{fps:.1f} fps、亮度 {avg:.0f}/255，可以直接用。")

    print("\n== 多分辨率抽样（判断传感器是否活着） ==")
    readings: dict[str, list[float]] = {}
    import cv2 as _cv2
    import numpy as _np

    for (rw, rh) in [(160, 120), (320, 240)]:
        c2 = _cv2.VideoCapture(0, _cv2.CAP_DSHOW)
        if not c2.isOpened():
            continue
        c2.set(_cv2.CAP_PROP_FRAME_WIDTH, rw)
        c2.set(_cv2.CAP_PROP_FRAME_HEIGHT, rh)
        c2.set(_cv2.CAP_PROP_FPS, 30)
        vals: list[float] = []
        for _ in range(4):
            ok, f = c2.read()
            if ok and f is not None:
                vals.append(float(_np.mean(f)))
        c2.release()
        readings[f"{rw}x{rh}"] = vals
        print(f"  {rw}x{rh}: {[round(v, 2) for v in vals]}")

    alive = any(v > 10 for vals in readings.values() for v in vals)
    if avg < 3 and alive:
        print("  小分辨率能读到非零亮度 → 传感器是好的，问题在 USB 流/驱动层。")
        print("  → 拔插 USB（要真正断电，pnputil 重启不一定断 VBUS），或换一个 USB 口。")
    elif avg < 3:
        print("  各分辨率都读不到亮 → 镜头确实没进光，先检查遮挡与朝向。")

    found = holders()
    print("\n== 可能占用摄像头的程序 ==")
    print("  " + ("、".join(found) if found else "未发现常见占用者"))
    if found and avg < 3:
        print("  → 画面异常时，完全退出这些程序（托盘也要退），再跑一次本脚本。")
    elif found:
        print("  （当前画面正常，这些程序并未妨碍采集）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

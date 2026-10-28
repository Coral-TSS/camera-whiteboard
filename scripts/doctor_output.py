"""输出链路体检：一眼看出"黑屏"是哪一段的问题。

依次检查：
1. 共享帧文件是否新鲜（生产者还在写吗）
2. 虚拟摄像头能不能读出一帧，画面是黑/白/有内容
3. 物理摄像头此刻是否被我们占用（别的程序会打不开）

用法：
    应用开着，另开一个终端：  .venv\\Scripts\\python.exe scripts\\doctor_output.py
"""

from __future__ import annotations

import ctypes
import os
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES = os.path.join(ROOT, ".run", "frames.bin")
HEADER_BYTES = 64


def filetime_now() -> int:
    return int((time.time() + 11644473600) * 10_000_000)


def check_frames() -> bool:
    print("== 共享帧文件 ==")
    if not os.path.exists(FRAMES):
        print(f"  不存在：{FRAMES}（应用没在送帧）")
        return False
    size = os.path.getsize(FRAMES)
    with open(FRAMES, "rb") as f:
        head = f.read(HEADER_BYTES)
    fields = struct.unpack("<IIIIIIIIQQQII", head)
    magic, _ver, _hb, w, h, _stride, fmt, _ = fields[:8]
    seq, frame_id, stamp, state = fields[8], fields[9], fields[10], fields[11]
    age = (filetime_now() - stamp) / 1e7 if stamp else 9999
    print(f"  文件大小 : {size / 1024 / 1024:.1f} MB   尺寸 {w}x{h}  格式 {fmt}")
    print(f"  frameId  : {frame_id}   序号 {seq}（偶数表示已写完）  状态 {state}")
    print(f"  写入时间 : {age:.2f} 秒前")
    ok = age < 2.0 and state == 1 and w > 0
    print("  → " + ("新鲜，生产者在正常送帧" if ok else "已停滞：应用没在送帧（会议里会回落诊断图案）"))
    return ok


def app_running() -> bool:
    import subprocess

    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CameraWhiteboard.exe"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    return "CameraWhiteboard" in out


def check_vcam() -> None:
    print("\n== 虚拟摄像头读一帧 ==")
    if app_running():
        # 应用在跑时会独占物理摄像头，DShow 的设备索引会变，
        # 用索引探测很容易误报"打不开"，所以这里只做提示
        print("  应用正在运行：跳过直接探测（此时 DShow 索引会错位，探测结果不可信）")
        print("  要单独验证设备，先退出应用，再跑 read_vcam.py")
        return
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("  缺少 opencv")
        return
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("  打不开设备 0（可能被别的程序占用，或设备没创建）")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)
    ok, frame = cap.read()
    if not ok or frame is None:
        print("  读了但没帧")
        cap.release()
        return
    mean = float(np.mean(frame))
    center = frame[frame.shape[0] // 2, frame.shape[1] // 2]
    print(f"  尺寸 {frame.shape[1]}x{frame.shape[0]}   平均亮度 {mean:.1f}/255")
    print(f"  中心像素 B/G/R = {center[0]}/{center[1]}/{center[2]}")
    if mean < 6:
        print("  → 画面是黑的：媒体源没拿到有效帧，或上游在送黑帧")
    elif mean > 248:
        print("  → 画面全白：白板占满（正常，如果画布区域正好铺满）")
    else:
        print("  → 有内容，输出正常")
    cap.release()


def check_physical() -> None:
    """不去抢摄像头（会干扰会议），只看本应用是否在跑。"""
    print("\n== 物理摄像头占用情况 ==")
    import subprocess

    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CameraWhiteboard.exe"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    if "CameraWhiteboard" in out:
        print("  本应用在运行 → 物理摄像头正被它占用")
        print("  → 会议里如果选的是物理摄像头，画面会是黑的；请改选「摄像头1」，")
        print("    或在托盘勾「让出摄像头（其他程序可用）」")
    else:
        print("  本应用没在运行，物理摄像头应为空闲")


def main() -> int:
    print("输出链路体检\n")
    check_frames()
    check_vcam()
    check_physical()
    print("\n判读：")
    print("  · 共享帧不新鲜 → 应用侧没在送帧，看 .run/app.log")
    print("  · 共享帧新鲜但摄像头是黑的 → 媒体源 DLL 的问题（是否重建过？）")
    print("  · 会议里黑、这里正常 → 会议选中的不是「摄像头1」，可能选的是物理摄像头")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

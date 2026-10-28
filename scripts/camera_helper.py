"""摄像头采集助手（独立进程，可选）。

界面默认在进程内采集（ui/camera_whiteboard/camera.py）。本脚本提供一个
"采集放到独立进程"的备选：把画面写进 .run/camera.bin，界面侧按共享帧协议读取。
将来换成 C++ 采集时，也用同一个接口替换。

排查提示：光线很暗时摄像头会掉到 1 fps（自动曝光把帧时间拉到 1 秒，亮度接近 0），
看起来像后端或线程问题。先看帧亮度，再怀疑代码。

与界面之间的传输复用共享帧协议（序号锁 + FILETIME），只是换成摄像头帧：
    .run/camera.bin      64 字节头 + BGRA 像素

用法：
    .venv\\Scripts\\python.exe scripts/camera_helper.py --seconds 30
    .venv\\Scripts\\python.exe scripts/camera_helper.py            # 一直跑，Ctrl+C 结束
"""

from __future__ import annotations

import argparse
import mmap
import os
import struct
import sys
import time

MAGIC = 0x43425743  # 'CWBc'
HEADER_BYTES = 64
STATE_OK = 1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT, ".run", "camera.bin")


def filetime() -> int:
    return int((time.time() + 11644473600) * 10_000_000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--seconds", type=float, default=0.0, help="0 表示一直跑")
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--path", default=DEFAULT_PATH)
    args = ap.parse_args()

    import cv2

    cap = cv2.VideoCapture(args.index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("摄像头打不开", file=sys.stderr, flush=True)
        return 1
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or args.width
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or args.height
    stride = width * 4
    total = HEADER_BYTES + stride * height

    os.makedirs(os.path.dirname(args.path), exist_ok=True)
    if not os.path.exists(args.path) or os.path.getsize(args.path) != total:
        with open(args.path, "wb") as f:
            f.truncate(total)

    f = open(args.path, "r+b")
    m = mmap.mmap(f.fileno(), total)
    m[0:HEADER_BYTES] = struct.pack(
        "<IIIIIIIIQQQII", MAGIC, 1, HEADER_BYTES, width, height, stride, 0, 0, 0, 0, 0, 0, 0
    )

    print(f"采集 {width}x{height} -> {args.path}", flush=True)
    seq = 0
    frame_id = 0
    t0 = time.perf_counter()
    deadline = t0
    interval = 1.0 / args.fps if args.fps > 0 else 0.0
    try:
        while True:
            if args.seconds and (time.perf_counter() - t0) >= args.seconds:
                break
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            payload = rgba.tobytes()

            seq += 1
            struct.pack_into("<Q", m, 32, seq)
            m[HEADER_BYTES:HEADER_BYTES + len(payload)] = payload
            frame_id += 1
            struct.pack_into("<Q", m, 40, frame_id)
            struct.pack_into("<Q", m, 48, filetime())
            struct.pack_into("<I", m, 56, STATE_OK)
            seq += 1
            struct.pack_into("<Q", m, 32, seq)

            # 采集本身已是 30fps，只在明显超前时补睡，避免把 CPU 打满
            if interval:
                deadline += interval
                sleep = deadline - time.perf_counter()
                if sleep > 0.002:
                    time.sleep(sleep)
                elif sleep < -0.5:
                    deadline = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        m.close()
        f.close()
        cap.release()
        elapsed = time.perf_counter() - t0
        fps = frame_id / elapsed if elapsed else 0
        print(f"结束：{frame_id} 帧 / {elapsed:.1f}s = {fps:.1f} fps", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

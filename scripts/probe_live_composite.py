"""端到端原型：物理摄像头画面 + 白板笔迹 = 虚拟摄像头输出。

这是"我的人 + 手上的笔迹"的最小可行验证：
采集走 DirectShow（Python 进程，用户会话），合成本地完成，虚拟摄像头侧仍然只读共享帧。

用法：
    .venv\\Scripts\\python.exe scripts/probe_live_composite.py --seconds 20
"""

import argparse
import struct
import sys
import time

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = __file__.rsplit("\\", 2)[0]
sys.path.insert(0, ROOT)
sys.path.insert(0, __file__.rsplit("\\", 1)[0])

from shm_producer import HEADER_BYTES, MAGIC  # noqa: E402

OUT_W, OUT_H = 1280, 960


def filetime() -> int:
    return int((time.time() + 11644473600) * 10_000_000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--frames", type=int, default=0, help="只发这么多帧后退出")
    ap.add_argument("--w", type=int, default=640)
    ap.add_argument("--h", type=int, default=480)
    args = ap.parse_args()

    app = QApplication.instance() or QApplication([])  # noqa: F841

    from pathlib import Path

    from ui.camera_whiteboard.canvas import Canvas
    from ui.camera_whiteboard.render import render

    # 一条演示笔迹（真实场景由界面提供）
    canvas = Canvas((0, 0, OUT_W, OUT_H))
    canvas.begin_stroke(200, 500, color=(255, 40, 40, 255), width=14)
    for i in range(1, 40):
        t = i / 39
        canvas.add_point(200 + t * 800, 500 - (t * 6 % 1 - 0.5) * 160)
    canvas.end_stroke()

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("摄像头打不开")
        return 1
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.h)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print(f"摄像头 {int(cap.get(3))}x{int(cap.get(4))} -> 输出 {OUT_W}x{OUT_H}")
    for _ in range(5):
        cap.read()

    path = Path(__file__).resolve().parent.parent / ".run" / "frames.bin"
    total = HEADER_BYTES + OUT_W * 4 * OUT_H
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "r+b" if path.exists() else "w+b") as f:
        if path.stat().st_size != total:
            f.truncate(total)
    f = open(path, "r+b")
    import mmap

    m = mmap.mmap(f.fileno(), total)
    m[0:HEADER_BYTES] = struct.pack(
        "<IIIIIIIIQQQII", MAGIC, 1, HEADER_BYTES, OUT_W, OUT_H, OUT_W * 4, 0, 0, 0, 0, 0, 0, 0,
    )

    stroke_layer = render(canvas, OUT_W, OUT_H).scaled(OUT_W, OUT_H)

    seq = 0
    frame_id = 0
    t0 = time.perf_counter()
    sent = 0
    try:
        while True:
            if args.frames and sent >= args.frames:
                break
            if not args.frames and (time.perf_counter() - t0) >= args.seconds:
                break

            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            base = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)

            out = QImage(OUT_W, OUT_H, QImage.Format.Format_ARGB32_Premultiplied)
            painter = QPainter(out)
            # 等比铺满（摄像头 4:3、输出 4:3，不裁不拉伸）
            painter.drawImage(out.rect(), base)
            painter.drawImage(0, 0, stroke_layer)
            painter.end()

            seq += 1
            struct.pack_into("<Q", m, 32, seq)
            m[HEADER_BYTES:HEADER_BYTES + total - HEADER_BYTES] = out.constBits().tobytes()
            frame_id += 1
            struct.pack_into("<Q", m, 40, frame_id)
            struct.pack_into("<Q", m, 48, filetime())
            struct.pack_into("<I", m, 56, 1)
            seq += 1
            struct.pack_into("<Q", m, 32, seq)
            sent += 1
    finally:
        m.close()
        f.close()
        cap.release()

    el = time.perf_counter() - t0
    print(f"已合成 {sent} 帧，用时 {el:.1f}s，实际 {sent / el:.1f} fps" if el else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""可行性探测：物理摄像头采集 + 与笔迹合成，能否撑住 30fps。

回答"我的人 + 手上的笔迹"这个诉求的性能底线：
1. DirectShow 采集真实摄像头的帧率与单帧阻塞时间
2. 用 QPainter 把笔迹叠到摄像头画面上的耗时
3. 转成 BGRA(共享帧协议) 的耗时

用法：
    .venv\\Scripts\\python.exe scripts/probe_composite.py --size 1280x720 --frames 60
"""

import argparse
import statistics
import sys
import time

import cv2
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def open_capture(width: int, height: int, fps: int, fourcc: str = "MJPG"):
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None
    if fourcc:
        # 720p 以上不指定压缩格式，DShow 会走未压缩 YUY2，USB2 带宽不够直接掉到 7.5fps
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 只留最新帧，避免积压
    return cap


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--fourcc", default="MJPG", help="MJPG（默认）/ YUY2 / 空字符串表示不指定")
    args = ap.parse_args()
    width, height = (int(v) for v in args.size.split("x"))

    cap = open_capture(width, height, args.fps, args.fourcc)
    if cap is None:
        print("DirectShow 打不开摄像头")
        return 1
    real_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    real_fps = cap.get(cv2.CAP_PROP_FPS)
    code = int(cap.get(cv2.CAP_PROP_FOURCC))
    code_s = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    print(f"协商结果：{real_w}x{real_h} @ {real_fps:.0f} fps  格式 {code_s!r}")

    # 预热，DShow 首帧很慢
    for _ in range(5):
        cap.read()

    reads = []
    frames = []
    t0 = time.perf_counter()
    while len(reads) < args.frames:
        c0 = time.perf_counter()
        ok, frame = cap.read()
        reads.append(time.perf_counter() - c0)
        if not ok:
            break
        frames.append(frame)
    capture_elapsed = time.perf_counter() - t0
    cap.release()

    n = len(frames)
    if not n:
        print("没读到帧")
        return 2
    print("\n== 采集 ==")
    print(f"  帧数       : {n}")
    print(f"  总耗时     : {capture_elapsed:.2f} s")
    print(f"  实际帧率   : {n / capture_elapsed:.1f} fps")
    print(f"  读帧耗时   : 中位 {statistics.median(reads) * 1000:.1f} ms / 最大 {max(reads) * 1000:.1f} ms")
    print(f"  （读帧是阻塞等下一帧，说明采集节奏由摄像头决定）")

    # 合成：摄像头帧 + 一条笔迹，输出 BGRA
    sample = frames[-1]
    h, w = sample.shape[:2]

    paint_costs = []
    encode_costs = []
    for i in range(20):
        c0 = time.perf_counter()
        rgb = cv2.cvtColor(sample, cv2.COLOR_BGR2RGBA)
        image = QImage(rgb.data, w, h, w * 4, QImage.Format.Format_ARGB32)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(255, 60, 60, 255))
        pen.setWidthF(8.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # 模拟一条 40 点的笔迹
        pts = [QPoint(100 + j * 20, 200 + (j % 7) * 12) for j in range(40)]
        painter.drawPolyline(pts)
        painter.end()
        paint_costs.append(time.perf_counter() - c0)

        c1 = time.perf_counter()
        _ = image.constBits().tobytes()
        encode_costs.append(time.perf_counter() - c1)

    print("\n== 合成 + 编码（每帧） ==")
    print(f"  BGR->RGBA + 画 40 点笔迹 : 中位 {statistics.median(paint_costs) * 1000:.1f} ms")
    print(f"  取 BGRA 字节             : 中位 {statistics.median(encode_costs) * 1000:.1f} ms")
    total = statistics.median(paint_costs) + statistics.median(encode_costs)
    print(f"  合计                     : {total * 1000:.1f} ms  (30fps 预算 33.3 ms)")

    print("\n== 结论 ==")
    budget_ok = total < 0.033
    print(f"  合成链路 {'可以' if budget_ok else '超出'} 30fps 预算")
    print(f"  采集实际帧率 {n / capture_elapsed:.1f} fps，{'满足' if n / capture_elapsed >= 25 else '低于'} 30fps 需求")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

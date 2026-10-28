"""共享帧生产者（P1.2 验证用）。

把测试画面写入 .run/frames.bin，供媒体源侧读取。协议见 specs/windows11/frame-protocol.md。

用法：
    .venv\\Scripts\\python.exe scripts/shm_producer.py --seconds 10 --fps 30
"""

import argparse
import os
import struct
import time

MAGIC = 0x31425743  # 'CWB1'
HEADER_BYTES = 64
STATE_OK = 1

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(REPO_ROOT, ".run", "frames.bin")


def make_frame(width: int, height: int, stride: int, frame_id: int) -> bytearray:
    """明显的三段信息：整幅渐变底（证明不是纯色）、移动红竖条（证明是活流）、
    左上角大号绿块编码（证明每帧内容真的在变）。"""
    buf = bytearray(stride * height)

    # 背景：从深蓝到亮蓝的整幅渐变（BGRA），跨度足够大，压缩后也能看出
    for y in range(height):
        t = y / max(1, height - 1)
        b = int(70 + t * 150)
        g = int(35 + t * 120)
        r = int(45 - t * 30)
        row = bytes((b, g, r, 0xFF)) * width
        buf[y * stride: y * stride + width * 4] = row

    # 移动红竖条：宽度约 1/20，每帧推进 1/45 屏宽
    bar_w = max(8, width // 20)
    x0 = (frame_id * (width // 45)) % (width - bar_w)
    bar = bytes((30, 30, 230, 0xFF)) * bar_w
    for y in range(height // 6, height * 5 // 6):
        off = y * stride + x0 * 4
        buf[off: off + bar_w * 4] = bar

    # 左上角 4x4 绿色格子：底色常驻，点亮位编码 frame_id 低 16 位
    cell = 24
    dim = bytes((35, 70, 35, 0xFF)) * (cell - 4)
    lit = bytes((40, 240, 40, 0xFF)) * (cell - 4)
    for bit in range(16):
        cx = (bit % 4) * cell + 12
        cy = (bit // 4) * cell + 12
        block = lit if (frame_id & (1 << bit)) else dim
        for yy in range(cy, cy + cell - 4):
            off = yy * stride + cx * 4
            buf[off: off + (cell - 4) * 4] = block

    return buf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=960,
                    help="默认 960，与媒体源协商的 1280x960 一致；尺寸不符会被媒体源忽略")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--seconds", type=float, default=0.0, help="0 表示一直跑")
    ap.add_argument("--path", default=DEFAULT_PATH)
    args = ap.parse_args()

    stride = args.width * 4
    total = HEADER_BYTES + stride * args.height

    os.makedirs(os.path.dirname(args.path), exist_ok=True)
    if not os.path.exists(args.path):
        with open(args.path, "wb") as f:
            f.truncate(total)
    size = os.path.getsize(args.path)
    if size != total:
        raise SystemExit(f"文件大小不符：期望 {total}，实际 {size}（换分辨率请删除后重建）")

    import mmap

    with open(args.path, "r+b") as f:
        m = mmap.mmap(f.fileno(), total)
        try:
            # 头部只写一次（不参与序号锁）
            m[0:64] = struct.pack(
                "<IIIIIIIIQQQII",
                MAGIC, 1, HEADER_BYTES, args.width, args.height, stride, 0, 0,
                0, 0, 0, 0, 0,
            )

            print(f"生产到 {args.path}  {args.width}x{args.height} stride={stride} @ {args.fps}fps")
            t0 = time.perf_counter()
            frame_id = 0
            seq = 0
            deadline = t0
            try:
                while True:
                    if args.seconds and (time.perf_counter() - t0) >= args.seconds:
                        break

                    seq += 1
                    struct.pack_into("<Q", m, 32, seq)          # 奇数：写入中
                    frame = make_frame(args.width, args.height, stride, frame_id)
                    m[64:64 + len(frame)] = frame
                    struct.pack_into("<Q", m, 40, frame_id)
                    # 时间戳用 Windows FILETIME（1601 起的 100ns），消费者可与之直接比较
                    filetime = int((time.time() + 11644473600) * 10_000_000)
                    struct.pack_into("<Q", m, 48, filetime)
                    struct.pack_into("<I", m, 56, STATE_OK)
                    seq += 1
                    struct.pack_into("<Q", m, 32, seq)          # 偶数：稳定

                    frame_id += 1
                    deadline += 1.0 / args.fps
                    sleep = deadline - time.perf_counter()
                    if sleep > 0:
                        time.sleep(sleep)

                    if frame_id % 30 == 0:
                        el = time.perf_counter() - t0
                        print(f"  frame={frame_id}  {frame_id / el:.1f} fps", flush=True)
            except KeyboardInterrupt:
                pass
            print(f"结束，共写入 {frame_id} 帧")
        finally:
            m.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

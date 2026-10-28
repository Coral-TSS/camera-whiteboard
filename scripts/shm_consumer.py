"""共享帧消费者（P1.2 验证用）。

按 specs/windows11/frame-protocol.md 的序号锁从 .run/frames.bin 读帧，
统计帧率、撕裂次数、frameId 单调性。媒体源 DLL 侧将复用同一套判定逻辑。

用法：
    .venv\\Scripts\\python.exe scripts/shm_consumer.py --seconds 5
"""

import argparse
import hashlib
import mmap
import os
import struct
import time

MAGIC = 0x31425743
HEADER_BYTES = 64

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(REPO_ROOT, ".run", "frames.bin")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--path", default=DEFAULT_PATH)
    args = ap.parse_args()

    if not os.path.exists(args.path):
        raise SystemExit(f"找不到 {args.path}，先运行 scripts/shm_producer.py")

    with open(args.path, "rb") as f:
        size = os.path.getsize(args.path)
        m = mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ)

        magic, ver, hb, w, h, stride, fmt, _r0, _seq0, _fid0, _ts0, _st0, _r2 = \
            struct.unpack("<IIIIIIIIQQQII", m[0:64])
        if magic != MAGIC:
            raise SystemExit(f"magic 不符：0x{magic:08X}")
        print(f"头部：ver={ver} {w}x{h} stride={stride} format={fmt} headerBytes={hb}")
        payload = stride * h
        assert HEADER_BYTES + payload <= size, "文件小于头部声明的尺寸"

        print(f"读取 {args.seconds}s ...")
        t0 = time.perf_counter()
        last_frame = -1
        accepted = 0
        torn = 0
        skipped_odd = 0
        regressions = 0
        hashes = set()
        last_hash_check = 0.0
        intervals = []
        prev_ts = None

        while (time.perf_counter() - t0) < args.seconds:
            s1 = struct.unpack_from("<Q", m, 32)[0]
            if s1 & 1:
                skipped_odd += 1
                time.sleep(0)
                continue

            frame_id = struct.unpack_from("<Q", m, 40)[0]
            ts = struct.unpack_from("<Q", m, 48)[0]
            state = struct.unpack_from("<I", m, 56)[0]
            data = m[HEADER_BYTES: HEADER_BYTES + payload]

            s2 = struct.unpack_from("<Q", m, 32)[0]
            if s1 != s2:
                torn += 1
                continue

            if state != 1:
                continue

            if frame_id < last_frame:
                regressions += 1
            if frame_id != last_frame:
                accepted += 1
                last_frame = frame_id

                now = time.perf_counter()
                if now - last_hash_check > 0.1:
                    hashes.add(hashlib.blake2b(data, digest_size=8).hexdigest())
                    last_hash_check = now

                if prev_ts is not None and ts > prev_ts:
                    intervals.append((ts - prev_ts) / 1e4)  # 100ns -> ms
                prev_ts = ts

            time.sleep(0.001)

        el = time.perf_counter() - t0
        m.close()

    print("\n== 结果 ==")
    print(f"  接受帧数       : {accepted}")
    print(f"  实测帧率       : {accepted / el:.2f} fps")
    print(f"  撕裂帧（丢弃） : {torn}")
    print(f"  遇到写入中     : {skipped_odd}")
    print(f"  frameId 倒退   : {regressions}")
    print(f"  采样到不同画面 : {len(hashes)}")
    if intervals:
        avg = sum(intervals) / len(intervals)
        print(f"  平均帧间隔     : {avg:.2f} ms（{len(intervals)} 个样本）")
        print(f"  最小/最大间隔  : {min(intervals):.2f} / {max(intervals):.2f} ms")

    ok = accepted > 0 and regressions == 0 and len(hashes) > 1
    print(f"\n  判定（有帧 且 frameId 单调 且 内容变化）: {'通过' if ok else '未通过'}")
    print(f"  撕裂率（应力指标，可 >0）: {torn}/{accepted + torn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

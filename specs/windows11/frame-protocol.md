# 共享帧协议 v1

制定：2026-10-24。替代 plan.md 中"三槽 + 跨进程 mutex + 通知事件"的初稿。

## 为什么不用 Global 共享内存

2026-10-24 实测（未提权进程）：

| 操作 | 结果 |
|---|---|
| `CreateMutexW(..., "Global\\x")` | 成功 |
| `CreateFileMappingW(INVALID_HANDLE_VALUE, ..., "Global\\x")` | **失败，WinError 5（拒绝访问）** |
| 会话内命名文件映射 | 成功 |

即普通用户拿不到创建 Global 文件映射所需的权限。而 spec 禁止用 NULL DACL 或放权绕过的做法，
因此放弃"生产者建 Global 映射、媒体源按名字打开"的方案。

## 采用的方案：文件映射 + 序号锁

- **落盘文件**：`.run/frames.bin`（大小固定 `64 + stride*height`，约 3.5 MB @720p BGRA）。
- 生产者（UI/引擎）与消费者（媒体源 DLL）各自 `CreateFileMapping` 同一个**文件**，
  再 `MapViewOfFile` 同一段。两者不需要共享内核对象名，因此不受 Global 命名空间权限限制。
- **不需要 mutex / event**：用序号锁（seqlock）保证读到完整帧，跨进程不依赖任何内核对象。
- 代价：数据经过文件缓存（page cache），实际不落盘；Windows 可能在空闲时回写，可接受。

### 头部布局（小端，固定 64 字节）

| 偏移 | 大小 | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | magic | `'CWB1'` = `0x31425743` |
| 4 | 4 | version | 当前 1 |
| 8 | 4 | headerBytes | 固定 64 |
| 12 | 4 | width | |
| 16 | 4 | height | |
| 20 | 4 | stride | 每行字节数 |
| 24 | 4 | format | 0 = BGRA8 预乘 alpha |
| 28 | 4 | reserved | 0 |
| 32 | 8 | seq | 序号锁；偶数=稳定，奇数=写入中 |
| 40 | 8 | frameId | 单调递增，0 表示尚无帧 |
| 48 | 8 | timestamp | **Windows FILETIME**（1601 起的 100ns），消费者据此判断帧是否陈旧 |
| 56 | 4 | state | 0=无帧 1=有效 2=故障占位 |
| 60 | 4 | reserved2 | 0 |
| 64 | … | pixels | `stride * height` 字节 |

### 写方

```
seq += 1                     # 变奇数，读者开始退避
写 pixels
写 width/height/stride/format/frameId/timestamp/state
seq += 1                     # 变偶数，帧完整
```

### 读方

```
s1 = seq
若 s1 为奇数 → 放弃本次，用上一帧
拷出 pixels 与头部字段
s2 = seq
若 s1 != s2 → 本次读到撕裂帧，丢弃并重试或复用上一帧
否则接受
```

## 消费者（媒体源侧实现）

实现在 `third_party/vcamsample/VCamSampleSource/SharedFrameSource.{h,cpp}`，接入点是
`MediaStream::RequestSample`：先尝试共享帧，失败才调用原有的 `FrameGenerator` 生成诊断图案。

- **文件路径**按优先级探测：`CWB_FRAME_FILE` 环境变量 → DLL 所在目录逐级向上 6 层的
  `.run\frames.bin` → `%ProgramData%\CameraWhiteboard\frames.bin`。
- **尺寸必须匹配**：当前媒体源协商固定 `1280x960`（`NUM_IMAGE_COLS/ROWS`）。头部尺寸不符时不做
  缩放，直接回落诊断图案——宁可看不到白板，也不输出被拉伸的画面。
- **像素格式**：`RGB32` 直接按行拷贝（尊重目标 pitch）；`NV12` 复用现有 `RGB32ToNV12`。
- **故障策略**：`state != 1`、读到撕裂、文件消失、尺寸不符，任一情况都回落诊断图案。诊断图案
  自身带移动色块与递增帧号，不会被误认为"白板停在最后一帧"。

## 已知边界

- **内存序**：依赖 x64 的存储顺序（TSO）。Python 侧无法插入显式屏障；C++ 侧应在写 seq 时使用
  `std::atomic_thread_fence(std::memory_order_release)`，读时用 acquire。
- **不检测生产者崩溃**：`frameId` 停滞超过 2 秒即视为故障，由消费者输出占位帧（spec 要求）。
  注意：只用本地计时不够——新建的消费者实例没有历史，会把陈旧的最后一帧当新帧；必须同时比对
  头部 `timestamp`（FILETIME）与当前 `GetSystemTimeAsFileTime()`。
- **不跨用户共享**：文件 ACL 只授予当前用户与 `LOCAL SERVICE`（读），不放开 Everyone。
- **文件位置**在项目内 `.run/`，避免写到项目外；打包阶段再改到 `%ProgramData%`。

## 后续

- P1.2 剩余：媒体源 DLL 侧实现读取并接入 `MediaStream::Generate` 路径（当前由 `FrameGenerator` 生成诊断图案，作为无生产者时的兜底）。
- 协议字段冻结后不再改动；分辨率变化通过重建文件（新 generation）协商，不复用旧映射。

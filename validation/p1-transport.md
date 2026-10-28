# P1.1 / P1.2 传输层记录

执行日期：2026-10-24。

## P1.1 权限最小实验（尚未完成的替代方案：Global 命名共享内存）

未提权进程实测：

| 操作 | 结果 |
|---|---|
| `CreateMutexW(..., "Global\\CWB_probe_mutex")` | 成功 |
| `CreateFileMappingW(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, 4096, "Global\\...")` | **失败，WinError 5** |
| `CreateFileMappingW(..., "CWB_probe_map_local")`（会话内） | 成功 |

结论：普通用户无法创建 Global 文件映射，因此"生产者建 Global 映射、媒体源按名打开"不可行；
而 NULL DACL / 放开 Everyone 的做法被 spec 明确禁止，不采用。

**决定**：改用文件映射 + 序号锁（不需要任何命名内核对象），详见
[frame-protocol.md](../specs/windows11/frame-protocol.md)。

尚未验证：媒体源 DLL 在会议软件中被加载时的真实宿主进程与用户身份（`mfpmp.exe` 会话归属）。
该信息影响 ACL 的具体授予对象，需在 P1.2 C++ 侧落地时一并采集。

## P1.2 协议与生产者/消费者（Python 侧已完成）

实现：`scripts/shm_producer.py`、`scripts/shm_consumer.py`，共享文件 `.run/frames.bin`。

命令：

```
.venv\Scripts\python.exe scripts/shm_producer.py --seconds 9 --fps 30
.venv\Scripts\python.exe scripts/shm_consumer.py --seconds 5
```

实测（两个进程并发）：

| 指标 | 结果 |
|---|---|
| 头部 | ver=1，1280x720，stride=5120，format=0，headerBytes=64 |
| 接受帧数 | 150（5 秒） |
| 实测帧率 | 29.99 fps（生产者设定 30） |
| 平均帧间隔 | 33.33 ms（最小 31.39 / 最大 35.24） |
| frameId 倒退 | 0 |
| 采样到不同画面 | 41 种 |
| 序号锁拒绝的撕裂帧 | 57（约 27%） |
| 判定 | **通过** |

撕裂率 27% 的解释：Python 生产者逐行构造 3.5 MB 帧需要约 10 ms，写入窗口很长，消费者
（1 ms 轮询）大量撞在写入中。C++ 侧用单次 `memcpy` 写入，窗口会显著缩短；该数字是应力观察，
不是缺陷。

## 联调发现的问题（2026-10-24，已修）

**现象**：摄像头输出换成了生产者图案（蓝底 + 红竖条 + 左上绿块），但红竖条不动、渐变看不出来、
绿块看不到。

**抓帧核对**：用 `read_vcam.py --save-png` 把摄像头实际输出存成 PNG，确认内容确实来自生产者，
说明传输链路本身是通的。图案设计上的问题（渐变跨度过小、绿格 14px 太小）只影响观感。

**真实缺陷**：生产者退出后，共享文件里留着最后一帧且 `state=1`、`seq` 为偶数，看起来完全合法。
消费者没有判断"帧还新不新"，于是把最后一帧一直送出去——画面冻结。这正是 spec 里
"不能用旧帧误导"要防的情况。

**修复**：`SharedFrameSource::FillSample` 增加 frameId 停滞检测——`frameId` 超过 2 秒未变化即
视为生产者已停，返回失败并回落诊断图案（诊断图案自带移动色块与递增帧号，不会被误认为白板卡住）。

**顺带改进**：测试图案改为整幅深蓝→亮蓝渐变、左上角常驻 4×4 绿格（亮格编码 frameId 低 16 位）、
红竖条加宽到 1/20 屏宽并每帧推进 1/45 屏宽。

## 待办（P1.2 剩余）

1. C++ 侧接入后重新构建，验证"生产者写什么，摄像头就出什么"。（代码已完成，未构建）
2. 采集真实宿主进程与身份，确定 ACL 授予对象（当前未授予 `LOCAL SERVICE`）。
3. 分辨率变化用新 generation 重建文件，不复用旧映射。

## C++ 侧实现（2026-10-24，待构建验证）

- 新增 `SharedFrameSource.{h,cpp}`，挂到 `VCamSampleSource.vcxproj`。
- 接入点：`MediaStream::RequestSample` 中先 `_shared.FillSample(...)`，失败才走 `FrameGenerator`。
- 路径探测：`CWB_FRAME_FILE` → DLL 祖先目录的 `.run\frames.bin` → `%ProgramData%\CameraWhiteboard`。
- 尺寸必须等于协商的 `1280x960`，否则回落；支持 RGB32 与 NV12。
- 验证方法：`shm_producer.py`（默认 1280x960）→ `read_vcam.py`，画面应变成"深蓝渐变底 + 移动红竖条 + 左上编码块"。

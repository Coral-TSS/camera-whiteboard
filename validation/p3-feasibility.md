# P3 可行性验证：摄像头画面 + 笔迹合成

执行日期：2026-10-25。回答"我的人 + 手上的笔迹同时出现"是否可行。

## 结论

**可行，已在真机上端到端跑通。** 虚拟摄像头输出的就是"实时摄像头画面 + 叠加的笔迹"
（`/.run/composite_test.png` 为读取器抓到的实际输出：房间画面 + 红色折线）。

## 架构判断（关键）

采集**不能**放在媒体源 DLL 里做——DLL 由 Frame Server 加载，运行身份与会话都不确定，
去开物理摄像头很可能被拒。正确分工：

```
用户会话的引擎进程                      Frame Server 侧
┌───────────────────────────┐          ┌──────────────────┐
│ DirectShow 采集物理摄像头  │          │ 媒体源 DLL        │
│        ↓                  │ 共享帧   │ 只读 .run/frames  │
│ QPainter 合成笔迹          │ ──────→  │ 原样送 sample     │
│ 写入 .run/frames.bin      │          └──────────────────┘
└───────────────────────────┘
```

DLL 完全不用改（现有 P1.2 的读取逻辑就是最终形态）。

## 实测数据

| 项 | 结果 |
|---|---|
| 采集后端 | **DirectShow 可用**；Media Foundation 在本环境 `ActivateObject` 返回 `E_INVALIDARG`（枚举同样失败） |
| 640×480 @30fps 采集 | **30.2 fps** 实测 |
| 1280×720 采集 | **7.4 fps**（协商成 YUY2 未压缩，USB 带宽不够） |
| 1920×1080 采集 | 后端回落成 1280×960，7.5 fps |
| BGR→RGBA + 画 40 点笔迹 | 2.6 ms/帧 |
| 取 BGRA 字节 | 1.0 ms/帧 |
| 合成 + 编码合计 | **3.8 ms/帧**（30fps 预算 33.3 ms，余量充足） |
| 整链路（采集→合成→发布 1280×960） | **28.0 fps**（120 帧 / 4.3 s） |

## 720p 的画质瓶颈

C270 的 720p30 必须走 MJPEG。OpenCV 的 DShow 后端**不认** `CAP_PROP_FOURCC`：

- 先设 MJPG 再设尺寸 → 尺寸设定会把格式重置回 YUY2
- 先设尺寸再设 MJPG → 不生效
- 反复设置 → 仍是 YUY2

三条路：

1. **C++ 采集助手**（`native/engine`）：DirectShow + `IAMStreamConfig` 显式选 MJPG/720p30，
   写进共享环形缓冲，Python 侧读取。工作量大但可控，且是 spec 原本规划的位置。
2. **C++ Media Foundation**：本环境 MF 设备激活失败，但可能只是本沙箱限制；需在用户自己的
   终端跑一次 `scripts/probe_camera.py` 确认。
3. **先用 640×480**：放大到 1280×960 会偏软，但今天就能用，零 C++ 改动。

## 其他风险

- 摄像头独占：虚拟摄像头与物理摄像头是两个设备，不冲突；但其他程序若同时开物理摄像头，
  DirectShow 可能打不开（本机未测多客户端）。
- 采集阻塞：`cap.read()` 是阻塞等帧（640×480 下约 33 ms）。引擎需要独立采集线程 + 只保留
  最新帧，不能在发布定时器里同步读，否则会拖累发布节奏。
- 隐私：合成本地完成，画面不落盘、不上传；`.run/frames.bin` 是本地文件映射。

## 复现命令

```
.venv\Scripts\python.exe scripts\probe_camera.py --frames 60        # MF 采集探针（看是否可行）
.venv\Scripts\python.exe scripts\probe_composite.py --size 1280x720 # 采集 + 合成耗时
.venv\Scripts\python.exe scripts\probe_live_composite.py --frames 120
```

最后一条跑起来后，另开一个终端：

```
.venv\Scripts\python.exe scripts\read_vcam.py --frames 20 --save-png .run/composite_test.png
```

## 复核修正（2026-10-25 晚）

用户在自己的普通终端里复现了 MF 失败（`ActivateObject = 0x80070057`），
**排除"沙箱限制"的可能**：这台机器的 MF 设备激活确实不通，DirectShow 正常。结论不变——
采集走 DirectShow。

**一个我自己的误判需要记下来**：调试采集线程时测到 1.0 fps，一度怀疑线程或后端有问题。
实际是房间关灯，画面亮度 **0/255**，摄像头自动曝光把帧时间拉到 1 秒。
判据：先看帧亮度，再看 fps。这条已写进 `camera.py` 与 `camera_helper.py` 的文件头。

## 分辨率上限（亮度正常时测得）

| 请求 | 结果 |
|---|---|
| 640x480 | 30.2 fps 可用 |
| 800x600 | 卡住，拿不到流畅流 |
| 960x720 | 未完成（同上） |
| 1280x720 | 7.4 fps，协商成 YUY2 |
| 1920x1080 | 回落成 1280x960，7.5 fps |

YUY2 未压缩流在 USB 上的带宽上限把这些分辨率压住了；C270 的 720p30 必须走 MJPEG，
而 OpenCV 的 DShow 后端不认 `CAP_PROP_FOURCC`。**要 720p 只能自己写采集端。**

## 已落地（P3.2 首版）

- `ui/camera_whiteboard/camera.py`：DirectShow 采集线程，只保留最新帧；
  无摄像头时 `NullCamera` 兜底，界面逻辑统一。
- `ui/camera_whiteboard/compositor.py`：摄像头画面打底 + 笔迹层覆盖，笔迹层按
  `Canvas.revision` 缓存。
- `publisher` 支持接入合成器；`app` 托盘新增"叠加摄像头画面"开关，默认开。
- 验证：用合成画面（蓝底 + 黄块）跑真实链路，虚拟摄像头输出为
  "蓝底 + 黄块 + 红笔迹"（`.run/fake_cam_out.png`），证明接线正确且不依赖光线。
- 测试：compositor 7 例，全库 63 例通过。

## 画质提升：720p30（2026-10-27）

需求："原摄像头那部分的画质不能变差，至少得和设备一致"。

C270 的 720p30 只能用 MJPEG；YUY2 在 USB 上带宽不够（720p 只有 7.4fps）。
OpenCV 的 DShow 后端不认 `CAP_PROP_FOURCC`，Media Foundation 在本机设备激活不可用，
所以改用 **ffmpeg 子进程**抓 DirectShow：

```
ffmpeg -f dshow -video_size 1280x720 -framerate 30 -vcodec mjpeg -i "video=<设备名>"
       -c:v copy -f mjpeg pipe:1
```

- 管道里传的是摄像头**原生 JPEG**（`-c:v copy`），不重新编码，画质无损。
- Python 侧按 SOI/EOI 切帧，`cv2.imdecode` 解码（720p 约 4-6 ms）。
- 关的时候往 stdin 送 `q` 让 ffmpeg 自己退出，**不硬杀**，避免 UVG 驱动卡死。

实测：**1280x720 @ 29.8 fps**（设备满速），整链路输出仍是 1280x960。

顺带修了一个必然发生的变形问题：摄像头 16:9、输出 4:3，原来直接 `drawImage(rect)`
会把脸拉扁。新增 `draw_cover()` 等比铺满 + 居中裁切，测试里用"方块必须还是方块"来守。

后端优先级：ffmpeg（720p）→ OpenCV（640x480）→ 无摄像头。
`imageio-ffmpeg` 自带 ffmpeg 二进制，已打进打包产物。

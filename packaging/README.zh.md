# Camera Whiteboard

把摄像头画面和白板笔迹合成一路视频，作为一台虚拟摄像头（设备名默认「摄像头1」）提供给会议软件。
本地自用工具，MIT 许可。

- `app/`：可直接运行的 Windows 11 x64 分发目录，先看 [app/USER_GUIDE.md](app/USER_GUIDE.md)。
- `source/`：干净源码，可整目录作为仓库内容提交。
- 二进制不进 Git，放 Releases。

---

## 一、怎么用（App）

### 1. 安装（只需一次）

1. 把整个 `app` 目录解压到本地磁盘，**保留 `_internal`**。
2. 双击 `Install.cmd`，同意管理员授权。它会做三件事：
   - 把媒体源 DLL 复制到 `C:\Program Files\CameraWhiteboard\CameraWhiteboardSource.dll`
   - 注册 CLSID `{2B28F238-082E-4FE4-8142-3141306593D0}`
   - 建 `C:\ProgramData\CameraWhiteboard`（放共享帧和日志）
3. 双击 `CameraWhiteboard.exe`，用**普通权限**运行，不需要常开管理员窗口。

安装/更新前请先退出会议软件和本程序——程序常驻会占用物理摄像头。

### 2. 在会议里选设备

会议软件 → 视频设置 → 选中「**摄像头1**」（系统可能给它加后缀）。

选中一次就不用再改：程序常驻，开关白板都在这一个设备里完成，**不需要在会议里切换视频源**。

### 3. 白板窗口

打开程序会看到一块白底窗口，窗口本身就是画布。

| 操作 | 说明 |
|---|---|
| 在纸面拖动 | 画线 |
| 拖动标题栏 | 移动窗口（画布内容跟着走，笔迹坐标不变） |
| 右下角蓝色方块 | 缩放；输出里白板面板的大小同步变化 |
| 标题栏右侧 `菜单 ☰` | 所有设置都在这里 |
| 标题栏 `✕` | 关闭画布（程序继续运行，输出变成纯摄像头画面） |

### 4. 「菜单 ☰」里的设置

| 项目 | 作用 |
|---|---|
| 画笔 ▸ 画笔 / 橡皮 | 换工具 |
| 画笔 ▸ 颜色 / 笔宽 | 红黄绿蓝黑；细 4 / 中 8 / 粗 16 |
| 撤销（Ctrl+Alt+F9） | 撤销上一笔 |
| 清空 | 清掉所有笔迹 |
| 画布位置（对方画面） | 13 个锚点：九宫格 9 个 + 三分法 4 个交点 |
| 画布大小 | 小 / 中 / 大，改的是白板窗口大小，输出随之等比变化 |
| 水平翻转笔迹 | 把笔迹左右翻转（默认关闭） |
| 叠加摄像头画面 | 关掉就是纯白板，只有笔迹 |
| 让出摄像头（其他程序可用） | 释放物理摄像头，勾上后别的程序才能打开真实摄像头 |
| 输出白底 | 关掉则用透明底（部分客户端显示为黑） |
| 穿透（鼠标不挡手） | 白板不再接收鼠标，点击落到下面的窗口 |
| 显示安全区边框（校准用） | 在输出上画一圈参考框，用来看会议软件裁掉了多少边缘 |
| 关闭画布 | 同上，程序继续跑 |

**关于位置与镜像**：锚点决定白板在对方画面里的位置，面板从左上角开始生长；
镜像只翻笔迹内容，不改变位置。若会议软件的自拍预览是镜像的，请在客户端关掉镜像，
或让对面确认——**不要用翻转发送画面去补偿预览**。

### 5. 托盘与快捷键

托盘图标（右下角）右键可开关画布、切位置/大小、让出摄像头、看运行状态、退出。
**双击托盘图标**也能开关画布。

| 快捷键 | 作用 |
|---|---|
| `Ctrl+Alt+F8` | 切换鼠标穿透 |
| `Ctrl+Alt+F9` | 撤销 |

关白板窗口 ≠ 退出程序。要真正退出（释放设备、卸载前必须做）：托盘 → **退出**。

### 6. 出问题先看这里

| 现象 | 处理 |
|---|---|
| 会议里没有「摄像头1」 | 确认跑过 `Install.cmd`；重启会议软件；程序启动约 0.6 秒后设备可用 |
| 会议里画面黑 | 在会议里切一次别的设备再切回「摄像头1」；确认没勾「让出摄像头」；确认选的是「摄像头1」而不是物理摄像头 |
| 画面全白 | 白板面板铺满，或摄像头没画面（回落到白底） |
| 画面闪过彩色图案 | 那是媒体源读不到新鲜帧时的诊断图案；出现说明送帧中断 |
| 摄像头打不开（别的程序） | 勾「让出摄像头」，或退出本程序 |
| 想看日志 | `C:\ProgramData\CameraWhiteboard\app.log` |

---

## 二、源码框架

### 数据流

```
物理摄像头
   │  ffmpeg 子进程抓 DirectShow MJPEG 1280x720@30
   ▼
FfmpegCamera（后台线程，只保留最新一帧）
   │
   ▼
Compositor ── 摄像头画面（等比铺满 + 居中裁切）+ 4:3 白板面板（白底/边框/笔迹）
   │           笔迹图层按 canvas.revision 缓存，画面没变不重画
   ▼
FramePublisher ── 每 33ms 把整帧写进共享文件（序号锁保护）
   │
   ▼
共享帧文件 frames.bin   ← 64 字节头 + BGRA 像素
   │
   ▼
媒体源 DLL（VCamSampleSource，注册为 CLSID {2B28F238…}）
   │  读到奇数序号 = 生产者正在写 → 重试几毫秒，仍失败才回落诊断图案
   ▼
会议软件（设备名「摄像头1」）
```

界面层和媒体源 DLL **没有直接通信**，只通过共享帧文件交换数据。这样 DLL 只有一份，
也不必在每个客户端里重写；采集可以留在用户会话（帧服务器进程里打不开物理摄像头）。

### 目录与模块

```
ui/camera_whiteboard/
  paths.py        运行期路径：共享帧/日志放哪（源码放仓库 .run，安装版放 ProgramData）
  bootstrap.py    早期启动：单实例互斥 + 创建虚拟摄像头（只用 stdlib/ctypes，先于 Qt）
  config.py       读 config/app.json（设备名、媒体源 CLSID）
  virtualcam.py   IMFVirtualCamera 的 ctypes 封装：创建 / Start / Stop / Remove
  camera.py       采集后端：FfmpegCamera（720p30 首选）、OpenCVCamera（640x480 兜底）
  canvas.py       纯笔迹模型：笔画、橡皮（按线段命中、整笔擦除）、撤销、revision
  render.py       把笔迹画到指定尺寸的透明图层
  layout.py       版式：13 个锚点、4:3 面板尺寸、贴边余量
  compositor.py   合成：摄像头打底 + 白板面板（边框/阴影/镜像/安全区参考框）
  publisher.py    帧协议生产者：33ms 一帧，序号锁保证读端不读到半帧
  viewport.py     白板窗口：自绘标题栏（菜单/关闭）、拖动、缩放、穿透
  hotkeys.py      RegisterHotKey + 独立线程消息循环
  clickthrough.py WS_EX_TRANSPARENT 开关
  log.py          日志（无控制台打包后 sys.stdout 为 None，统一走这里）
  app.py          组装：动作、菜单、托盘、定时器、摄像头占用/让出
  overlay.py      全屏透明层（暂未接入，留给将来的桌面标注模式）

packaging/
  entry.py        打包入口：单实例 → 建虚拟摄像头 → 再导入界面（设备 0.6s 就绪）
  whiteboard.spec PyInstaller 配置（单目录、无控制台、随包带 ffmpeg）

third_party/vcamsample/   媒体源 DLL（基于 MIT 的 VCamSample，本地改过共享帧读取）
scripts/                  体检与调试脚本（doctor_camera / doctor_output / read_vcam …）
tests/ui/                 单元测试（canvas / render / compositor / layout / publisher / camera）
```

### 几个关键机制

**帧协议**（`publisher.py` ↔ DLL）
文件 = 64 字节头 + 像素。头里有 magic `CWB1`、宽高、stride、格式、`seq`、`frameId`、
生产者时间戳、状态。写入时先把 `seq` 改成奇数，写完像素再改成偶数；读端看到奇数或
前后不一致就判定"正在写"。像素固定 BGRA，stride = 宽 × 4。

**为什么每帧都要写**：媒体源判断帧是否新鲜看的是生产者写的时间戳，超过约 2 秒没有新帧
就回落到诊断图案。所以即使画面没变也要按 33ms 持续写。

**为什么关画布不断流**：关画布只是不画面板（`panel_visible=False`），输出变成纯摄像头画面，
会议里看到的还是同一个设备，不需要切换视频源。

**摄像头占用**：ffmpeg 打开 DirectShow 是独占的。程序运行期间一直持有物理摄像头，
所以别的程序打不开它——这是"关画布仍是摄像头画面"的代价。需要同时用真实摄像头时，
托盘勾「让出摄像头」。

**启动顺序**：`entry.py` 先做单实例检查并创建虚拟摄像头（只用 ctypes，几百毫秒），
然后才导入 PySide6/cv2 起界面。所以双击后约 0.6 秒设备就出现在会议里，
而不是等 Qt 加载完（那样要 5 秒以上）。

**分辨率**：采集 1280×720（MJPEG，设备满速 30fps），输出 1280×720。
白板面板是 4:3，宽度 = 白板窗口宽度 ÷ 屏幕宽度，随窗口缩放实时变化。
摄像头 16:9 进输出时等比铺满并居中裁切，不会把脸拉扁。

**单实例**：`Global\CameraWhiteboard.SingleInstance` 互斥体。两个实例会互相拆设备，
表现为黑屏或闪烁，所以第二个实例直接退出并写日志。

---

## 三、从源码运行与打包

```bat
:: 运行（开发）
.venv\Scripts\python.exe scripts\run_ui.py

:: 只检查摄像头
.venv\Scripts\python.exe scripts\doctor_camera.py

:: 检查输出链路（应用运行中也能用）
.venv\Scripts\python.exe scripts\doctor_output.py

:: 跑单元测试（逐模块跑，tests/ui 不是包，用不了 discover）
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python.exe -c "import subprocess,sys,pathlib; [subprocess.run([sys.executable,'-m','tests.ui.'+p.stem]) for p in sorted(pathlib.Path('tests/ui').glob('test_*.py'))]"

:: 打包
.venv\Scripts\pyinstaller.exe packaging\whiteboard.spec --noconfirm ^
    --distpath packaging\dist --workpath packaging\build
```

源码模式的共享帧和日志在仓库 `.run\`；打包版在 `C:\ProgramData\CameraWhiteboard`。
两边都能用环境变量 `CWB_FRAME_FILE` 指定。

改了媒体源 DLL 必须重建：

```bat
scripts\build-vcamsample.cmd
```

---

## 四、已知限制

- 会议客户端可能裁切显示画面，边缘内容会被切掉；菜单里「显示安全区边框」可以量出来。
- 客户端自拍预览可能是镜像的；本程序只翻笔迹，不做预览补偿。
- 摄像头不支持 720p MJPEG 时回落 640×480。
- 摄像头断线后需要退出并重开程序。
- 未签名，首次运行可能触发 SmartScreen。
- 未经干净系统与会议远端验收，详见 `source/validation/`。

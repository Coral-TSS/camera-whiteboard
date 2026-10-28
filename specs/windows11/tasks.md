# 里程碑与执行任务

更新：2026-10-24。定位为**本地自用开源工具**，工程基建已完成，功能实现尚未开始。验收口径改为"自己用的那款会议软件能看到画面"，不再要求多客户端兼容矩阵、签名与升级回滚。

| 阶段 | 状态 | 任务与依赖 | 验收证据 |
|---|---|---|---|
| E0 工程基建 | **完成** | git 仓库（main）、目录骨架、顶层 CMake（C++20）、scripts/env.cmd + env.ps1、PySide6 6.12.0、CMake 4.4.4 / Ninja 1.13.2、.gitignore / .gitattributes / .editorconfig / .clang-format | 提交 `925d18d`、`029ee7f`；`cmake --version` 4.4.4；Qt 离屏创建 QWidget 通过 |
| D0 设计 | **完成** | 范围确认为本地自用开源工具；许可证 **MIT**；媒体源 CLSID `{2B28F238-082E-4FE4-8142-3141306593D0}`、默认设备名 `摄像头1`，记录于 `config/app.json` 与 plan.md | `LICENSE`（MIT）、`config/app.json`、plan.md 平台与注册小节 |
| P0.1 官方基线 | **完成** | VCamSample @ `58b6d4b`（MIT）引入 `third_party/vcamsample/`，依赖已还原，Release x64 构建成功；工具集 v145 与本机 MSVC 14.51 / SDK 26100 一致 | [validation/p0.1-baseline.md](../../validation/p0.1-baseline.md)：产物大小、SHA256、CLSID、注册行为 |
| P0.2 注册 | **完成** | 样例 CLSID 注册成功（HKLM，Default 指向本地 DLL，`ThreadingModel=Both`）；未提权进程中 `MFCreateVirtualCamera` 与 `Start` 均返回 `S_OK` | [validation/p0.1-baseline.md](../../validation/p0.1-baseline.md)；探针 `scripts/doctor_vcam.py` |
| P0.3 动态收流 | **完成** | 独立读取器：300 帧、300 种不同画面、时间戳单调、65 fps；已加入移动色块与 L/R 方向标记并重新构建（DLL sha256 `b4faface…`），复跑判定通过 | [validation/p0.3-stream.md](../../validation/p0.3-stream.md) |
| P0.4 客户端验证 | **完成** | 腾讯会议中选中样例设备（`VCamSample`）能出动态画面，后续界面笔迹也能实时看到 | 用户多轮实测确认；未单独计时 60 秒，属自用口径可接受 |
| P1.1 安全传输实验 | **完成** | 实测普通用户不能创建 `Global\` 文件映射（WinError 5），故放弃命名共享内存；改用文件映射 + 序号锁，无需任何命名内核对象 | [validation/p1-transport.md](../../validation/p1-transport.md)、[frame-protocol.md](frame-protocol.md) |
| P1.2 帧协议 | **完成** | 联调通过；两处陈旧帧修复（本地计时不够，改为比生产者写的 FILETIME）。**已验证回落**：发布器停止 3 秒后读帧，画面回到诊断图案（中心像素 `B=191`，非白板） | [validation/p1-transport.md](../../validation/p1-transport.md) |
| P2.0 坐标系定义 | **完成** | 四条规则已定：独立画布、可关闭视口、缩放影响线宽、越界丢弃 | [canvas-coordinate.md](canvas-coordinate.md)（含变换公式、规则表、4 个用例） |
| P2.1 绘图模型 | **完成** | `ui/camera_whiteboard/canvas.py` 笔迹模型 + `render.py` 透明渲染；画笔、橡皮（按线段命中、整笔擦除）、撤销、清空全部实现 | 17 个单元测试通过（[tests/ui](../../tests/ui)），透明背景与缩放线宽均有断言 |
| P2.2 窗口与穿透 | **完成** | 置顶白板窗口、鼠标→纸坐标、穿透开关、Ctrl+Alt+F8/F9、工具栏与托盘、多屏并集。曾用全屏透明悬浮层，因压住标题栏且全屏可画，已改为白底窗口（`overlay.py` 保留未接入） | 用户手工确认：可画线、穿透可用、撤销可用 |
| P2.3 UI 到输出 | **完成** | 白底窗口即画布，可拖动/缩放/关闭；框外不是画笔；纸坐标模型（拖窗口内容跟随）；输出锁 4:3、`PreciseTimer` 33ms | [validation/p2.3-output.md](../../validation/p2.3-output.md)；用户多轮实机使用确认 |
| P3.1 摄像头采集 | **完成** | 采集在用户会话进程内，DLL 只读共享帧。DirectShow 可用（640×480@30fps）；MF 设备激活在本机不可用（用户终端复现 `E_INVALIDARG`） | [validation/p3-feasibility.md](../../validation/p3-feasibility.md)；`scripts/doctor_camera.py` 可一键体检 |
| P3.2 合成 | **完成** | 摄像头画面 + **带边界的白板面板**；13 个锚点（九宫格 9 + 三分法 4）+ 3 档大小，托盘可切；暗帧/无摄像头自动回落白底不黑屏 | [validation/p2.3-output.md](../../validation/p2.3-output.md)「白板面板版式」；79 个测试 |
| P3.3 画质提升 | **完成** | 改用 ffmpeg 子进程抓 DShow MJPEG（`-c:v copy` 无损直通），拿到 **1280×720@29.8fps**；顺带修 16:9→4:3 的拉伸变形（等比裁切） | [validation/p3-feasibility.md](../../validation/p3-feasibility.md)「画质提升」；测试含"方块必须还是方块" |
| P4.1 自用打包 | **完成** | PyInstaller 单目录打包，`packaging/dist/CameraWhiteboard/CameraWhiteboard.exe`；修复冻结后共享帧路径（与 DLL 搜索顺序对齐）。**不做签名与升级回滚** | [validation/p4.1-packaging.md](../../validation/p4.1-packaging.md)：259 MB、启动即出画面、`--seconds` 正常退出 |
| P4.2 收尾验收 | **进行中** | 设备名改「摄像头1」：应用自己创建并持有虚拟摄像头（名字是创建参数），退出时释放；新增注册与卸载脚本；CLSID 未注册时自动退回样例 | [validation/p4.2-acceptance.md](../../validation/p4.2-acceptance.md)；**待人工确认**：重启免配置、睡眠唤醒、卸载干净、会议内实测 |

进度：**16 / 17 完成**，P4.2 进行中（代码已就绪，剩重启/睡眠/卸载的人工确认）。画质已对齐设备（720p30），可双击运行。

## 执行约定

- 每项拆为一次可验证的提交；失败先复现并记录，不跳过依赖。
- P0 成功不代表 P1 权限或 P3 摄像头包装成功，三者各自验收。
- P1.1 安全传输不成立时暂停后续集成，保留可复现基线；改用 broker 前先记录代价。
- 某款会议软件不兼容只记录并绕开，不作为全局阻塞（自用场景只需保证自己那款可用）。
- 已完成项的证据必须可复查：提交号、版本号、日志路径。

## 遗留缺口

| 缺口 | 说明 | 影响 |
|---|---|---|
| 产品 CLSID 未注册 | 设备名已是「摄像头1」（应用创建时传入）；CLSID 仍是样例 `{3CAD447D…}`。管理员跑 `scripts/register_vcam.ps1` 可切到产品 CLSID | 不影响使用 |
| 整体不透明度 | 视口窗口的整体 alpha 未实现 | 需求未明确要求，可延后 |

## 下一步

1. **P4.2 收尾验收**：睡眠唤醒后摄像头/虚拟设备是否仍可用、重启后是否免配置、卸载是否干净。
2. **产品 CLSID**：把设备名从样例的 `VCamSample` 换成 `摄像头1`（`config/app.json` 已写好）。
3. **产品 CLSID**：把设备名从样例的 `VCamSample` 换成 `摄像头1`（`config/app.json` 里已写好）。

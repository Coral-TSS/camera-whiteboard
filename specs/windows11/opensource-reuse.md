# GitHub 开源复用评估

核对日期：2026-10-24。以下均为**读文档与 README 的结论**，未下载、未编译、未运行；许可证以仓库 LICENSE 文件为准，正式引入前需按固定 commit 复核。

## 结论摘要

- **P0 基线不必只押微软官方仓库**。`smourier/VCamSample` 是 MIT 许可证的最小实现（两个工程），结构比官方 `Windows-Camera` 简单得多，且 README 记录了 Teams 预览正常但对方收不到画面的已知问题、以及 Frame Server 服务访问权限导致的 Access Denied 排查路径。建议作为**第二基线**并行构建。
- **`OneLimeStudio/BestCam` 与本项目架构几乎同构**（Python 生产者 → Global 共享内存 NV12 → C++ MF 虚拟摄像头 → 会议软件）。本项目已定 MIT，故它只能作设计参考（GPL-2.0 不可复制代码）；其 NULL DACL 与强制提权两点无论如何都不能照搬。
- **绘图层有现成的 PySide6 参考**：`MichaelDu4rte/ScreenInkApp`（MIT）覆盖了透明全屏、全局热键、笔/形状/橡皮/撤销、托盘、PyInstaller + Inno Setup 打包，与 P2.1/P2.2 的任务几乎一一对应。
- **没有找到可直接使用的"摄像头 + 白板合成"完整开源项目**——这正是本项目要填的空档。所有候选都只覆盖其中一段。

## A. 可作为实现基线（MIT，可复用代码）

| 项目 | 许可证 | 提供什么 | 对应阶段 |
|---|---|---|---|
| [microsoft/Windows-Camera](https://github.com/microsoft/Windows-Camera) | MIT | 官方 VirtualCamera 示例、媒体源状态机、适用测试 | P0.1（spec 已锁定） |
| [smourier/VCamSample](https://github.com/smourier/VCamSample) | MIT | 极简双工程：`VCamSampleSource`（RGB32 + NV12，Direct2D/DirectWrite 出图，GPU 无则退化 WIC/CPU）+ `VCamSample`（调用 MFCreateVirtualCamera 的壳） | P0.2–P0.3 |
| [MichaelDu4rte/ScreenInkApp](https://github.com/MichaelDu4rte/ScreenInkApp) | MIT | PySide6 屏幕批注 overlay：透明无边框窗口、全局热键、笔/箭头/矩形/椭圆/文字/荧光笔/模糊/橡皮、撤销重做、托盘、PyInstaller + Inno Setup | P2.1–P2.2、P4.1 |
| [tshino/softcam](https://github.com/tshino/softcam) | MIT | DirectShow 虚拟摄像头库，含 `python_binding` 与 `softcam_installer`（安装/卸载实现） | 备选路线 + 安装器参考 |

`VCamSample` 值得单独抄的三处细节：

1. **DLL 必须放在 Frame Server / Frame Server Monitor（Local Service / Local System）可访问的路径**，否则 `IMFVirtualCamera::Start` 返回 `E_ACCESSDENIED`；在用户目录下构建就会踩这个坑。这与 spec 中"COM DLL 安装到受保护目录"的要求方向一致，但给出了具体成因。
2. **ETW 字符串模式追踪**（配合 [TraceSpy](https://github.com/smourier/TraceSpy)，provider GUID `964d4572-adb9-4f3a-8170-fcbecec27467`）。虚拟摄像头链路至少涉及 4 个进程，`OutputDebugString` 不够用——直接对应 spec "记录每个 HRESULT、步骤"的要求。
3. **README 自述的已知缺陷**：Teams 预览正常但远端收不到画面。这不是小问题，恰好是 P0.4 客户端闸门要拦住的场景，说明"预览成功≠协作端成功"的判断是对的。

## B. GPL 项目：取决于你自己的许可证

**本项目已确定开源、本地自用。** 如果项目采用 GPL-2.0，下列项目可以直接改源码，BestCam 的媒体源与共享内存实现是最省力的起点；如果坚持 MIT 保持自由度，则只能读它们的做法，不能复制代码。这是纯取舍，没有对错。

| 项目 | 许可证 | 为什么重要 | 用法 |
|---|---|---|---|
| [OneLimeStudio/BestCam](https://github.com/OneLimeStudio/BestCam) | **GPL-2.0** | 与本项目同构的完整实现：`Global\` 命名共享内存 + Win32 mutex 传 NV12、`reference_companion.py` 约 80 行即可推送动态测试帧、mfpmp.exe 在 Session 0 加载 DLL 的实测结论 | 项目若用 GPL-2.0：直接改其 C++ 媒体源最省力。若用 MIT：只读做法。**其 NULL DACL 无论哪种都不能照抄** |
| [obsproject/obs-studio](https://github.com/obsproject/obs-studio) | GPL-2.0 | DirectShow 虚拟摄像头的事实标准，多客户端兼容性最好 | 只在"MF 路线失败"时考虑；技术路线已被微软弃用，不作为首选 |
| [letmaik/pyvirtualcam](https://github.com/letmaik/pyvirtualcam) | GPL-2.0 | Python 发帧到虚拟摄像头的封装 | 不采用：依赖用户预装 OBS/UnityCapture，自用场景下多一层依赖没有收益 |

**BestCam 的三处反向价值**（比它的代码更有用）：

- 它证明了"Python 生产者 + C++ 媒体源 + 跨会话共享内存"这条路真的能跑通，P1 的可行性风险因此下降。
- 它用 NULL DACL 换来"能跑"，正好是 spec 第 9 行"不得用放开 Everyone 权限绕过问题"要避免的做法——本项目要自己补上 DACL 与握手。
- 它结论"`MFCreateVirtualCamera()` 需要提权"，与 plan.md "普通用户创建 CurrentUser 设备"的说法**存在分歧，需在 P0.2 实测澄清**。

## C. 只借鉴交互与坑位

| 项目 | 许可证/语言 | 可借鉴点 |
|---|---|---|
| [geovens/gInk](https://github.com/geovens/gInk) | MIT / C# | 成熟批注工具的穿透模式、多显示器、笔压、快照；README 明确记录**多屏 DPI 不一致会导致快照区域错误、工具栏拖不动**——正是 spec 要验收的项 |
| [cleoag/UnityCapture](https://github.com/cleoag/UnityCapture) | Filter MIT / Plugin zlib | 异常状态的占位画面设计：分辨率不匹配、发送未开始、发送已停止三种错误各配一张占位图（含绿幕键控选项）——可直接映射到 spec 的"故障占位帧" |
| [smourier/VCamNetSample](https://github.com/smourier/VCamNetSample) | MIT / .NET | 仅作 API 用法交叉验证；引入 .NET 运行时与本项目"单包无额外运行时"冲突，不采用 |
| [dw4dev/DWAnnotation](https://github.com/dw4dev/DWAnnotation) | .NET 8 / WPF | 魔术笔淡出、渐层笔刷等交互细节，优先级低 |

## D. 待验证的分歧点

| 分歧 | 各方说法 | 处理 |
|---|---|---|
| 最低 OS build | spec/plan：22000（依据 Learn 文档）；BestCam：22621（22H2） | P0.1 在目标机实际检查 `mfvirtualcamera.h` 与 API 导出，以实测记录为准 |
| 是否必须提权 | plan：安装提权一次、日常普通用户；BestCam：`MFCreateVirtualCamera` 需提权 | **已实测（2026-10-24）**：未提权进程下 Create 与 Start 均返回 `S_OK`，BestCam 的说法不成立；仅 AllUsers / System 需要管理员 |
| 共享内存 DACL | spec：禁止 NULL DACL；BestCam：用 NULL DACL | 本项目自行实现受限 DACL + 已验证身份的管道握手，P1.1 出证据 |
| Teams 端到端 | VCamSample README：预览正常、远端收不到 | P0.4 必须用第二台设备实拍确认，不接受本地预览作为通过 |

## E. 建议动作

项目许可证已定 **MIT**，因此下列动作按"只读 GPL、可改 MIT"执行：

1. **P0.1 主基线改 VCamSample**：固定 commit 后放进 `third_party/vcamsample/`，用它自带的 `.sln` 构建；官方 `Windows-Camera` 只作对照，不整仓引入。
2. **P0.3 测试帧**：改造 `VCamSample` 的 Direct2D 出图路径为动态色块 + 帧号 + 方向标记。
3. **P1.2 协议**：借鉴 BestCam 的内存布局思路（GPL，不复制代码），头部字段、generation、slotCount、溢出检查按 spec 的 v1 协议自写；**禁止 NULL DACL**。
4. **P2.1/P2.2**：以 `ScreenInkApp` 的 overlay 结构为骨架（MIT，可直接改），补多屏负坐标与 DPI 变化测试。
5. **引入时必须**：每个上游固定 commit、保留 LICENSE、在 `docs/` 出第三方声明；GPL 项目只作设计参考、不落代码。

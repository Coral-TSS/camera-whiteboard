# 官方依据与当前验证边界

核对日期：2026-10-22。以下是在线文档核对，不是运行验证。

| 依据 | 设计使用方式 |
|---|---|
| [MFCreateVirtualCamera](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/nf-mfvirtualcamera-mfcreatevirtualcamera) | 最低 build 22000；sourceId 为媒体源 CLSID；区分 CurrentUser/AllUsers，后者需管理员；相机隐私可能拒绝调用 |
| [IMFVirtualCamera](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/nn-mfvirtualcamera-imfvirtualcamera) | 区分配置、Start、Stop、Remove 与 Shutdown |
| [Start](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/nf-mfvirtualcamera-imfvirtualcamera-start) | Start 后记录 symbolic link，观察源启动/停止事件 |
| [Lifetime](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/ne-mfvirtualcamera-mfvirtualcameralifetime) | Session 随对象释放/Shutdown 结束；System 按文档跨会话与重启 |
| [Access](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/ne-mfvirtualcamera-mfvirtualcameraaccess) | 设备访问范围与 COM 部署权限分开设计 |
| [AddDeviceSourceInfo](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/nf-mfvirtualcamera-imfvirtualcamera-adddevicesourceinfo) | 物理摄像头独占与系统仲裁，禁止不验证即混用外部采集 |
| [微软官方示例](https://github.com/microsoft/Windows-Camera/tree/master/Samples/VirtualCamera) | 官方媒体源与测试作为 P0 起点；服务宿主中的激活必须单独验证 |

注意：官方示例 README 对 System 生命周期有“重启前保留”的旧表述，与 Learn API 定义不一致。本项目采用 API 定义作为设计依据，实际重启行为留待实验。示例 README 亦有历史运行库说明，实际依赖以锁定 commit 的构建产物为准。

当前环境检查：项目初始只有 work/ 与 outputs/；读取系统信息的 CIM 请求失败；PATH 可发现 git 和 Python，未发现 cl、MSBuild、CMake。此结论不证明系统未安装任何 VS 组件，也不证明当前 OS 版本。

已做：读取可获取的前面对话、整理设计、核对微软官方资料、检查可见工具。
未做：获取/锁定完整示例源码、编译、COM 注册、虚拟摄像头注册、共享内存实验、实际视频收流、四款会议软件测试、安装与卸载。
因此所有运行验收仍为未执行，不能宣称“Windows 11 已验证”或“四会议软件兼容”。

## 2026-10-24 环境复测（更正上节）

上节"未发现 cl、MSBuild、CMake"是仅查 PATH 的结论，实际组件存在。复测结果：

- Visual Studio Build Tools 2026，安装位置 `D:\Tools\VS Tools`；`vswhere -requires Microsoft.VisualStudio.Workload.VCTools` 有返回，C++ 桌面工作负载已安装。
- MSVC 工具集 14.51.36231，`VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64` 下 74 个文件，x64 工具链完整。
- Windows SDK 已装 10.0.17134.0、10.0.17763.0、10.0.26100.0。`um\mfvirtualcamera.h` 与 `Lib\um\x64\mfsensorgroup.lib` 均在 26100 中存在。
- PATH 中无 CMake。Python venv 为 3.13.17，仅装 pip，未装 PySide6。项目目录不是 git 仓库。

由此修正两点：plan.md 的"最低 SDK 基线 10.0.22000.0"在本机不可选，实际只能锁 26100；MSVC 14.51 属较新工具集，是否可构建上游示例未验证，属新增风险而非已知可用。


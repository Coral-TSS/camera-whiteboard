# 技术设计草案

## 架构决策
UI 使用 Python/PySide6；媒体源 DLL、虚拟设备管理器、视频引擎使用 C++。媒体源必须在 Python 不运行时仍能被系统加载并输出占位帧，禁止依赖 Python 解释器或 Qt。优先复用微软官方示例的媒体源状态机、事件与采样流程，而非重写简化版 IMFMediaSource。

数据路径：
桌面笔迹模型 → 透明像素层 → 共享内存 → C++ 引擎（物理摄像头采集、变换、合成）→ 输出共享内存 → 系统加载的媒体源 DLL → Frame Server → 会议软件。
控制路径：UI ↔ 引擎使用带版本的命名管道；系统媒体源 ↔ 引擎的控制及共享内存连接另设安全边界。预览读取引擎输出，不另开物理摄像头。

P0 媒体源自己生成动态帧。P1 先只做外部测试帧生产者；P3 再加入摄像头。若跨安全上下文传输无法安全成立，先停止 P2 集成，改用受控 broker 或官方 AugmentedMediaSource 内部采集/合成方案；不得用放开 Everyone 权限绕过问题。

## 平台与注册
MFCreateVirtualCamera 最低 OS build 22000，头文件 mfvirtualcamera.h，链接 mfsensorgroup.lib。最低 SDK 基线 10.0.22000.0，实际工具集和 SDK 在首次构建后锁定；不承诺只装一个 SDK 即能构建整个官方仓库。
P0 采用 SoftwareCameraSource + Session + CurrentUser，管理器保持对象存活。生产候选为 System + CurrentUser；所有用户可见是另一个明确的产品选项，不能默认使用。System 的持久性按 API 文档解释并实测。
COM DLL 安装到受保护的 Program Files，x64 注册写入 HKLM\Software\Classes\CLSID\{2B28F238-082E-4FE4-8142-3141306593D0}\InprocServer32；ThreadingModel 按实际 COM 实现设定。不能将 DLL 放在用户可写目录后让服务加载。微软示例与产品使用不同 CLSID，避免覆盖示例。CurrentUser 设备作用域不等于 HKCU COM 注册可被服务激活。

已分配身份（2026-10-24，来源 `config/app.json`，勿随意变更）：媒体源 CLSID `{2B28F238-082E-4FE4-8142-3141306593D0}`；默认设备名 `摄像头1`。设备名是 `MFCreateVirtualCamera` 的创建参数而非可改属性，因此"可编辑"的实现是：从配置读名字 → Stop/Remove 旧设备 → 用新名字 Start。会议软件占用摄像头时改名会失败，需提示关闭占用程序；改名后客户端看到的是新设备，需重新选择一次。
管理员阶段只部署/注册 DLL；普通用户阶段创建本人设备，避免安装器提权后把 CurrentUser 设备创建给另一管理员账号。升级保留固定设备身份参数；卸载先 Remove，再注销 COM、清理文件。跨用户设备清理策略须在 P4 验证，不能只在 SYSTEM 身份下删除“当前用户”实例。

## 媒体源与时钟
拟议 manager 命令：doctor、register、status、stop、remove；这是待实现接口。COM 初始化、MFStartup/MFShutdown 成对，注册工作不放 UI 线程。记录每个 HRESULT、步骤、设备 symbolic link、OS/架构。
以官方 SimpleMediaSource 为 P0 起点；先枚举并记录其真实媒体类型，再建立 720p/30fps NV12 基线，按需要增加 RGB32 和 1080p。不可对未实现的类型虚假声明支持。样本使用单调时钟，100ns 单位时间戳/持续时间，按有理数帧率累加防止漂移；保留请求 token，正确处理 start/stop/shutdown、背压和多次打开。测试图包含移动色块、帧号/时间标识、方向标记，禁止静态图冒充动态流。

## 共享帧协议 v1（P1 冻结 ABI）
协议使用固定宽整数和固定偏移序列化，不直接共享 C++ struct 或 Qt 对象。头部含 magic、major/minor、headerBytes、mappingBytes、generation、width/height、stride、format、payloadBytes、frameId、timestamp、slotCount、flags；尺寸和长度须溢出检查并有硬上限。初期固定 720p；分辨率变化通过新 generation/新 mapping 重新协商。
逻辑白板是 RGBA；共享内存明确采用小端 BGRA8、预乘 alpha，与 QImage Format_ARGB32_Premultiplied 在目标平台的字节排列一致，跨边界做显式校验。无隐藏的 RGBA/BGRA 假设。
先用三槽 + 跨进程 mutex + 通知事件：写方只在锁内提交完整帧，读方在锁内复制最新完整帧至私有缓冲，锁外处理。超时则重复最近有效帧，避免阻塞系统采样；abandoned mutex 使该 generation 失效并重建。事件只用于提示，可合并；frameId 才判断新帧。先证明正确，再按测量决定是否改原子发布。
只取最新帧，不无限积压。超时 2 秒转为故障占位帧；UI 崩溃时清空共享白板而非保留敏感笔迹。引擎重启重新握手，旧 generation 不复用。

## 安全上下文验证门槛
UI/引擎在交互用户会话；媒体源实际服务宿主、token SID、session、完整性和受限状态必须在目标机记录，不把某个服务账号硬编码成事实。
Local 命名空间跨会话不可假定可见；Global 文件映射的创建权限也不可假定普通用户具备。P1 先做最小跨宿主打开实验：由有权限的宿主/broker 创建资源，通过已认证的管道协商句柄或名称。对管道限制本机、验证客户端身份，DACL 只授予目标用户与实测所需服务主体，读写权限分离；拒绝其他普通用户及同名抢占，禁止 NULL DACL。必要时由单安装包部署最小 broker，明确新增服务成本后修订方案。
媒体源激活线程不得无限等待 UI；未连接可独立输出占位帧。先验证读帧、重启、拒绝未授权访问三项，再冻结协议。

## UI 与合成
笔迹保存为逻辑画布坐标与笔画对象，QPainter 渲染透明层；本地窗口移动不重写笔迹。无边框置顶透明窗口实现鼠标绘图；穿透设置使用 Qt/Win32 组合并实测，不能仅依据 WS_EX_TRANSPARENT 名字认定完成。多屏负坐标、DPI 变化和热拔插都做坐标转换测试。
工具栏独立窗口；全局快捷键注册失败可恢复，托盘保留模式切换入口。对外视口按 [canvas-coordinate.md](canvas-coordinate.md) 定义：画布上的矩形 `(vx, vy, vw, vh)` 加 opacity，可移动、可缩放、可关闭；输出时等比贴入帧并留边，不拉伸；支持恢复默认。
采集由引擎单独拥有，过滤本产品及其他虚拟设备，避免反馈环。先 CPU 合成 BGRA 再转换 NV12；1080p 性能不达标再引入 D3D11。预乘色 B，alpha a，全局透明度 o，背景 C，结果为 B*o + C*(1-a*o)。明确 BT.709、范围、stride、色彩转换，并以半透明边缘图测试。摄像头比例默认等比留边。
AddDeviceSourceInfo 用于由虚拟源包装物理摄像头的模式；外部引擎先开摄像头的路径不可盲目同时声明独占，避免与系统仲裁冲突。该项为 P3 决策门，需实际验证后选择外部引擎或源内包装。

## 安装与依赖
单个签名安装包携带 UI、嵌入式 Python、PySide6/Qt 插件、C++ 组件及所需运行库，最终机不需要 VS/SDK。开发期采用 VS C++ 工具链与 Windows SDK；官方项目附加依赖按锁定版本核查。Python/PySide6 版本在依赖验证后锁定，附带许可证清单。
安装器必须支持失败回滚、升级文件占用、重启待办提示和卸载；不停止系统摄像头服务来强制替换。签名、SmartScreen 及企业策略单独验证，不承诺签名可绕过策略。

## 拟议目录（当前仅文档存在）
```text
CameraWhiteboard/
  README.md
  specs/windows11/              # 规格、设计、任务、验收与证据
  third_party/Windows-Camera/   # 固定 commit 的官方基线与许可证
  native/
    manager/                   # 设备生命周期与诊断 CLI
    media_source/              # 系统加载的 COM DLL
    engine/                    # 采集、合成、输出
    ipc/                       # 协议、ACL、连接与帧传输
  ui/camera_whiteboard/        # 笔迹、悬浮层、工具栏、预览
  tests/{native,ui,integration}/
  packaging/                  # 单安装包、签名、回滚
  scripts/                    # 构建与只读诊断
  docs/                       # 用户指南与第三方声明
  validation/                 # 机器、应用版本、日志、结果索引
```

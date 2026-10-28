@echo off
REM 构建 third_party\vcamsample 的 Release x64（P0.1 基线）
REM 用法：  scripts\build-vcamsample.cmd
REM 注意：必须在真实终端里跑，沙箱/受限环境会拦 cl.exe 与 MSBuild。

setlocal
for %%i in ("%~dp0..") do set "ROOT=%%~fi"
set "SLN=%ROOT%\third_party\vcamsample\VCamSample.sln"
set "NUGET=%ROOT%\scripts\tools\nuget.exe"

if not exist "%SLN%" (
    echo [build] 未找到解决方案：%SLN%
    exit /b 1
)

call "%ROOT%\scripts\env.cmd" >nul
if errorlevel 1 (
    echo [build] 环境加载失败
    exit /b 1
)

REM packages.config 风格必须用 nuget.exe 还原，msbuild -t:Restore 对它无效
if not exist "%ROOT%\third_party\vcamsample\packages\Microsoft.Windows.CppWinRT.3.0.260818.1" (
    if not exist "%NUGET%" (
        if not exist "%ROOT%\scripts\tools" mkdir "%ROOT%\scripts\tools"
        echo [build] 缺少 nuget.exe，正在下载...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://dist.nuget.org/win-x86-commandline/latest/nuget.exe' -OutFile '%NUGET%'"
    )
    echo [build] 还原 NuGet 包...
    "%NUGET%" restore "%SLN%" -NonInteractive || exit /b 1
)

echo [build] 开始编译 Release x64 ...
msbuild "%SLN%" /p:Configuration=Release /p:Platform=x64 /v:minimal /nologo
if errorlevel 1 (
    echo [build] 编译失败，完整日志请加 /v:diag
    exit /b 1
)

echo.
echo [build] 完成，产物：
dir /b "%ROOT%\third_party\vcamsample\x64\Release\*.dll" 2>nul
dir /b "%ROOT%\third_party\vcamsample\x64\Release\*.exe" 2>nul
echo.
echo [build] 下一步：以管理员注册媒体源（DLL 路径必须对 Frame Server 可读）
echo         regsvr32 "%ROOT%\third_party\vcamsample\x64\Release\VCamSampleSource.dll"
echo         然后运行 VCamSample.exe，再用相机应用确认能看到动态画面

endlocal

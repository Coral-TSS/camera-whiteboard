@echo off
REM 在当前 cmd 会话中准备 C++ 构建环境（MSVC + CMake + Ninja + venv）。
REM 用法：  call scripts\env.cmd
REM 必须用 call，否则环境变量不会留在当前会话。
REM 约定：所有缓存、临时文件都指向项目内 .build\，不写用户目录。

set "VSRoot=D:\Tools\VS Tools"

if not exist "%VSRoot%\VC\Auxiliary\Build\vcvars64.bat" (
    echo [env] 未找到 vcvars64.bat，请修改本文件里的 VSRoot
    exit /b 1
)

REM 归一化项目根目录（去掉 .. 与结尾反斜杠）
for %%i in ("%~dp0..") do set "ROOT=%%~fi"

REM 工具缓存与临时目录一律留在项目内
set "BUILD=%ROOT%\.build"
if not exist "%BUILD%\tmp" mkdir "%BUILD%\tmp" >nul 2>&1
set "NUGET_HTTP_CACHE_PATH=%BUILD%\nuget-http-cache"
set "NUGET_PACKAGES=%BUILD%\nuget-packages"
set "PIP_CACHE_DIR=%BUILD%\pip-cache"
set "TEMP=%BUILD%\tmp"
set "TMP=%BUILD%\tmp"

call "%VSRoot%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 (
    echo [env] vcvars64.bat 执行失败
    exit /b 1
)

set "PATH=%VSRoot%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%PATH%"
set "PATH=%VSRoot%\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
set "PATH=%ROOT%\.venv\Scripts;%PATH%"

echo [env] cmake  ^| & cmake --version 2^>nul | findstr /b /c:"cmake version"
echo [env] python ^| & python --version 2^>nul
echo [env] 缓存在 ^| %BUILD%
echo [env] 下一步 ^| cmake -S . -B build -G Ninja

set "VSRoot="

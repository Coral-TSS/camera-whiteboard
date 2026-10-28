# 在当前 PowerShell 会话中准备 C++ 构建环境（MSVC + CMake + Ninja + venv）。
# 用法：  . .\scripts\env.ps1
# 必须用点号导入，否则环境变量只存在于子进程，退出即失效。

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$vsRoot = 'D:\Tools\VS Tools'

if (-not (Test-Path $vsRoot)) {
    throw "未找到 Visual Studio Build Tools：$vsRoot ；若装在别处，请改本脚本的 `$vsRoot"
}

# 1) 工具缓存与临时目录一律留在项目内 .build\
$build = Join-Path $root '.build'
$tmpDir = Join-Path $build 'tmp'
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$env:NUGET_HTTP_CACHE_PATH = Join-Path $build 'nuget-http-cache'
$env:NUGET_PACKAGES = Join-Path $build 'nuget-packages'
$env:PIP_CACHE_DIR = Join-Path $build 'pip-cache'
$env:TEMP = $tmpDir
$env:TMP = $tmpDir

# 2) MSVC：导入 vcvars64 的环境变量（cl.exe / link.exe / INCLUDE / LIB）
$vcvars = Join-Path $vsRoot 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $vcvars)) {
    throw "未找到 vcvars64.bat：$vcvars"
}

$dump = Join-Path $env:TEMP ('vcvars_' + $PID + '.txt')
$cmdLine = 'call "' + $vcvars + '" >nul 2>&1 && set > "' + $dump + '"'
cmd /c $cmdLine | Out-Null

if (-not (Test-Path $dump)) {
    throw "vcvars64.bat 执行失败，未生成环境导出文件"
}

Get-Content $dump | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $name = $matches[1]
        $value = $matches[2]
        # 以 = 开头的变量（如 =C:）无法写入 env:，直接跳过
        if (-not $name.StartsWith('=')) {
            Set-Item -Path ('env:' + $name) -Value $value
        }
    }
}
Remove-Item $dump -Force

# 3) CMake 与 Ninja：VS Build Tools 自带，但不在 PATH 中
$cmakeBin = Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin'
$ninjaBin = Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja'
if (Test-Path $cmakeBin) { $env:PATH = $cmakeBin + ';' + $env:PATH }
if (Test-Path $ninjaBin) { $env:PATH = $ninjaBin + ';' + $env:PATH }

# 4) Python venv 优先于系统 Python
$venvScripts = Join-Path $root '.venv\Scripts'
if (Test-Path $venvScripts) { $env:PATH = $venvScripts + ';' + $env:PATH }

# 5) 自检
$cmakeLine = (cmake --version | Select-Object -First 1)
Write-Host ("cmake  : " + $cmakeLine) -ForegroundColor Green
Write-Host ("ninja  : " + (ninja --version)) -ForegroundColor Green
Write-Host ("python : " + (python --version 2>&1)) -ForegroundColor Green
Write-Host ("缓存在 : " + $build) -ForegroundColor Green
Write-Host ""
Write-Host "接下来可以：cmake -S . -B build -G Ninja" -ForegroundColor Cyan

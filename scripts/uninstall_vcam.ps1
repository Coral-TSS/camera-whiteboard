# 卸载：清掉虚拟摄像头注册与运行期文件（需要管理员）
# 用法（管理员 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall_vcam.ps1

$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent $PSScriptRoot
$clsidProduct = '{2B28F238-082E-4FE4-8142-3141306593D0}'
$clsidSample  = '{3CAD447D-F283-4AF4-A3B2-6F5363309F52}'

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host '需要管理员权限：请以管理员身份打开 PowerShell 后重跑。' -ForegroundColor Red
    exit 1
}

# 1) 先停掉可能还活着的界面进程，避免 DLL 被占用
Get-Process CameraWhiteboard -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

# 2) 删注册项
foreach ($clsid in @($clsidProduct, $clsidSample)) {
    $key = "HKLM:\SOFTWARE\Classes\CLSID\$clsid"
    if (Test-Path $key) {
        Remove-Item -Path $key -Recurse -Force
        Write-Host "已删除注册项：$clsid" -ForegroundColor Green
    } else {
        Write-Host "未注册：$clsid"
    }
}

# 3) 删运行期文件
foreach ($path in @((Join-Path $root '.run'), (Join-Path $env:ProgramData 'CameraWhiteboard'))) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force
        Write-Host "已删除：$path" -ForegroundColor Green
    }
}

Write-Host ''
Write-Host '完成。建议确认：' -ForegroundColor Cyan
Write-Host '  1) 会议软件里不再出现「摄像头1」'
Write-Host '  2) 其他真实摄像头仍可正常使用'
Write-Host "  3) 需要恢复时：powershell -ExecutionPolicy Bypass -File scripts\register_vcam.ps1"

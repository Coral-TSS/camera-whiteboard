# 把媒体源 DLL 注册到产品 CLSID（需要管理员）
# 用法（管理员 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File scripts\register_vcam.ps1

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$dll  = Join-Path $root 'third_party\vcamsample\x64\Release\VCamSampleSource.dll'
$clsid = '{2B28F238-082E-4FE4-8142-3141306593D0}'
$key = "HKLM:\SOFTWARE\Classes\CLSID\$clsid"

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Administrator access required. Re-run from an elevated PowerShell.' -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $dll)) {
    Write-Host "DLL not found: $dll (build VCamSampleSource first)" -ForegroundColor Red
    exit 1
}

New-Item -Path $key -Force | Out-Null
Set-ItemProperty -Path $key -Name '(Default)' -Value 'Camera Whiteboard media source'
New-Item -Path "$key\InprocServer32" -Force | Out-Null
Set-ItemProperty -Path "$key\InprocServer32" -Name '(Default)' -Value $dll
Set-ItemProperty -Path "$key\InprocServer32" -Name 'ThreadingModel' -Value 'Both'

Write-Host "Registered: $clsid" -ForegroundColor Green
Write-Host "  DLL: $dll"
Write-Host ''
Write-Host 'The app chooses the device name from config/app.json at startup.'
Write-Host 'Optional registry description:'
Write-Host "  Set-ItemProperty '$key' -Name 'FriendlyName' -Value 'Camera Whiteboard'"

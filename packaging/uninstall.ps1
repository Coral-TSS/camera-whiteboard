$ErrorActionPreference = 'Stop'
try {
    if (-not [Environment]::Is64BitProcess) { throw 'Run using 64-bit PowerShell.' }
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        $child = Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $PSCommandPath) -Verb RunAs -Wait -PassThru
        exit $child.ExitCode
    }
    if (Get-Process CameraWhiteboard -ErrorAction SilentlyContinue) { throw 'Exit CameraWhiteboard from its tray menu first; close camera clients too.' }
    $programFilesRoot = [IO.Path]::GetFullPath($env:ProgramFiles)
    $programDataRoot = [IO.Path]::GetFullPath($env:ProgramData)
    $installDir = [IO.Path]::GetFullPath((Join-Path $programFilesRoot 'CameraWhiteboard'))
    $framesDir = [IO.Path]::GetFullPath((Join-Path $programDataRoot 'CameraWhiteboard'))
    if ([IO.Path]::GetDirectoryName($installDir) -ne $programFilesRoot -or
        [IO.Path]::GetDirectoryName($framesDir) -ne $programDataRoot) { throw 'Unexpected uninstall target.' }
    foreach ($target in @($installDir, $framesDir)) {
        if (Test-Path -LiteralPath $target) {
            if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing to remove a linked directory.' }
        }
    }
    $key = 'HKLM:\SOFTWARE\Classes\CLSID\{2B28F238-082E-4FE4-8142-3141306593D0}'
    if (Test-Path -LiteralPath $key) { Remove-Item -LiteralPath $key -Recurse -Force }
    # The app uses Session lifetime and removes its device on normal exit.
    # No sample CLSID or other vendor's virtual camera is touched.
    foreach ($target in @($installDir, $framesDir)) {
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    }
    Write-Host 'Product registration and runtime files removed. The app folder may now be deleted.' -ForegroundColor Green
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 1
}

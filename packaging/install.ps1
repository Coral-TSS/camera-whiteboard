param([string]$TargetUserSid)
$ErrorActionPreference = 'Stop'
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows 11 x64 is required.' }
    if ([Environment]::OSVersion.Version.Build -lt 22000) { throw 'Windows build 22000 or newer is required.' }
    if (-not [Environment]::Is64BitProcess) { throw 'Run this installer using 64-bit PowerShell.' }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $isAdmin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $TargetUserSid) { $TargetUserSid = $identity.User.Value }
    $null = [Security.Principal.SecurityIdentifier]::new($TargetUserSid)
    if (-not $isAdmin) {
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -TargetUserSid "{1}"' -f $PSCommandPath, $TargetUserSid
        $child = Start-Process powershell.exe -ArgumentList $arguments -Verb RunAs -Wait -PassThru
        exit $child.ExitCode
    }
    if (Get-Process CameraWhiteboard -ErrorAction SilentlyContinue) { throw 'Close CameraWhiteboard and camera clients before installing/updating.' }
    $source = Join-Path $PSScriptRoot 'native\CameraWhiteboardSource.dll'
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing native DLL: $source" }
    $installDir = Join-Path $env:ProgramFiles 'CameraWhiteboard'
    $framesDir = Join-Path $env:ProgramData 'CameraWhiteboard'
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    New-Item -ItemType Directory -Path $framesDir -Force | Out-Null
    # Only the installing user may write frames; the system hosts may read them.
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($entry in @(@('S-1-5-18', 'FullControl'), @('S-1-5-32-544', 'FullControl'),
                         @($TargetUserSid, 'Modify'), @('S-1-5-19', 'ReadAndExecute'))) {
        $sid = [Security.Principal.SecurityIdentifier]::new($entry[0])
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, $entry[1],
            'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $framesDir -AclObject $acl
    $dll = Join-Path $installDir 'CameraWhiteboardSource.dll'
    Copy-Item -LiteralPath $source -Destination $dll -Force
    $key = 'HKLM:\SOFTWARE\Classes\CLSID\{2B28F238-082E-4FE4-8142-3141306593D0}\InprocServer32'
    New-Item -Path $key -Force | Out-Null
    Set-Item -LiteralPath $key -Value $dll
    New-ItemProperty -LiteralPath $key -Name ThreadingModel -Value Both -PropertyType String -Force | Out-Null
    Write-Host 'Installed. Start CameraWhiteboard.exe as the original (non-admin) user.' -ForegroundColor Green
    Write-Host 'The app folder can now be moved. Do not delete individual files inside _internal.'
    Write-Host 'This installation serves one interactive user on this PC. Re-run Install.cmd as another user to change access.'
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 1
}

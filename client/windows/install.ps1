# Makia Windows Full Device Connector + standalone Desktop 0.1.0 RC installer.
param([string]$SourceDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
New-Item -ItemType Directory -Force -Path $target | Out-Null

if (Get-Process -Name MakiaDesktop,MakiaClientConnector -ErrorAction SilentlyContinue) {
  throw "Close Makia Desktop and the connector before updating; disconnect an active tunnel deliberately."
}

foreach ($name in @("MakiaClientConnector.exe","MakiaDesktop.exe","sing-box.exe","wstunnel.exe")) {
  $src = Join-Path $SourceDir $name
  if (!(Test-Path $src)) { throw "Missing $name in package" }
  Copy-Item -Force $src (Join-Path $target $name)
}

$connector = Join-Path $target "MakiaClientConnector.exe"
$desktopApp = Join-Path $target "MakiaDesktop.exe"
$runtime = Join-Path $target "sing-box.exe"
$wstunnel = Join-Path $target "wstunnel.exe"

# Register the per-user makia:// launcher used by the authenticated Client Portal.
$base = "HKCU:\Software\Classes\makia"
New-Item -Force -Path $base | Out-Null
Set-Item -Path $base -Value "URL:Makia Client Connector"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Force -Path "$base\DefaultIcon" | Out-Null
Set-Item -Path "$base\DefaultIcon" -Value ('"' + $connector + '",0')
New-Item -Force -Path "$base\shell\open\command" | Out-Null
Set-Item -Path "$base\shell\open\command" -Value ('"' + $connector + '" "%1"')

foreach ($path in @($connector,$desktopApp,$runtime,$wstunnel)) {
  if (!(Test-Path $path)) { throw "Makia Windows installation missing: $path" }
}
$registered = (Get-Item "$base\shell\open\command").GetValue("")
if ([string]::IsNullOrWhiteSpace($registered) -or !$registered.Contains("MakiaClientConnector.exe")) {
  throw "makia:// registration failed"
}

$state = @{
  version = "desktop-0.1.0-rc1"
  mode = "full-device"
  connector = $connector
  desktop = $desktopApp
  runtime = $runtime
  wstunnel = $wstunnel
  installed_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText((Join-Path $target "install-state.json"),$state,(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
# Shortcuts are per-user; the GUI is not elevated. Connector asks UAC
# only when the selected full-device tunnel requires Windows privileges.
if ($env:MAKIA_INSTALL_SKIP_SHORTCUT -ne "1") {
  $shell = New-Object -ComObject WScript.Shell
  $startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Makia Desktop.lnk"
  $desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Makia Desktop.lnk"
  foreach ($shortcutPath in @($startMenu,$desktopShortcut)) {
    $link = $shell.CreateShortcut($shortcutPath)
    $link.TargetPath = $desktopApp
    $link.WorkingDirectory = $target
    $link.Description = "Makia Desktop - Full Device VPN"
    $link.Save()
  }
}

Write-Host "Makia Desktop 0.1.0 RC installed successfully." -ForegroundColor Green
Write-Host "Open Makia Desktop from Desktop or Start Menu." -ForegroundColor Cyan
Write-Host "Desktop: $desktopApp"
Write-Host "Connector: $connector"
Write-Host "Runtime: $runtime"
Write-Host "WStunnel: $wstunnel"
Write-Host "Browser VPN users do not need this package; use the Makia Browser VPN extension instead." -ForegroundColor Yellow

# Makia Desktop 0.1.0 RC + existing Windows Full Device Connector.
param([string]$SourceDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
$required = @("MakiaClientConnector.exe","MakiaDesktop.exe","sing-box.exe","wstunnel.exe")

if (Get-Process -Name MakiaDesktop,MakiaClientConnector -ErrorAction SilentlyContinue) {
  throw "Close Makia Desktop and Connector before updating. Disconnect active VPN deliberately."
}
foreach ($name in $required) {
  if (!(Test-Path (Join-Path $SourceDir $name))) { throw "Missing package file: $name" }
}

# Verify all shipped executables BEFORE touching the existing installation.
# The CI smoke runs before the SHA256SUMS manifest is generated and opts out
# only through its explicit MAKIA_INSTALL_SKIP_SHORTCUT environment variable.
$sumFile = Join-Path $SourceDir "SHA256SUMS.txt"
if (Test-Path $sumFile) {
  $hashes = @{}
  foreach ($line in (Get-Content -LiteralPath $sumFile)) {
    if ($line -match '^([a-fA-F0-9]{64})  ([A-Za-z0-9._-]+)$') {
      $hashes[$Matches[2]] = $Matches[1].ToLowerInvariant()
    }
  }
  foreach ($name in $required) {
    if (!$hashes.ContainsKey($name)) { throw "Checksum entry missing: $name" }
    $actual = (Get-FileHash (Join-Path $SourceDir $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hashes[$name] -ne $actual) { throw "Package checksum mismatch: $name" }
  }
} elseif ($env:MAKIA_INSTALL_SKIP_SHORTCUT -ne "1") {
  throw "SHA256SUMS.txt missing; extract the complete official CI artifact."
}

New-Item -ItemType Directory -Path $target -Force | Out-Null
$backup = Join-Path (Split-Path $target -Parent) ("backup-before-desktop-"+[guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$hadOld = @{}
foreach ($name in $required) {
  $previous = Join-Path $target $name
  $hadOld[$name] = Test-Path $previous
  if ($hadOld[$name]) { Copy-Item -LiteralPath $previous -Destination (Join-Path $backup $name) -ErrorAction Stop }
}
try {
  foreach ($name in $required) {
    $src = Join-Path $SourceDir $name
    $dst = Join-Path $target $name
    Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop
    if ((Get-FileHash $src -Algorithm SHA256).Hash -ne (Get-FileHash $dst -Algorithm SHA256).Hash) {
      throw "Installed binary checksum mismatch: $name"
    }
  }
} catch {
  foreach ($name in $required) {
    $dst = Join-Path $target $name
    if ($hadOld[$name]) {
      Copy-Item -LiteralPath (Join-Path $backup $name) -Destination $dst -Force -ErrorAction SilentlyContinue
    } else {
      Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
    }
  }
  throw
}

$connector = Join-Path $target "MakiaClientConnector.exe"
$desktopApp = Join-Path $target "MakiaDesktop.exe"
$runtime = Join-Path $target "sing-box.exe"
$wstunnel = Join-Path $target "wstunnel.exe"

# Per-user makia:// registration; ticket-only URLs, never raw VPN credentials.
$base = "HKCU:\Software\Classes\makia"
New-Item -Path $base -Force | Out-Null
Set-Item -Path $base -Value "URL:Makia Client Connector"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Path "$base\DefaultIcon" -Force | Out-Null
Set-Item -Path "$base\DefaultIcon" -Value ('"' + $connector + '",0')
New-Item -Path "$base\shell\open\command" -Force | Out-Null
Set-Item -Path "$base\shell\open\command" -Value ('"' + $connector + '" "%1"')

foreach ($path in @($connector,$desktopApp,$runtime,$wstunnel)) {
  if (!(Test-Path $path)) { throw "Makia installation missing: $path" }
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

if ($env:MAKIA_INSTALL_SKIP_SHORTCUT -ne "1") {
  $shell = New-Object -ComObject WScript.Shell
  $menu = Join-Path ([Environment]::GetFolderPath("Programs")) "Makia Desktop.lnk"
  $desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Makia Desktop.lnk"
  foreach ($shortcutPath in @($menu,$desktop)) {
    $link = $shell.CreateShortcut($shortcutPath)
    $link.TargetPath = $desktopApp
    $link.WorkingDirectory = $target
    $link.Description = "Makia Desktop - Full Device VPN"
    $link.Save()
  }
}

Write-Host "Makia Desktop 0.1.0 RC installed successfully." -ForegroundColor Green
Write-Host "Launch Makia Desktop from Windows Desktop or Start Menu." -ForegroundColor Cyan
Write-Host "Desktop: $desktopApp"
Write-Host "Connector: $connector"
Write-Host "Runtime: $runtime"
Write-Host "WStunnel: $wstunnel"
Write-Host "Browser-only users should install the separate Makia Browser VPN extension." -ForegroundColor Yellow

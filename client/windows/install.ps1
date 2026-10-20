# Makia Windows Full Device Connector installer.
# The CMD launcher intentionally passes no SourceDir: $PSScriptRoot reliably
# handles spaces and avoids a quoted directory ending in backslash.
param([string]$SourceDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"
$version = "1.6.4.1"
$names = @("MakiaClientConnector.exe","sing-box.exe","wstunnel.exe")
# Windows PowerShell 5.1 may inherit a restricted module path from pwsh.
# Use the built-in .NET SHA256 implementation instead of Get-FileHash.
function Get-ConnectorSha256([string]$FilePath) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $stream = [System.IO.File]::OpenRead($FilePath)
  try {
    return [System.BitConverter]::ToString($sha.ComputeHash($stream)).Replace("-","")
  } finally {
    $stream.Dispose()
    $sha.Dispose()
  }
}


if ([string]::IsNullOrWhiteSpace($SourceDir)) { throw "Package directory was not provided." }
# Also accept a caller-supplied directory for automated smoke tests.
$sourcePath = $SourceDir.Trim().Trim('"')
try {
  $sourcePath = (Resolve-Path -LiteralPath $sourcePath -ErrorAction Stop).ProviderPath
} catch {
  throw "Invalid installer package directory. Extract the full ZIP before installing."
}
if (!(Test-Path -LiteralPath $sourcePath -PathType Container)) {
  throw "Installer package directory is not a folder."
}

# Preflight the complete package BEFORE touching an existing installation.
foreach ($name in $names) {
  $src = Join-Path $sourcePath $name
  if (!(Test-Path -LiteralPath $src -PathType Leaf)) {
    throw "Missing $name in package. Extract the complete ZIP, then run Install-Makia.cmd."
  }
  if ((Get-Item -LiteralPath $src).Length -lt 1) {
    throw "Empty $name in package."
  }
}

$root = Join-Path $env:LOCALAPPDATA "Makia\Connector"
$target = Join-Path $root "bin"
$id = [guid]::NewGuid().ToString("N")
$staging = Join-Path $root ("bin-staging-" + $id)
$backup = Join-Path $root ("bin-backup-" + $id)
$hadPrevious = Test-Path -LiteralPath $target -PathType Container
$swapped = $false
$previousMoved = $false

New-Item -ItemType Directory -Force -Path $root | Out-Null
try {
  New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null
  foreach ($name in $names) {
    $src = Join-Path $sourcePath $name
    $dest = Join-Path $staging $name
    Copy-Item -LiteralPath $src -Destination $dest -ErrorAction Stop
    if ((Get-ConnectorSha256 $src) -ne (Get-ConnectorSha256 $dest)) {
      throw "Staged $name did not match the package checksum."
    }
  }

  $connector = Join-Path $target "MakiaClientConnector.exe"
  $runtime = Join-Path $target "sing-box.exe"
  $wstunnel = Join-Path $target "wstunnel.exe"
  $state = @{
    version = $version
    mode = "full-device"
    connector = $connector
    runtime = $runtime
    wstunnel = $wstunnel
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
  } | ConvertTo-Json -Depth 3
  [System.IO.File]::WriteAllText(
    (Join-Path $staging "install-state.json"),$state,
    (New-Object System.Text.UTF8Encoding($false))
  )

  if ($hadPrevious) {
    Move-Item -LiteralPath $target -Destination $backup -ErrorAction Stop
    $previousMoved = $true
  }
  Move-Item -LiteralPath $staging -Destination $target -ErrorAction Stop
  $swapped = $true

  foreach ($path in @($connector,$runtime,$wstunnel)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
      throw "Makia Windows installation incomplete."
    }
  }

  # Register the per-user makia:// launcher used by the Client Portal.
  $base = "HKCU:\Software\Classes\makia"
  New-Item -Force -Path $base | Out-Null
  Set-Item -Path $base -Value "URL:Makia Client Connector"
  New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
  New-Item -Force -Path "$base\DefaultIcon" | Out-Null
  Set-Item -Path "$base\DefaultIcon" -Value ('"' + $connector + '",0')
  New-Item -Force -Path "$base\shell\open\command" | Out-Null
  Set-Item -Path "$base\shell\open\command" -Value ('"' + $connector + '" "%1"')
  $registered = (Get-Item "$base\shell\open\command").GetValue("")
  if ([string]::IsNullOrWhiteSpace($registered) -or
      !$registered.Contains("MakiaClientConnector.exe") -or
      !$registered.Contains("%1")) {
    throw "makia:// registration failed"
  }
} catch {
  if ($swapped -and (Test-Path -LiteralPath $target)) {
    Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
  }
  if ($previousMoved -and (Test-Path -LiteralPath $backup)) {
    Move-Item -LiteralPath $backup -Destination $target -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
  }
  throw
}

Write-Host ""
Write-Host "Makia Windows Full Device Connector $version installed successfully." -ForegroundColor Green
Write-Host "Connector: $connector"
Write-Host "Runtime: $runtime"
Write-Host "WStunnel: $wstunnel"
if ($previousMoved) { Write-Host "Previous installation retained for rollback: $backup" }
Write-Host "Browser-only users do not need this package; use the Makia Browser VPN extension instead." -ForegroundColor Yellow

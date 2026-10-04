# Makia Windows Full Device Connector 1.5.1 installer.
param([string]$SourceDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
New-Item -ItemType Directory -Force -Path $target | Out-Null

foreach ($name in @("MakiaClientConnector.exe","sing-box.exe")) {
  $src = Join-Path $SourceDir $name
  if (!(Test-Path $src)) { throw "Missing $name in package" }
  Copy-Item -Force $src (Join-Path $target $name)
}

$connector = Join-Path $target "MakiaClientConnector.exe"
$runtime = Join-Path $target "sing-box.exe"

# Register the per-user makia:// launcher used by the authenticated Client Portal.
$base = "HKCU:\Software\Classes\makia"
New-Item -Force -Path $base | Out-Null
Set-Item -Path $base -Value "URL:Makia Client Connector"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Force -Path "$base\DefaultIcon" | Out-Null
Set-Item -Path "$base\DefaultIcon" -Value ('"' + $connector + '",0')
New-Item -Force -Path "$base\shell\open\command" | Out-Null
Set-Item -Path "$base\shell\open\command" -Value ('"' + $connector + '" "%1"')

foreach ($path in @($connector,$runtime)) {
  if (!(Test-Path $path)) { throw "Makia Windows installation missing: $path" }
}
$registered = (Get-Item "$base\shell\open\command").GetValue("")
if ([string]::IsNullOrWhiteSpace($registered) -or !$registered.Contains("MakiaClientConnector.exe")) {
  throw "makia:// registration failed"
}

$state = @{
  version = "1.5.1"
  mode = "full-device"
  connector = $connector
  runtime = $runtime
  installed_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText((Join-Path $target "install-state.json"),$state,(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Makia Windows Full Device Connector 1.5.1 installed successfully." -ForegroundColor Green
Write-Host "Connector: $connector"
Write-Host "Runtime: $runtime"
Write-Host "Browser VPN users do not need this package; use the Makia Browser VPN extension instead." -ForegroundColor Yellow

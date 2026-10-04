# Makia Client Connector per-user installer.
param([string]$SourceDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
New-Item -ItemType Directory -Force -Path $target | Out-Null

foreach ($name in @("MakiaClientConnector.exe","MakiaBrowserHost.exe","sing-box.exe")) {
  $src = Join-Path $SourceDir $name
  if (!(Test-Path $src)) { throw "Missing $name in package" }
  Copy-Item -Force $src (Join-Path $target $name)
}

$connector = Join-Path $target "MakiaClientConnector.exe"
$browserHost = Join-Path $target "MakiaBrowserHost.exe"

# makia:// protocol for Full Device Direct Connect.
$base = "HKCU:\Software\Classes\makia"
New-Item -Force -Path $base | Out-Null
Set-Item -Path $base -Value "URL:Makia Client Connector"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Force -Path "$base\DefaultIcon" | Out-Null
Set-Item -Path "$base\DefaultIcon" -Value ('"' + $connector + '",0')
New-Item -Force -Path "$base\shell\open\command" | Out-Null
Set-Item -Path "$base\shell\open\command" -Value ('"' + $connector + '" "%1"')

# Chrome/Edge Native Messaging host for browser-only VPN.
$hostName = "com.makia.browser_host"
$extensionId = "jgpmmenelldgfmjfnonhjaaaccfeniji"
$hostManifest = Join-Path $target "$hostName.json"
$manifest = @{
  name = $hostName
  description = "Makia Browser VPN Native Host"
  path = $browserHost
  type = "stdio"
  allowed_origins = @("chrome-extension://$extensionId/")
} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($hostManifest,$manifest,(New-Object System.Text.UTF8Encoding($false)))

foreach ($key in @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$hostName",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$hostName"
)) {
  New-Item -Force -Path $key | Out-Null
  Set-Item -Path $key -Value $hostManifest
}

if (!(Test-Path $connector) -or !(Test-Path $browserHost)) { throw "Makia connector installation failed" }
$registered = (Get-Item "$base\shell\open\command").GetValue("")
if ([string]::IsNullOrWhiteSpace($registered) -or !$registered.Contains("MakiaClientConnector.exe")) {
  throw "makia:// registration failed"
}

Write-Host "Makia Client Connector 1.4.1 installed successfully."
Write-Host "Full-device connector: $connector"
Write-Host "Browser native host: $browserHost"
Write-Host "Chrome/Edge native messaging host registered for extension $extensionId"

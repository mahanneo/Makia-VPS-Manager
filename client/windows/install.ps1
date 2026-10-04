# Makia Client Connector 1.4.2 installer.
# Machine scope is preferred so Chrome/Edge can resolve the Native Messaging
# host regardless of UAC/user-registry context. User-scope fallback remains
# available for locked-down PCs.
param(
  [string]$SourceDir = $PSScriptRoot,
  [ValidateSet("Machine","User")]
  [string]$Scope = "Machine"
)

$ErrorActionPreference = "Stop"
$hostName = "com.makia.browser_host"
$extensionId = "jgpmmenelldgfmjfnonhjaaaccfeniji"
$allowedOrigin = "chrome-extension://$extensionId/"

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($Scope -eq "Machine" -and -not (Test-IsAdministrator)) {
  Write-Host "Administrator permission is required for reliable Chrome/Edge registration."
  $argList = @(
    "-NoProfile",
    "-ExecutionPolicy","Bypass",
    "-File",('"' + $PSCommandPath + '"'),
    "-SourceDir",('"' + $SourceDir + '"'),
    "-Scope","Machine"
  )
  $proc = Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -PassThru -ArgumentList $argList
  exit $proc.ExitCode
}

if ($Scope -eq "Machine") {
  $target = Join-Path $env:ProgramFiles "Makia\Connector\bin"
} else {
  $target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
}
New-Item -ItemType Directory -Force -Path $target | Out-Null

foreach ($name in @("MakiaClientConnector.exe","MakiaBrowserHost.exe","sing-box.exe")) {
  $src = Join-Path $SourceDir $name
  if (!(Test-Path $src)) { throw "Missing $name in package" }
  Copy-Item -Force $src (Join-Path $target $name)
}

$connector = Join-Path $target "MakiaClientConnector.exe"
$browserHost = Join-Path $target "MakiaBrowserHost.exe"
$singBox = Join-Path $target "sing-box.exe"

# Register makia:// for the current user. This keeps Direct Connect predictable
# without taking ownership of system-wide URL handlers.
$base = "HKCU:\Software\Classes\makia"
New-Item -Force -Path $base | Out-Null
Set-Item -Path $base -Value "URL:Makia Client Connector"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Force -Path "$base\DefaultIcon" | Out-Null
Set-Item -Path "$base\DefaultIcon" -Value ('"' + $connector + '",0')
New-Item -Force -Path "$base\shell\open\command" | Out-Null
Set-Item -Path "$base\shell\open\command" -Value ('"' + $connector + '" "%1"')

# Native Messaging manifest. UTF-8 without BOM is intentional.
$hostManifest = Join-Path $target "$hostName.json"
$manifest = @{
  name = $hostName
  description = "Makia Browser VPN Native Host"
  path = $browserHost
  type = "stdio"
  allowed_origins = @($allowedOrigin)
} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($hostManifest,$manifest,(New-Object System.Text.UTF8Encoding($false)))

function Register-NativeHostKey([string]$key) {
  New-Item -Force -Path $key | Out-Null
  Set-Item -Path $key -Value $hostManifest
}

# Always register for the current user.
$userKeys = @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$hostName",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$hostName"
)
foreach ($key in $userKeys) { Register-NativeHostKey $key }

# Machine registration fixes the common case where the package was installed
# from an elevated/admin context but Chrome is running under a different token.
$machineKeys = @()
if ($Scope -eq "Machine") {
  $machineKeys = @(
    "HKLM:\Software\Google\Chrome\NativeMessagingHosts\$hostName",
    "HKLM:\Software\Microsoft\Edge\NativeMessagingHosts\$hostName",
    "HKLM:\Software\WOW6432Node\Google\Chrome\NativeMessagingHosts\$hostName",
    "HKLM:\Software\WOW6432Node\Microsoft\Edge\NativeMessagingHosts\$hostName"
  )
  foreach ($key in $machineKeys) { Register-NativeHostKey $key }
}

# Self-test the installed executable and manifest before reporting success.
foreach ($path in @($connector,$browserHost,$singBox,$hostManifest)) {
  if (!(Test-Path $path)) { throw "Makia installation missing: $path" }
}
$hostConfig = Get-Content $hostManifest -Raw | ConvertFrom-Json
if ($hostConfig.name -ne $hostName) { throw "Native host manifest name mismatch" }
if ($hostConfig.path -ne $browserHost) { throw "Native host manifest executable path mismatch" }
if ($hostConfig.allowed_origins.Count -ne 1 -or $hostConfig.allowed_origins[0] -ne $allowedOrigin) {
  throw "Native host extension allowlist mismatch"
}

$nativeProbeRaw = & $browserHost --self-test
if ($LASTEXITCODE -ne 0) { throw "MakiaBrowserHost self-test failed" }
$nativeProbe = $nativeProbeRaw | ConvertFrom-Json
if (!$nativeProbe.ok -or !$nativeProbe.sing_box) { throw "MakiaBrowserHost runtime self-test failed" }

foreach ($key in $userKeys) {
  $value = (Get-Item $key).GetValue("")
  if ($value -ne $hostManifest -or !(Test-Path $value)) { throw "Native Messaging user registration invalid: $key" }
}
foreach ($key in $machineKeys) {
  $value = (Get-Item $key).GetValue("")
  if ($value -ne $hostManifest -or !(Test-Path $value)) { throw "Native Messaging machine registration invalid: $key" }
}

$registered = (Get-Item "$base\shell\open\command").GetValue("")
if ([string]::IsNullOrWhiteSpace($registered) -or !$registered.Contains("MakiaClientConnector.exe")) {
  throw "makia:// registration failed"
}

$state = @{
  version = "1.4.2"
  scope = $Scope
  extension_id = $extensionId
  native_host = $browserHost
  manifest = $hostManifest
  installed_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText((Join-Path $target "install-state.json"),$state,(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Makia Client Connector 1.4.2 installed successfully." -ForegroundColor Green
Write-Host "Scope: $Scope"
Write-Host "Full-device connector: $connector"
Write-Host "Browser native host: $browserHost"
Write-Host "Extension ID: $extensionId"
Write-Host ""
Write-Host "IMPORTANT: Close ALL Chrome/Edge windows and reopen the browser before testing Browser VPN." -ForegroundColor Yellow

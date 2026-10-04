# Makia Client Connector per-user installer; registers makia:// and the Chromium Native Messaging host.
param(
  [string]$SourceDir = $PSScriptRoot,
  [string]$ChromeExtensionId = "",
  [string]$EdgeExtensionId = ""
)

$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
New-Item -ItemType Directory -Force -Path $target | Out-Null

foreach ($name in @("MakiaClientConnector.exe","MakiaBrowserHost.exe","sing-box.exe")) {
  $src = Join-Path $SourceDir $name
  if (!(Test-Path $src)) { throw "Missing $name in package" }
  Copy-Item -Force $src (Join-Path $target $name)
}

$exe = Join-Path $target "MakiaClientConnector.exe"
$browserHost = Join-Path $target "MakiaBrowserHost.exe"
$base = "HKCU:\Software\Classes\makia"
New-Item -Force -Path $base | Out-Null
Set-Item -Path $base -Value "URL:Makia Client Connector"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Force -Path "$base\DefaultIcon" | Out-Null
Set-Item -Path "$base\DefaultIcon" -Value ('"' + $exe + '",0')
New-Item -Force -Path "$base\shell\open\command" | Out-Null
Set-Item -Path "$base\shell\open\command" -Value ('"' + $exe + '" "%1"')

if (!(Test-Path $exe)) { throw "Connector executable was not installed" }
if (!(Test-Path $browserHost)) { throw "Browser Host executable was not installed" }
$registered = (Get-Item "$base\shell\open\command").GetValue("")
if ([string]::IsNullOrWhiteSpace($registered) -or !$registered.Contains("MakiaClientConnector.exe")) {
  throw "makia:// registration failed"
}

# Stable unpacked/UAT extension ID derived from the public manifest key.
$devExtensionId = "kifidlpkeejegkcolpjfipmjllldakik"
$allowedIds = New-Object System.Collections.Generic.List[string]
$allowedIds.Add($devExtensionId)
foreach ($candidate in @($ChromeExtensionId,$EdgeExtensionId)) {
  $value = [string]$candidate
  if ([string]::IsNullOrWhiteSpace($value)) { continue }
  $value = $value.Trim().ToLowerInvariant()
  if ($value -notmatch '^[a-p]{32}$') { throw "Invalid Chromium extension ID: $value" }
  if (!$allowedIds.Contains($value)) { $allowedIds.Add($value) }
}
$origins = @($allowedIds | ForEach-Object { "chrome-extension://$_/" })
$manifestPath = Join-Path $target "com.makia.client.browser.json"
$nativeManifest = [ordered]@{
  name = "com.makia.client.browser"
  description = "Makia secure browser bridge"
  path = $browserHost
  type = "stdio"
  allowed_origins = $origins
}
$manifestJson = $nativeManifest | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($manifestPath,$manifestJson,(New-Object System.Text.UTF8Encoding($false)))

foreach ($registryPath in @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.makia.client.browser",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.makia.client.browser"
)) {
  New-Item -Force -Path $registryPath | Out-Null
  Set-Item -Path $registryPath -Value $manifestPath
  $value = (Get-Item $registryPath).GetValue("")
  if ($value -ne $manifestPath) { throw "Native Messaging registration failed: $registryPath" }
}

$parsed = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($parsed.name -ne "com.makia.client.browser") { throw "Native Messaging manifest is invalid" }
if ($parsed.path -ne $browserHost) { throw "Native Messaging executable path is invalid" }
if (@($parsed.allowed_origins) -notcontains ("chrome-extension://" + $devExtensionId + "/")) {
  throw "Native Messaging UAT extension origin is missing"
}

Write-Host "Makia Client Connector installed successfully."
Write-Host "Installed at: $target"
Write-Host "Direct Connect is registered as makia://"
Write-Host "Chrome/Edge Native Messaging host registered: com.makia.client.browser"
Write-Host "UAT extension ID: $devExtensionId"

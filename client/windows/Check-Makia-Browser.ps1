param([switch]$Quiet)

$ErrorActionPreference = "Stop"
$hostName = "com.makia.browser_host"
$extensionId = "jgpmmenelldgfmjfnonhjaaaccfeniji"
$expectedOrigin = "chrome-extension://$extensionId/"
$keys = @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$hostName",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$hostName",
  "HKLM:\Software\Google\Chrome\NativeMessagingHosts\$hostName",
  "HKLM:\Software\Microsoft\Edge\NativeMessagingHosts\$hostName",
  "HKLM:\Software\WOW6432Node\Google\Chrome\NativeMessagingHosts\$hostName",
  "HKLM:\Software\WOW6432Node\Microsoft\Edge\NativeMessagingHosts\$hostName"
)

$found = @()
$errors = @()
foreach ($key in $keys) {
  if (Test-Path $key) {
    try {
      $manifestPath = (Get-Item $key).GetValue("")
      if ([string]::IsNullOrWhiteSpace($manifestPath)) { throw "empty registry value" }
      if (!(Test-Path $manifestPath)) { throw "manifest file missing: $manifestPath" }
      $cfg = Get-Content $manifestPath -Raw | ConvertFrom-Json
      if ($cfg.name -ne $hostName) { throw "manifest host name mismatch" }
      if (!(Test-Path $cfg.path)) { throw "native host executable missing: $($cfg.path)" }
      if ($cfg.allowed_origins.Count -ne 1 -or $cfg.allowed_origins[0] -ne $expectedOrigin) {
        throw "extension allowlist mismatch"
      }
      $probeRaw = & $cfg.path --self-test
      if ($LASTEXITCODE -ne 0) { throw "native host self-test failed" }
      $probe = $probeRaw | ConvertFrom-Json
      if (!$probe.ok -or !$probe.sing_box) { throw "native host/sing-box self-test failed" }
      $found += [pscustomobject]@{Key=$key;Manifest=$manifestPath;Host=$cfg.path}
    } catch {
      $errors += "$key :: $($_.Exception.Message)"
    }
  }
}

if ($found.Count -eq 0) {
  Write-Host "Makia Browser Host: NOT REGISTERED" -ForegroundColor Red
  Write-Host "Run Repair-Makia-Browser.cmd from the Makia 1.4.2 Windows package." -ForegroundColor Yellow
  exit 2
}
if ($errors.Count -gt 0) {
  Write-Host "Makia Browser Host: REGISTRATION ERRORS" -ForegroundColor Red
  $errors | ForEach-Object { Write-Host " - $_" }
  exit 3
}

if (!$Quiet) {
  Write-Host "Makia Browser Host: PASS" -ForegroundColor Green
  Write-Host "Extension ID: $extensionId"
  foreach ($item in $found) {
    Write-Host " - $($item.Key)"
    Write-Host "   $($item.Manifest)"
  }
  Write-Host "Close every Chrome/Edge window and reopen the browser before testing."
}
exit 0

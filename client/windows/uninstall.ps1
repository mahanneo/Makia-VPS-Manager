$ErrorActionPreference = "SilentlyContinue"

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
  $proc = Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -PassThru -ArgumentList @(
    "-NoProfile","-ExecutionPolicy","Bypass","-File",('"' + $PSCommandPath + '"')
  )
  exit $proc.ExitCode
}

$roots = @(
  (Join-Path $env:ProgramFiles "Makia\Connector"),
  (Join-Path $env:LOCALAPPDATA "Makia\Connector")
)
foreach ($root in $roots) {
  $connector = Join-Path $root "bin\MakiaClientConnector.exe"
  if (Test-Path $connector) {
    & $connector --browser-disconnect | Out-Null
    & $connector --disconnect | Out-Null
  }
}

Remove-Item -Recurse -Force "HKCU:\Software\Classes\makia"
foreach ($key in @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.makia.browser_host",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.makia.browser_host",
  "HKLM:\Software\Google\Chrome\NativeMessagingHosts\com.makia.browser_host",
  "HKLM:\Software\Microsoft\Edge\NativeMessagingHosts\com.makia.browser_host",
  "HKLM:\Software\WOW6432Node\Google\Chrome\NativeMessagingHosts\com.makia.browser_host",
  "HKLM:\Software\WOW6432Node\Microsoft\Edge\NativeMessagingHosts\com.makia.browser_host"
)) {
  Remove-Item -Recurse -Force $key
}

foreach ($root in $roots) {
  Remove-Item -Recurse -Force (Join-Path $root "bin")
}
Write-Host "Makia Client Connector and Browser Native Host removed."

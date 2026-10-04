$ErrorActionPreference = "SilentlyContinue"
$root = "$env:LOCALAPPDATA\Makia\Connector"
$connector = "$root\bin\MakiaClientConnector.exe"

if (Test-Path $connector) {
  & $connector --disconnect | Out-Null
}

Remove-Item -Recurse -Force "HKCU:\Software\Classes\makia"
Remove-Item -Recurse -Force "$root\bin"
Write-Host "Makia Windows Full Device Connector removed."

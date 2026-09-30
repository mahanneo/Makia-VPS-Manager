$ErrorActionPreference = "SilentlyContinue"
& "$env:LOCALAPPDATA\Makia\Connector\bin\MakiaClientConnector.exe" --disconnect | Out-Null
Remove-Item -Recurse -Force "HKCU:\Software\Classes\makia"
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Makia\Connector\bin"
Write-Host "Makia Client Connector removed."

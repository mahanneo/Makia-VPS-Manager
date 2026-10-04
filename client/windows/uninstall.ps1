$ErrorActionPreference = "SilentlyContinue"

& "$env:LOCALAPPDATA\Makia\Connector\bin\MakiaClientConnector.exe" --disconnect | Out-Null

Remove-Item -Recurse -Force "HKCU:\Software\Classes\makia"
Remove-Item -Recurse -Force "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.makia.client.browser"
Remove-Item -Recurse -Force "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.makia.client.browser"

Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Makia\BrowserHost"
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Makia\Connector\bin"

Write-Host "Makia Client Connector and Browser Host removed."
Write-Host "If the unpacked Makia VPN extension is still loaded, remove it from Chrome/Edge Extensions."

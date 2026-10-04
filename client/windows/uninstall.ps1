$ErrorActionPreference = "SilentlyContinue"
$root = "$env:LOCALAPPDATA\Makia\Connector"
& "$root\bin\MakiaBrowserHost.exe" --native-host 2>$null | Out-Null
& "$root\bin\MakiaClientConnector.exe" --disconnect | Out-Null
Remove-Item -Recurse -Force "HKCU:\Software\Classes\makia"
Remove-Item -Recurse -Force "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.makia.browser_host"
Remove-Item -Recurse -Force "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.makia.browser_host"
Remove-Item -Recurse -Force "$root\bin"
Write-Host "Makia Client Connector and Browser Native Host removed."

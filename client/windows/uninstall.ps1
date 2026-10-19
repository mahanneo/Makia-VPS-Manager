$ErrorActionPreference = "SilentlyContinue"
$root = "$env:LOCALAPPDATA\Makia\Connector"
$connector = "$root\bin\MakiaClientConnector.exe"

if (Test-Path $connector) {
  & $connector --disconnect | Out-Null
}

# Delete only shortcuts that still point to this Makia installation.
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @(
  (Join-Path ([Environment]::GetFolderPath("Programs")) "Makia Desktop.lnk"),
  (Join-Path ([Environment]::GetFolderPath("Desktop")) "Makia Desktop.lnk")
)) {
  if (Test-Path $shortcutPath) {
    try {
      $lnk = $shell.CreateShortcut($shortcutPath)
      $expected = Join-Path $root "bin\MakiaDesktop.exe"
      if ($lnk.TargetPath -eq $expected) { Remove-Item -LiteralPath $shortcutPath -Force }
    } catch { }
  }
}
Remove-Item -Recurse -Force "HKCU:\Software\Classes\makia"
Remove-Item -Recurse -Force "$root\bin"
# Uninstall deletes the locally saved DPAPI bearer session as well.
Remove-Item -LiteralPath (Join-Path $env:LOCALAPPDATA "Makia\Desktop\device.json") -Force -ErrorAction SilentlyContinue
Write-Host "Makia Desktop and Full Device Connector removed. Local saved sign-in was removed; revoke this device in Makia Client if another copy remains."

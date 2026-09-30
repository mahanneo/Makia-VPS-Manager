param([string]$SourceDir = $PSScriptRoot)
$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Makia\Connector\bin"
New-Item -ItemType Directory -Force -Path $target | Out-Null
foreach ($name in @("MakiaClientConnector.exe","sing-box.exe")) {
  $src = Join-Path $SourceDir $name
  if (!(Test-Path $src)) { throw "Missing $name in package" }
  Copy-Item -Force $src (Join-Path $target $name)
}
$exe = Join-Path $target "MakiaClientConnector.exe"
$base = "HKCU:\Software\Classes\makia"
New-Item -Force -Path $base | Out-Null
Set-ItemProperty -Path $base -Name "(default)" -Value "URL:Makia Client Connector"
Set-ItemProperty -Path $base -Name "URL Protocol" -Value ""
New-Item -Force -Path "$base\DefaultIcon" | Out-Null
Set-ItemProperty -Path "$base\DefaultIcon" -Name "(default)" -Value ('"' + $exe + '",0')
New-Item -Force -Path "$base\shell\open\command" | Out-Null
Set-ItemProperty -Path "$base\shell\open\command" -Name "(default)" -Value ('"' + $exe + '" "%1"')
Write-Host "Makia Client Connector installed."
Write-Host "Direct Connect is now registered as makia://"

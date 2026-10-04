@echo off
setlocal
title Makia Browser VPN Repair
echo.
echo Repairing Makia Browser VPN native host...
echo This may request Administrator permission.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -SourceDir "%~dp0" -Scope Machine
if errorlevel 1 (
  echo.
  echo Repair failed. Keep this window open and copy the error above.
  pause
  exit /b 1
)
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Check-Makia-Browser.ps1"
if errorlevel 1 (
  echo.
  echo Browser host verification failed.
  pause
  exit /b 1
)
echo.
echo Repair completed. Close ALL Chrome and Edge windows, then reopen the browser.
pause

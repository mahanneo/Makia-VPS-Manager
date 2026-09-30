@echo off
setlocal
title Makia Client Connector Uninstaller
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
if errorlevel 1 (
  echo.
  echo Uninstall reported an error.
  pause
  exit /b 1
)
echo.
echo Makia Client Connector removed.
pause

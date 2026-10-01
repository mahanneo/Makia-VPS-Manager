@echo off
setlocal
title Makia Client Connector Installer
echo Installing Makia Client Connector...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -SourceDir "%~dp0"
if errorlevel 1 (
  echo.
  echo Installation failed. Keep this window open and copy the error message.
  pause
  exit /b 1
)
echo.
echo Installation completed successfully.
pause

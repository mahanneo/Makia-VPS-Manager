@echo off
setlocal
title Makia Client Connector Installer
echo Installing Makia Client Connector...
rem The installer detects its own directory. Do not forward %~dp0 as a quoted
rem argument: its trailing backslash can swallow the closing quote on Windows.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed. Keep this window open and copy the error message.
  if not defined MAKIA_INSTALL_NONINTERACTIVE pause
  exit /b 1
)
echo.
echo Installation completed successfully.
if not defined MAKIA_INSTALL_NONINTERACTIVE pause

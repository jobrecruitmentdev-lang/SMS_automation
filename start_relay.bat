@echo off
title JobRecruitment Cloud-to-Phone Relay Daemon
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo      Starting JobRecruitment Cloud-to-Phone Relay Daemon...
echo ==============================================================================

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python not found! Please install Python 3 from https://www.python.org/
    pause
    exit /b 1
)

:: Auto-create start_relay.py if missing in the current directory
if not exist "%~dp0start_relay.py" (
    echo [*] Fetching latest Relay Agent engine from Render Cloud...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://sms-automation-q1zf.onrender.com/download/start_relay.py', '%~dp0start_relay.py')"
)

set "PATH=%~dp0platform-tools;%PATH%"

python start_relay.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Relay stopped.
    pause
)

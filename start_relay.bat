@echo off
title JobRecruitment Cloud-to-Phone Relay Daemon
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo      Starting JobRecruitment Cloud-to-Phone Relay Daemon...
echo ==============================================================================

:: 1. Smart Multi-Path Python Detection
set "PY_CMD="

:: Check standard python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PY_CMD=python"

:: Check py launcher
if not defined PY_CMD (
    py --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PY_CMD=py"
)

:: Search LocalAppData Python installations
if not defined PY_CMD (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
)

:: Search ProgramFiles Python installations
if not defined PY_CMD (
    for /d %%D in ("%ProgramFiles%\Python*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
)

if not defined PY_CMD (
    echo.
    echo ==============================================================================
    echo  [!] PYTHON NOT FOUND ON THIS SYSTEM!
    echo ==============================================================================
    echo  Please install Python 3 (Tick "Add python.exe to PATH" during installation)
    echo  Download link: https://www.python.org/downloads/
    echo ==============================================================================
    echo.
    pause
    exit /b 1
)

:: 2. Always ensure latest Relay Agent engine from Render Cloud
echo [*] Checking latest Relay Agent engine from Render Cloud...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://sms-automation-q1zf.onrender.com/download/start_relay.py', '%~dp0start_relay.py')" >nul 2>&1

set "PATH=%~dp0platform-tools;%PATH%"

%PY_CMD% start_relay.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Relay stopped.
    pause
)

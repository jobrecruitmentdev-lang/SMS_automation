@echo off
title JobRecruitment SMS Automation — 1-Click Automated Setup
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo      JobRecruitment SMS Automation — 1-Click Automated Setup
echo ==============================================================================
echo.

:: 1. Check Python Installation
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.9+ from https://www.python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo [1/4] Python is installed:
python --version
echo.

:: 2. Install / Upgrade Dependencies
echo [2/4] Installing lightweight dependencies (requests, python-dotenv, colorama)...
pip install -r requirements.txt --quiet --upgrade
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Pip install had warnings, trying standard install...
    pip install requests python-dotenv colorama
)
echo      [OK] Dependencies verified.
echo.

:: 3. Setup .env file
echo [3/4] Checking Environment Configuration (.env)...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo      [OK] Created new .env from template.
    ) else (
        echo      [WARNING] .env.example missing, creating fresh .env...
        (
            echo WORKER_API_URL=https://jobrecruitment.in/backend/api/worker-api.php
            echo WORKER_API_KEY=
            echo GROQ_API_KEY=
            echo GEMINI_API_KEY=
            echo SMS_MODE=adb
            echo ANDROID_GATEWAY_URL=http://192.168.1.100:8080/send
            echo DAILY_SMS_LIMIT=180
            echo DISPATCH_DELAY_SECONDS=5
        ) > .env
    )
) else (
    echo      [OK] .env configuration file exists.
)
echo.

:: 4. Check & Auto-Install Android ADB
echo [4/4] Checking Android ADB Platform-Tools...
set "ADB_EXE=adb"
adb version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%~dp0platform-tools\adb.exe" (
        set "ADB_EXE=%~dp0platform-tools\adb.exe"
        echo      [OK] Portable ADB found in local directory.
    ) else (
        echo      [DOWNLOADING] Portable Google ADB Platform-Tools (~12MB)...
        curl.exe -L "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -o "%~dp0platform-tools.zip" --progress-bar
        if %ERRORLEVEL% EQU 0 (
            echo      [EXTRACTING] Unpacking ADB binaries...
            tar.exe -xf "%~dp0platform-tools.zip" -C "%~dp0"
            del "%~dp0platform-tools.zip" >nul 2>&1
            if exist "%~dp0platform-tools\adb.exe" (
                set "ADB_EXE=%~dp0platform-tools\adb.exe"
                echo      [OK] Portable ADB installed successfully!
            )
        ) else (
            echo      [WARNING] Could not download ADB automatically. If using USB dispatch, install ADB manually or switch SMS_MODE=http in .env.
        )
    )
) else (
    echo      [OK] System ADB found in PATH.
)

:: Test connected devices
echo.
echo Checking connected Android devices:
"%ADB_EXE%" devices
echo.
echo [TIP] For ADB Mode: Connect Android phone via USB and enable "USB Debugging" in Developer Options.
echo       When prompted on phone, tap "Always allow from this computer".
echo.

echo ==============================================================================
echo  🎉 Setup Complete! You can now run either:
echo     1. start_ui.bat  -- To launch the Web Dashboard (http://localhost:8050)
echo     2. run.bat       -- To launch the Terminal CLI Engine
echo ==============================================================================
echo.
pause

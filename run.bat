@echo off
title JobRecruitment AI SMS Automation Engine
color 0b
cd /d "%~dp0"
set "PATH=%~dp0platform-tools;%PATH%"

echo ==============================================================================
echo      Starting JobRecruitment AI SMS Engine...
echo ==============================================================================
python sms_engine.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Execution stopped. If dependencies are missing, run:
    echo setup.bat
    echo.
    pause
)

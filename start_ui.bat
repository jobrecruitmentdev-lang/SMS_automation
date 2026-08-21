@echo off
title JobRecruitment AI SMS Studio (Web UI)
color 0a
cd /d "%~dp0"
set "PATH=%~dp0platform-tools;%PATH%"
set "PORT=8050"

echo ==============================================================================
echo      Starting JobRecruitment AI SMS Web Studio...
echo ==============================================================================

start "" http://localhost:8050
python sms_studio.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] SMS Studio stopped.
    pause
)

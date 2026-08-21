import os
from fastapi import APIRouter, Response, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from app.core.config import BASE_DIR, settings

router = APIRouter(tags=["System & Static Downloads"])

@router.get("/api/health_check")
@router.get("/healthz")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME, "version": settings.VERSION}

import time

SERVER_START_TIME = time.time()

@router.get("/api/server_version")
def server_version():
    index_mtime = 0
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        index_mtime = os.path.getmtime(index_path)
    return {
        "version": settings.VERSION,
        "service": "FastAPI ASGI Cloud Engine",
        "server_start_time": SERVER_START_TIME,
        "max_mtime": index_mtime
    }

@router.get("/download/android-relay-agent.bat")
def download_bat():
    bat_content = (
        "@echo off\r\n"
        "title JobRecruitment Android Relay Agent\r\n"
        "color 0A\r\n"
        "echo ====================================================\r\n"
        "echo   JobRecruitment.in - Physical Phone USB Relay Agent\r\n"
        "echo ====================================================\r\n"
        "echo.\r\n"
        "set /p CODE=Enter your Recruiter Pairing Code (e.g. JR-635287): \r\n"
        "if \"%CODE%\"==\"\" set CODE=JR-DEFAULT\r\n"
        "echo [*] Registering Phone to Cloud Engine with Code: %CODE%...\r\n"
        "curl -s -X POST https://sms.jobrecruitment.in/api/gateway/register -H \"Content-Type: application/json\" -d \"{\\\"pairing_code\\\":\\\"%CODE%\\\",\\\"device_name\\\":\\\"USB Relay Phone\\\"}\"\r\n"
        "echo.\r\n"
        "echo [OK] Phone Connected! Keeping Relay Alive. Do NOT close this window.\r\n"
        ":loop\r\n"
        "timeout /t 10 >nul\r\n"
        "curl -s -X POST https://sms.jobrecruitment.in/api/gateway/heartbeat -H \"Content-Type: application/json\" -d \"{\\\"pairing_code\\\":\\\"%CODE%\\\",\\\"battery\\\":\\\"100%\\\"}\" >nul\r\n"
        "goto loop\r\n"
    )
    return Response(
        content=bat_content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=android-relay-agent.bat"}
    )

@router.get("/download/JobRecruitment-Gateway.apk")
@router.get("/download/jobrecruitment-companion.apk")
@router.get("/download/app.apk")
@router.get("/download/gateway.apk")
def download_apk():
    for fname in ["JobRecruitment-Gateway.apk", "jobrecruitment-companion.apk", "app-release.apk"]:
        apk_path = os.path.join(BASE_DIR, fname)
        if os.path.exists(apk_path):
            return FileResponse(apk_path, media_type="application/vnd.android.package-archive", filename="JobRecruitment-Gateway.apk")
        sub_path = os.path.join(BASE_DIR, "android_gateway_app", fname)
        if os.path.exists(sub_path):
            return FileResponse(sub_path, media_type="application/vnd.android.package-archive", filename="JobRecruitment-Gateway.apk")
    return Response(
        content=b"JobRecruitment Companion APK Build v3.0",
        media_type="application/vnd.android.package-archive",
        headers={"Content-Disposition": "attachment; filename=JobRecruitment-Gateway.apk"}
    )

@router.get("/", response_class=HTMLResponse)
def serve_index_view():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>JobRecruitment SMS Studio API v3.0</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")

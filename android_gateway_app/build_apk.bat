@echo off
echo =======================================================================
echo   JobRecruitment - Android SMS Gateway Companion APK Builder
echo =======================================================================
echo.

where gradle >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [*] Building Android APK via Gradle...
    gradle assembleRelease
    goto done
)

echo [!] Note: To compile this Android App into an APK (.apk):
echo     1. Open the 'android_gateway_app' folder in Android Studio.
echo     2. Or run: gradlew assembleRelease
echo.
:done
pause

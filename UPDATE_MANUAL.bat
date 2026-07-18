@echo off
setlocal enabledelayedexpansion
title Command Centre Pro -- Manual Updater

echo.
echo  ============================================================
echo   COMMAND CENTRE PRO -- MANUAL UPDATER
echo  ============================================================
echo.
echo  Use this if the automatic URL download did not work.
echo.
echo  INSTRUCTIONS:
echo  1. Download the new CommandCentrePro.exe manually
echo     (open the link in your browser and save the file)
echo  2. Rename the downloaded file to: CommandCentrePro_new.exe
echo  3. Place it in the SAME folder as this bat file
echo  4. Run this bat file
echo.
echo  ============================================================
echo.

if not exist "CommandCentrePro.exe" (
    echo  [ERROR] CommandCentrePro.exe not found here.
    echo          Copy this bat into the same folder as the app.
    pause & exit /b 1
)

if not exist "CommandCentrePro_new.exe" (
    echo  [ERROR] CommandCentrePro_new.exe not found.
    echo.
    echo  Please download the new version, rename it to
    echo  CommandCentrePro_new.exe and place it here, then
    echo  run this bat again.
    echo.
    pause & exit /b 1
)

:: Verify it looks like a real exe
for %%A in ("CommandCentrePro_new.exe") do set FILESIZE=%%~zA
if !FILESIZE! LSS 1000000 (
    echo  [ERROR] CommandCentrePro_new.exe is too small (!FILESIZE! bytes^).
    echo          Make sure you downloaded the full exe file.
    pause & exit /b 1
)

:: Close app if running
tasklist /FI "IMAGENAME eq CommandCentrePro.exe" 2>NUL | find /I "CommandCentrePro.exe" >NUL
if not errorlevel 1 (
    echo  Closing app...
    taskkill /F /IM "CommandCentrePro.exe" >NUL 2>&1
    timeout /t 2 /nobreak >NUL
)

:: Backup
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%T
set BACKUP_NAME=CommandCentrePro_backup_%STAMP%.exe
copy /Y "CommandCentrePro.exe" "%BACKUP_NAME%" >NUL

:: Replace
move /Y "CommandCentrePro_new.exe" "CommandCentrePro.exe" >NUL
if errorlevel 1 (
    echo  [ERROR] Could not replace. Try running as Administrator.
    pause & exit /b 1
)

echo.
echo  ============================================================
echo   UPDATE COMPLETE -- Your data is untouched.
echo   Backup saved as: %BACKUP_NAME%
echo  ============================================================
echo.

set /p LAUNCH="  Launch now? (Y/N): "
if /I "!LAUNCH!"=="Y" start "" "CommandCentrePro.exe"
echo.
pause

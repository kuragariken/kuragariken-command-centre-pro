@echo off
setlocal enabledelayedexpansion
title Command Centre Pro -- Updater

:: ================================================================
::  COMMAND CENTRE PRO -- UPDATER
:: ================================================================
set DOWNLOAD_URL=https://github.com/kuragariken/kuragariken-command-centre-pro/releases/download/v10.0/CommandCentrePro.exe
:: Next version example:
:: set DOWNLOAD_URL=https://github.com/kuragariken/kuragariken-command-centre-pro/releases/download/v10.1/CommandCentrePro.exe
:: ================================================================

:: Force working directory to folder containing this bat file
cd /d "%~dp0"

echo.
echo  ============================================================
echo   COMMAND CENTRE PRO -- UPDATER
echo  ============================================================
echo.
echo  Running from: %~dp0
echo  This will update CommandCentrePro.exe to the latest version.
echo  Your data (commands, vault, settings) is NEVER touched.
echo  Data lives in: %APPDATA%\Command Centre Pro\
echo.
echo  ============================================================
echo.

:: ── Find the exe — try both common name variants ─────────────────
set EXE_NAME=
if exist "CommandCentrePro.exe"  set EXE_NAME=CommandCentrePro.exe
if exist "commandcentrepro.exe"  set EXE_NAME=commandcentrepro.exe
if exist "Command Centre Pro.exe" set EXE_NAME=Command Centre Pro.exe
if exist "CCP.exe"               set EXE_NAME=CCP.exe

:: If still not found, search for any .exe in this folder
if "!EXE_NAME!"=="" (
    for %%F in (*.exe) do (
        if /I not "%%F"=="CommandCentrePro_new.exe" (
            if /I not "%%F"=="CommandCentrePro_backup_*.exe" (
                set EXE_NAME=%%F
            )
        )
    )
)

if "!EXE_NAME!"=="" (
    echo  [ERROR] No exe found in this folder.
    echo.
    echo  Files found here:
    dir /b "%~dp0" 2>NUL
    echo.
    echo  Make sure UPDATE.bat is in the SAME folder as
    echo  CommandCentrePro.exe and try again.
    echo.
    pause & exit /b 1
)

echo  Found exe: !EXE_NAME!
echo.

:: ── Check URL is configured ───────────────────────────────────────
if "!DOWNLOAD_URL!"=="PASTE_GITHUB_RELEASE_URL_HERE" (
    echo  [ERROR] No download URL configured.
    echo  Open UPDATE.bat in Notepad and set the DOWNLOAD_URL.
    pause & exit /b 1
)

:: ── Close app if running ──────────────────────────────────────────
echo  [1/4] Checking if app is running...
tasklist /FI "IMAGENAME eq !EXE_NAME!" 2>NUL | find /I "!EXE_NAME!" >NUL
if not errorlevel 1 (
    echo         Closing app...
    taskkill /F /IM "!EXE_NAME!" >NUL 2>&1
    timeout /t 2 /nobreak >NUL
    echo         App closed.
) else (
    echo         Not running. Good.
)
echo.

:: ── Back up current exe ───────────────────────────────────────────
echo  [2/4] Backing up current exe...
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%T
set BACKUP_NAME=CommandCentrePro_backup_%STAMP%.exe

copy /Y "!EXE_NAME!" "%BACKUP_NAME%" >NUL
if errorlevel 1 (
    echo  [ERROR] Could not create backup.
    echo          Right-click UPDATE.bat and choose Run as Administrator.
    pause & exit /b 1
)
echo         Backed up as: %BACKUP_NAME%
echo.

:: ── Download from GitHub ──────────────────────────────────────────
echo  [3/4] Downloading from GitHub...
echo         !DOWNLOAD_URL!
echo.

powershell -NoProfile -Command ^
    "try {" ^
    "  $wc = New-Object System.Net.WebClient;" ^
    "  $wc.Headers.Add('User-Agent', 'CommandCentrePro-Updater/1.0');" ^
    "  $wc.DownloadFile('!DOWNLOAD_URL!', 'CommandCentrePro_new.exe');" ^
    "  Write-Host '  Download complete.';" ^
    "} catch {" ^
    "  Write-Host ('  FAILED: ' + $_.Exception.Message);" ^
    "  exit 1;" ^
    "}"

if errorlevel 1 (
    echo.
    echo  [ERROR] Download failed.
    echo          Check internet connection and the GitHub URL.
    echo.
    copy /Y "%BACKUP_NAME%" "!EXE_NAME!" >NUL
    del "%BACKUP_NAME%" >NUL 2>&1
    del "CommandCentrePro_new.exe" >NUL 2>&1
    pause & exit /b 1
)

if not exist "CommandCentrePro_new.exe" (
    echo  [ERROR] Downloaded file not found.
    copy /Y "%BACKUP_NAME%" "!EXE_NAME!" >NUL
    pause & exit /b 1
)

:: ── Verify file is a real exe (must be over 1 MB) ─────────────────
for %%A in ("CommandCentrePro_new.exe") do set FILESIZE=%%~zA
if !FILESIZE! LSS 1000000 (
    echo  [ERROR] Downloaded file too small (!FILESIZE! bytes^).
    copy /Y "%BACKUP_NAME%" "!EXE_NAME!" >NUL
    del "CommandCentrePro_new.exe" >NUL 2>&1
    pause & exit /b 1
)

:: ── Replace exe ───────────────────────────────────────────────────
echo  [4/4] Installing update...
move /Y "CommandCentrePro_new.exe" "!EXE_NAME!" >NUL
if errorlevel 1 (
    echo  [ERROR] Could not replace the exe.
    echo          Right-click UPDATE.bat and Run as Administrator.
    echo          Backup saved as: %BACKUP_NAME%
    pause & exit /b 1
)
echo         Installed successfully.
echo.

:: ── Done ──────────────────────────────────────────────────────────
echo  ============================================================
echo   UPDATE COMPLETE
echo  ============================================================
echo.
echo   Your data is untouched.
echo   All commands, vault, settings and history are safe.
echo.
echo   Previous version backed up as:
echo   %BACKUP_NAME%
echo   (Delete once the new version is confirmed working.)
echo.
echo  ============================================================
echo.

set /p LAUNCH="  Launch Command Centre Pro now? (Y/N): "
if /I "!LAUNCH!"=="Y" start "" "!EXE_NAME!"

echo.
echo  Done. Close this window.
echo.
pause

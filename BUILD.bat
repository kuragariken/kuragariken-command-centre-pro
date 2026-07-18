@echo off
setlocal enabledelayedexpansion
echo ============================================
echo  Command Centre Pro - Build Script
echo ============================================
echo.

REM ============================================================
REM  VERSION PROMPT
REM  Whatever you type here is written into src\updater.py as
REM  APP_VERSION *before* building, so the exe's internal version
REM  always matches what you intend to release. This prevents the
REM  "updates to itself forever" bug caused by a stale APP_VERSION.
REM ============================================================
echo Enter the version you are building (e.g. 10.5).
echo This will be baked into the exe AND is the tag you must use
echo on the GitHub release.
echo.
set /p BUILDVER="  Version to build: "

if "!BUILDVER!"=="" (
    echo.
    echo ERROR: No version entered. Aborting so you don't build an
    echo        exe with the wrong version inside it.
    pause & exit /b 1
)

REM Strip a leading v/V if the user typed one (we store the bare number)
set "CLEANVER=!BUILDVER!"
if /I "!CLEANVER:~0,1!"=="v" set "CLEANVER=!CLEANVER:~1!"

echo.
echo   Building version: !CLEANVER!
echo.

REM --- Write APP_VERSION into src\updater.py -------------------
REM We write a small PowerShell script to a temp file and run it, rather
REM than inline caret-continuation (which is fragile and was erroring with
REM "filename syntax is incorrect").
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    pause & exit /b 1
)

set "VERPS=%TEMP%\ccp_setver_%RANDOM%.ps1"
>  "%VERPS%" echo $f = 'src\updater.py'
>> "%VERPS%" echo $c = Get-Content $f -Raw
>> "%VERPS%" echo $pattern = 'APP_VERSION\s*=\s*"[^"]*"'
>> "%VERPS%" echo $replacement = 'APP_VERSION = "!CLEANVER!"'
>> "%VERPS%" echo $new = [regex]::Replace^($c, $pattern, $replacement^)
>> "%VERPS%" echo Set-Content $f -Value $new -NoNewline
>> "%VERPS%" echo Write-Host "APP_VERSION set to !CLEANVER!"

powershell -NoProfile -ExecutionPolicy Bypass -File "%VERPS%"
set VERR=%errorlevel%
del /f /q "%VERPS%" >NUL 2>&1
if !VERR! NEQ 0 (
    echo ERROR: Could not update APP_VERSION. Aborting.
    pause & exit /b 1
)

REM Confirm what actually landed in the file
echo.
echo   Verifying APP_VERSION in source:
set "CHKPS=%TEMP%\ccp_chkver_%RANDOM%.ps1"
>  "%CHKPS%" echo Select-String -Path 'src\updater.py' -Pattern 'APP_VERSION' ^| Select-Object -First 1 -ExpandProperty Line
powershell -NoProfile -ExecutionPolicy Bypass -File "%CHKPS%"
del /f /q "%CHKPS%" >NUL 2>&1
echo.

python --version
echo.

echo Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install "PyQt6>=6.6.0" "pyautogui>=0.9.54" "pyinstaller>=6.0.0" "cryptography>=41.0.0" "requests>=2.31.0" "openpyxl>=3.1.0" --quiet
if errorlevel 1 ( echo ERROR: pip install failed. & pause & exit /b 1 )
echo Dependencies ready.
echo.

if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist CommandCentrePro.spec del CommandCentrePro.spec

echo Building CommandCentrePro.exe (version !CLEANVER!)...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --noconsole ^
    --name "CommandCentrePro" ^
    --manifest "app.manifest" ^
    --icon "icon.ico" ^
    --paths "." ^
    --add-data "src;src" ^
    --add-data "icon.ico;." ^
    --add-data "seed_data.json;." ^
    --collect-submodules src ^
    --collect-all PyQt6 ^
    --collect-all cryptography ^
    --collect-all pyautogui ^
    --collect-all openpyxl ^
    --collect-all requests ^
    --hidden-import ctypes ^
    --hidden-import ctypes.wintypes ^
    --hidden-import PyQt6 ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    --hidden-import PyQt6.QtNetwork ^
    main.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED. See errors above.
    pause & exit /b 1
)

echo.
echo ============================================
echo  SUCCESS - dist\CommandCentrePro.exe
echo  Built version: !CLEANVER!
echo ============================================
echo.
echo  NEXT STEPS to release this update:
echo   1. Go to your GitHub repo - Releases - Draft a new release
echo   2. Tag it EXACTLY: !CLEANVER!
echo   3. Upload dist\CommandCentrePro.exe as the asset
echo      (must be named CommandCentrePro.exe)
echo   4. Publish it as the LATEST release (not draft/pre-release)
echo.
echo  The tag (!CLEANVER!) and the version inside the exe now MATCH,
echo  so users on older versions will update correctly and the
echo  version WILL change after updating.
echo.
pause

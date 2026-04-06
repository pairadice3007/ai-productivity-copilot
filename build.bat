@echo off
echo === AI Co-Pilot Build Script ===
echo.

REM Verify Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Make sure Python is installed and on your PATH.
    pause
    exit /b 1
)
python --version

REM Install dependencies
echo.
echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt
python -m pip install pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM Build the exe
echo.
echo [2/3] Building AI-CoPilot.exe...
python -m PyInstaller ai_copilot.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

REM Copy to Desktop
echo.
echo [3/3] Copying to Desktop...
copy /Y "dist\AI-CoPilot.exe" "%USERPROFILE%\Desktop\AI-CoPilot.exe"
if errorlevel 1 (
    echo ERROR: Could not copy to Desktop.
    pause
    exit /b 1
)

echo.
echo === Done! AI-CoPilot.exe is on your Desktop ===
echo.
echo First run: the app will prompt you for your ANTHROPIC_API_KEY.
pause

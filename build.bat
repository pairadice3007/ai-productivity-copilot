@echo off
echo === AI Co-Pilot Build Script ===
echo.

REM Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller
echo.

REM Build the exe
echo [2/3] Building AI-CoPilot.exe...
pyinstaller ai_copilot.spec --clean --noconfirm
echo.

REM Copy to Desktop
echo [3/3] Copying to Desktop...
copy /Y "dist\AI-CoPilot.exe" "%USERPROFILE%\Desktop\AI-CoPilot.exe"

echo.
echo === Done! AI-CoPilot.exe is on your Desktop ===
echo.
echo First run: copy .env.example to .env and add your ANTHROPIC_API_KEY
echo Or just launch the app — it will prompt you for the key on first run.
pause

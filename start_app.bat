@echo off
REM Start BetSoccer Analytics locally on http://localhost:5005
cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"
REM Open the app in the default browser once the server has had a moment to start
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:5005"
python app.py
pause

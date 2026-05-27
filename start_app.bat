@echo off
REM Start BetSoccer Analytics locally on http://localhost:5000
cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"
python app.py
pause

@echo off
title Exam Buddy server
cd /d "%~dp0"

rem Use the virtual environment if it is in this folder or the folder above
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "..\.venv\Scripts\activate.bat" (
    call "..\.venv\Scripts\activate.bat"
)

rem Open the website after 3 seconds (gives the server time to start)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8002"

echo ================================================
echo  Exam Buddy is running. Keep this window OPEN.
echo  Website:    http://127.0.0.1:8002
echo  Demo form:  http://127.0.0.1:8002/static/demo_form.html
echo  To stop: press Ctrl+C or close this window.
echo ================================================
python -m uvicorn main:app --reload --port 8002
pause

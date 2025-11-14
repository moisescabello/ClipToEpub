@echo off
setlocal

REM Change to repository root
cd /d "%~dp0"

REM Activate virtual environment if present
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"

echo Launching Clipboard to ePub (Windows Tray)...
python -m cliptoepub.tray_app_windows
if errorlevel 1 (
  echo.
  echo If you see 'ModuleNotFoundError' (e.g., PySide6), install dependencies:
  echo   pip install -r requirements.txt
  echo Ensure you're running inside a virtual environment.
  pause
)

endlocal

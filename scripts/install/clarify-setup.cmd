@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..
cd /d "%PROJECT_ROOT%"

py -3.14 "%SCRIPT_DIR%clarify-setup.py" %* --project-root "%CD%"
if errorlevel 1 (
  echo.
  echo Clarify setup failed. See logs\install.jsonl for details.
  pause
  exit /b 1
)

echo.
echo Clarify setup completed. See logs\install.jsonl for details.
pause

@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 goto run_py
)

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 goto run_python
)

echo Python 3.10 or newer is required to run this app.
echo Install Python from https://www.python.org/downloads/windows/ and select "Add Python to PATH".
pause
exit /b 1

:run_py
py -3 -B launcher.py %*
goto finish

:run_python
python -B launcher.py %*

:finish
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%

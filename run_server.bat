@echo off
REM ============================================================================
REM  run_server.bat
REM  Starts the Streamlit command dashboard in its own window.
REM  Called automatically by setup_and_start.bat - you normally never run
REM  this file by hand.
REM
REM  Usage:  run_server.bat [port]
REM  The Python interpreter to use is passed in through the NPF_PYTHON
REM  environment variable (set by setup_and_start.bat).
REM ============================================================================

setlocal EnableExtensions
cd /d "%~dp0"

set "APP_PORT=%~1"
if "%APP_PORT%"=="" set "APP_PORT=8501"

title NPF Enugu - SOS Command Server
color 0A
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ============================================================================
echo   NPF ENUGU - SOS COMMAND SERVER
echo ============================================================================
echo.
echo   Keep this window OPEN while demonstrating the system.
echo   Closing this window stops the dashboard.
echo.
echo   Dashboard URL : http://localhost:%APP_PORT%
echo   Interpreter   : %NPF_PYTHON%
echo.
echo   Commander login  : commander  / npf123
echo   Dispatcher login : dispatcher / npf123
echo.
echo ============================================================================
echo.

if not defined NPF_PYTHON (
    echo [ERROR] NPF_PYTHON is not set. Please run setup_and_start.bat instead.
    goto :hold
)

if not exist "%NPF_PYTHON%" (
    echo [ERROR] Python interpreter not found: %NPF_PYTHON%
    goto :hold
)

"%NPF_PYTHON%" -m streamlit run "%~dp0app.py" ^
    --server.port=%APP_PORT% ^
    --server.headless=true ^
    --browser.gatherUsageStats=false

echo.
echo ============================================================================
echo   The dashboard server has stopped.
echo ============================================================================
echo.

:hold
pause
endlocal
exit /b 0

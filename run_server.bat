@echo off
REM ============================================================================
REM  run_server.bat
REM  Starts the Streamlit server in its own window.
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
echo   (ONE server - both the Citizen app and the Police dashboard run from it)
echo ============================================================================
echo.
echo   Keep this window OPEN while demonstrating the system.
echo   Closing this window stops the dashboard AND the citizen app.
echo.
echo   On THIS computer:
echo       Police Command : http://localhost:%APP_PORT%/?mode=police
echo       Citizen SOS    : http://localhost:%APP_PORT%/?mode=citizen
echo.
echo   On a PHONE (same Wi-Fi network): use the Network URL printed below,
echo   then add   /?mode=citizen   to the end of it.
echo.
echo   Logins : commander / npf123   (full access)
echo            dispatcher / npf123  (read-only)
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

REM --server.address=0.0.0.0 makes the app reachable from a phone on the same
REM Wi-Fi network, which is what allows the citizen side to be demonstrated on
REM a real handset rather than only in a second browser tab.
"%NPF_PYTHON%" -m streamlit run "%~dp0app.py" ^
    --server.port=%APP_PORT% ^
    --server.address=0.0.0.0 ^
    --server.headless=true ^
    --browser.gatherUsageStats=false

echo.
echo ============================================================================
echo   The server has stopped.
echo ============================================================================
echo.

:hold
pause
endlocal
exit /b 0

@echo off
REM ============================================================================
REM  EMERGENCY RESPONSE AND SOS LOCATION TRACKING SYSTEM
REM  Nigeria Police Force - Enugu State Command
REM ----------------------------------------------------------------------------
REM  setup_and_start.bat
REM
REM  ONE server, TWO modes:
REM     MODE 1  Citizen SOS App    (no login, mobile panic button)
REM     MODE 2  Police Command     (login required, live alarm + dashboards)
REM  Both are served by this single script and share one SQLite database.
REM
REM  This script performs a complete, hands-free start-up:
REM     1. Chooses the Python interpreter to use
REM     2. Reuses an existing virtual environment if one is available,
REM        otherwise creates a new one in .\venv
REM     3. Installs every dependency listed in requirements.txt
REM     4. Creates and seeds the SQLite database (setup_db.py)
REM     5. Generates the alarm and confirmation sounds (sounds.py)
REM     6. Starts the Streamlit server
REM     7. Opens BOTH modes in the browser
REM
REM  Interpreter priority
REM     a) The virtual environment that is already activated in this window
REM     b) ..\myenv           (a shared environment next to this project)
REM     c) .\venv             (this project's own environment)
REM     d) A brand new .\venv created from the system Python 3
REM
REM  Usage:
REM     setup_and_start.bat            normal start
REM     setup_and_start.bat reset      wipe and re-seed the demo database first
REM     setup_and_start.bat fresh      ignore myenv and build a clean local venv
REM ============================================================================

setlocal EnableExtensions EnableDelayedExpansion
title NPF Enugu - Emergency Response and SOS Tracking System
color 0B

REM ---- always work from the folder that contains this script ------------------
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "SHARED_ENV=%PROJECT_DIR%..\myenv"
set "SHARED_PY=%SHARED_ENV%\Scripts\python.exe"
set "APP_PORT=8501"
set "BASE_URL=http://localhost:%APP_PORT%"
set "POLICE_URL=%BASE_URL%/?mode=police"
set "CITIZEN_URL=%BASE_URL%/?mode=citizen"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "RESET_FLAG="
if /i "%~1"=="reset" set "RESET_FLAG=--reset"

set "FORCE_FRESH="
if /i "%~1"=="fresh" set "FORCE_FRESH=1"
if /i "%~2"=="fresh" set "FORCE_FRESH=1"

echo.
echo ============================================================================
echo   NIGERIA POLICE FORCE - ENUGU STATE COMMAND
echo   Emergency Response and SOS Location Tracking System
echo      A Case Study of the Nigeria Police Force, Enugu State Command
echo ============================================================================
echo.
echo   Project folder : %PROJECT_DIR%
echo   Police Command : %POLICE_URL%
echo   Citizen SOS    : %CITIZEN_URL%
echo.

REM ============================================================================
REM  STEP 1 - verify the project files are present
REM ============================================================================
if not exist "%PROJECT_DIR%app.py" (
    echo [ERROR] app.py was not found in this folder.
    echo         Please keep setup_and_start.bat inside the project folder.
    goto :fatal
)
if not exist "%PROJECT_DIR%requirements.txt" (
    echo [ERROR] requirements.txt was not found in this folder.
    goto :fatal
)
if not exist "%PROJECT_DIR%run_server.bat" (
    echo [ERROR] run_server.bat was not found in this folder.
    goto :fatal
)
if not exist "%PROJECT_DIR%setup_db.py" (
    echo [ERROR] setup_db.py was not found in this folder.
    goto :fatal
)

REM ============================================================================
REM  STEP 2 - choose the Python interpreter
REM ============================================================================
echo [1/7] Choosing the Python interpreter...

set "RUN_PY="
set "ENV_KIND="

if not defined FORCE_FRESH (
    REM (a) an already-activated virtual environment wins
    if defined VIRTUAL_ENV (
        if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
            set "RUN_PY=%VIRTUAL_ENV%\Scripts\python.exe"
            set "ENV_KIND=activated virtual environment"
        )
    )
    REM (b) the shared myenv next to this project
    if not defined RUN_PY (
        if exist "%SHARED_PY%" (
            set "RUN_PY=%SHARED_PY%"
            set "ENV_KIND=shared myenv environment"
        )
    )
    REM (c) this project's own virtual environment
    if not defined RUN_PY (
        if exist "%VENV_PY%" (
            set "RUN_PY=%VENV_PY%"
            set "ENV_KIND=project venv"
        )
    )
)

REM (d) create a new virtual environment if none of the above applied
if not defined RUN_PY (
    echo       No usable virtual environment found - creating one.
    set "SYSTEM_PY="
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "SYSTEM_PY=py -3"
    if not defined SYSTEM_PY (
        python --version >nul 2>&1
        if not errorlevel 1 set "SYSTEM_PY=python"
    )
    if not defined SYSTEM_PY (
        echo.
        echo [ERROR] Python 3 was not found on this computer.
        echo.
        echo         Please install Python 3.10 or newer from
        echo             https://www.python.org/downloads/
        echo         IMPORTANT: tick "Add python.exe to PATH" during installation.
        echo         After installing, close this window and run this script again.
        goto :fatal
    )
    echo       Creating a new virtual environment in .\venv ...
    %SYSTEM_PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not create the virtual environment.
        echo         Try running this script as Administrator, or create it manually:
        echo             python -m venv venv
        goto :fatal
    )
    set "RUN_PY=%VENV_PY%"
    set "ENV_KIND=newly created project venv"
)

if not exist "%RUN_PY%" (
    echo [ERROR] The chosen interpreter does not exist: %RUN_PY%
    goto :fatal
)

for /f "tokens=*" %%v in ('"%RUN_PY%" --version 2^>^&1') do set "PYVER=%%v"
echo       Using  : %RUN_PY%
echo       Source : !ENV_KIND!
echo       Version: !PYVER!

REM ---- make sure pip is available in the chosen environment -------------------
"%RUN_PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo       pip is missing from this environment - attempting to install it...
    "%RUN_PY%" -m ensurepip --upgrade >nul 2>&1
    "%RUN_PY%" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] pip is not available in the chosen environment.
        echo         Run this script with the "fresh" option to build a clean venv:
        echo             setup_and_start.bat fresh
        goto :fatal
    )
)

REM ============================================================================
REM  STEP 3 - install the dependencies
REM ============================================================================
echo [2/7] Installing dependencies (this may take a few minutes on the first run)...
"%RUN_PY%" -m pip install -r "%PROJECT_DIR%requirements.txt" --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed.
    echo         Check your internet connection and try again.
    echo         If you are behind a proxy, configure it with:
    echo             set HTTP_PROXY=http://your-proxy:port
    goto :fatal
)

REM ---- verify the critical imports really work --------------------------------
"%RUN_PY%" -c "import streamlit, pandas, folium, streamlit_folium, wave" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Some required packages still cannot be imported.
    echo         Try:  "%RUN_PY%" -m pip install --force-reinstall -r requirements.txt
    goto :fatal
)
echo       All dependencies are installed and importable.

REM ============================================================================
REM  STEP 4 - create and seed the database
REM ============================================================================
echo [3/7] Preparing the SQLite database (data\sos_emergency.db)...
if defined RESET_FLAG (
    echo       RESET requested - rebuilding the database from scratch.
    "%RUN_PY%" "%PROJECT_DIR%setup_db.py" --reset
) else (
    "%RUN_PY%" "%PROJECT_DIR%setup_db.py"
)
if errorlevel 1 (
    echo.
    echo [ERROR] Database setup failed. See the messages above for details.
    goto :fatal
)

REM ============================================================================
REM  STEP 5 - generate the alarm and confirmation sounds
REM ============================================================================
echo [4/7] Preparing the sound files (no internet required)...
"%RUN_PY%" "%PROJECT_DIR%sounds.py"
if errorlevel 1 (
    echo.
    echo [WARNING] The sound files could not be generated.
    echo           The dashboard will still work, but the ringing alarm and the
    echo           citizen confirmation chime will be silent.
)

REM ============================================================================
REM  STEP 6 - make sure the chosen port is free
REM ============================================================================
echo [5/7] Checking that port %APP_PORT% is available...
set "PORT_BUSY="
for /f "tokens=*" %%a in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /c:":%APP_PORT% "') do set "PORT_BUSY=1"

if defined PORT_BUSY (
    echo       [WARNING] Port %APP_PORT% is already in use.
    echo       Another copy of the system may already be running.
    echo       Switching to port 8502.
    set "APP_PORT=8502"
    set "BASE_URL=http://localhost:8502"
    set "POLICE_URL=%BASE_URL%/?mode=police"
    set "CITIZEN_URL=%BASE_URL%/?mode=citizen"
)

REM ============================================================================
REM  STEP 7 - work out this computer's LAN address (so a phone can connect)
REM ============================================================================
set "LAN_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4 Address"') do (
    if not defined LAN_IP (
        set "LAN_IP=%%a"
    )
)
if defined LAN_IP set "LAN_IP=%LAN_IP: =%"
set "PHONE_URL=http://%LAN_IP%:%APP_PORT%/?mode=citizen"

REM ============================================================================
REM  STEP 8 - launch the server and open both modes
REM ============================================================================
echo [6/7] Starting the server (both modes)...
set "NPF_PYTHON=%RUN_PY%"
start "NPF Enugu - SOS Command Server" "%PROJECT_DIR%run_server.bat" %APP_PORT%

echo [7/7] Waiting for the server, then opening both views...
timeout /t 12 /nobreak >nul

start "" "%POLICE_URL%"
timeout /t 3 /nobreak >nul
start "" "%CITIZEN_URL%"

echo.
echo ============================================================================
echo   THE SYSTEM IS NOW RUNNING - BOTH MODES
echo ============================================================================
echo.
echo   TAB 1  POLICE COMMAND (this computer)
echo          %POLICE_URL%
echo          Login: commander / npf123   (full access)
echo          Login: dispatcher / npf123  (read-only)
echo.
echo   TAB 2  CITIZEN SOS APP (this computer - no login needed)
echo          %CITIZEN_URL%
echo.
if defined LAN_IP (
    echo   PHONE  CITIZEN SOS APP (open this on a handset on the same Wi-Fi)
    echo          %PHONE_URL%
    echo.
    echo          If the phone cannot connect, allow Python through the Windows
    echo          Firewall, or run this once in an Administrator Command Prompt:
    echo            netsh advfirewall firewall add rule name="NPF SOS 8501" ^
    echo              dir=in action=allow protocol=TCP localport=%APP_PORT%
    echo.
)
echo   DEMONSTRATION ORDER
echo     1. Tab 1: sign in as commander, stay on the Command Dashboard
echo     2. Tab 2: fill your name, pick "Armed Robbery", tap the big red button
echo     3. Tab 1: the alarm RINGS within 3 seconds and a red border flashes
echo     4. Tab 1: click "Mark as Dispatched" - the ringing stops
echo.
echo   To stop the system : close the green "SOS COMMAND SERVER" window,
echo                        then close this window.
echo   To rebuild demo data : setup_and_start.bat reset
echo.
echo ============================================================================
echo.

pause
endlocal
exit /b 0

:fatal
echo.
echo ============================================================================
echo   START-UP ABORTED
echo ============================================================================
echo.
echo   Please read the error message above, correct the problem and run
echo   setup_and_start.bat again.
echo.
pause
endlocal
exit /b 1

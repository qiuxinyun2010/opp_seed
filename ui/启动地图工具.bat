@echo off
rem ---------------------------------------------------------------
rem  One-click launcher for the OPP map tool (just double-click me).
rem  Extra args are passed to mapview.py:  PSA_MT01 / --list / --png a.png
rem  If the global hotkey does nothing while the game runs as admin,
rem  right-click this file -> "Run as administrator".
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

rem Pick an interpreter that actually starts. A broken pythonw.exe (bad
rem install, half-upgraded Python) dies before running any code, which
rem looks like "double-click does nothing" -- so smoke-test it first.
set "PYW="
set "PY="
where pythonw.exe >nul 2>nul && pythonw.exe -c "import sys" >nul 2>nul && set "PYW=pythonw"
where python.exe  >nul 2>nul && python.exe  -c "import sys" >nul 2>nul && set "PY=python"

if defined PYW (
    start "" /b cmd /c "pythonw mapview.py %* > mapview_out.log 2>&1"
    exit /b 0
)

if defined PY (
    echo [!] pythonw.exe missing or not working, using python.exe instead
    echo     a console window stays open while the map tool is running.
    python mapview.py %*
    if errorlevel 1 pause
    exit /b 0
)

echo [!] No working Python in PATH. Install Python 3.9+ first.
pause
exit /b 1

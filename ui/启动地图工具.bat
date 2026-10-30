@echo off
rem ---------------------------------------------------------------
rem  One-click launcher for the OPP map tool (Web UI edition).
rem  Pass --tk to use the legacy Tkinter UI, or other args to mapweb.py.
rem  If the global hotkey does nothing while the game runs as admin,
rem  right-click this file -> "Run as administrator".
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "ENTRY=mapweb.py"
if /i "%~1"=="--tk" (
    set "ENTRY=mapview.py"
    shift
)

set "PYW="
set "PY="
where pythonw.exe >nul 2>nul && pythonw.exe -c "import sys" >nul 2>nul && set "PYW=pythonw"
where python.exe  >nul 2>nul && python.exe  -c "import sys" >nul 2>nul && set "PY=python"

if defined PYW (
    start "" /b cmd /c "pythonw %ENTRY% %* > mapview_out.log 2>&1"
    exit /b 0
)

if defined PY (
    echo [!] pythonw.exe missing or not working, using python.exe instead
    echo     a console window stays open while the map tool is running.
    python %ENTRY% %*
    if errorlevel 1 pause
    exit /b 0
)

echo [!] No working Python in PATH. Install Python 3.9+ first.
pause
exit /b 1

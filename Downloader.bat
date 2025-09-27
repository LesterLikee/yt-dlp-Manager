@echo off
REM Get the folder where this batch file itself is located
set SCRIPT_DIR=%~dp0

REM Change to that folder
cd /d "%SCRIPT_DIR%"

REM Run the Python script from the same folder
python "%SCRIPT_DIR%Yt_downloader.py"

pause

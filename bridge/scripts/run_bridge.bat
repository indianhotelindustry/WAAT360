@echo off
REM WAAST360 Bridge Launcher Batch Script
REM This script is used by Windows Service to launch the Bridge daemon.
REM Can also be used manually for diagnostic/debug runs.

setlocal enabledelayedexpansion

REM Get the Bridge root directory (parent of scripts directory)
for /d %%i in ("%~dp0..\..") do set BRIDGE_ROOT=%%~fi

if not exist "%BRIDGE_ROOT%\.venv\Scripts\python.exe" (
    echo Error: Python virtual environment not found at %BRIDGE_ROOT%\.venv
    echo Please run: python -m venv .venv
    exit /b 1
)

REM Set up environment
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8

REM Load .env if present (for development)
if exist "%BRIDGE_ROOT%\.env" (
    for /f "tokens=1,2 delims==" %%A in ('findstr /v "^#" "%BRIDGE_ROOT%\.env"') do (
        if not "%%A"=="" (
            set "%%A=%%B"
        )
    )
)

REM Create logs directory if needed (ProgramData for service account access)
set LOG_DIR=C:\ProgramData\WAAST360\Bridge\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Prepare log file path
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set LOG_FILE=%LOG_DIR%\bridge_%mydate%_%mytime%.log

REM Log startup
echo [%date% %time%] WAAST360 Bridge startup >> "%LOG_FILE%"
echo Bridge Root: %BRIDGE_ROOT% >> "%LOG_FILE%"
echo Python: %BRIDGE_ROOT%\.venv\Scripts\python.exe >> "%LOG_FILE%"

REM Launch Bridge daemon
echo [%date% %time%] Launching daemon... >> "%LOG_FILE%"
cd /d "%BRIDGE_ROOT%"
"%BRIDGE_ROOT%\.venv\Scripts\python.exe" -u src\main.py start >> "%LOG_FILE%" 2>&1

REM Log exit
echo [%date% %time%] Bridge shutdown with exit code %ERRORLEVEL% >> "%LOG_FILE%"
exit /b %ERRORLEVEL%

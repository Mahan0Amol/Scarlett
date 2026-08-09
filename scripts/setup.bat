@echo off
REM Scarlett setup script (Windows, classic .bat)
REM
REM Download this file and double-click it, or run from cmd.exe:
REM   setup.bat
REM
REM This is a thin wrapper: it just calls setup.ps1 with the execution
REM policy bypassed for this run only (doesn't change your system policy).
REM Prefer the one-liner instead if you're comfortable with PowerShell:
REM   irm https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/setup.ps1 ^| iex

setlocal

echo Scarlett setup starting...
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo ERROR: PowerShell was not found on this system.
    echo Scarlett's setup script requires PowerShell ^(included by default on Windows 10/11^).
    pause
    exit /b 1
)

set "SETUP_PS1_URL=https://raw.githubusercontent.com/Mahan0Amol/Scarlett/main/setup.ps1"
set "SETUP_PS1_LOCAL=%~dp0setup.ps1"

if exist "%SETUP_PS1_LOCAL%" (
    echo Found local setup.ps1, running it...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SETUP_PS1_LOCAL%"
) else (
    echo Downloading setup.ps1...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Invoke-RestMethod -Uri '%SETUP_PS1_URL%' -OutFile '%TEMP%\scarlett_setup.ps1'; & '%TEMP%\scarlett_setup.ps1'"
)

if errorlevel 1 (
    echo.
    echo Setup failed - see the messages above for details.
    pause
    exit /b 1
)

echo.
echo Setup finished. See the messages above for next steps.
pause

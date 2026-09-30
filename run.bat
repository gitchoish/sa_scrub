@echo off
cd /d "%~dp0"
title Naver Search Ad Monitor Launcher

echo Starting Launcher...

:: 1. Try system python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python launcher.py
    goto end
)

:: 2. Try py launcher
py --version >nul 2>&1
if %errorlevel% equ 0 (
    py -3 launcher.py
    goto end
)

:: 3. Try common Python install paths in LocalAppData (fallback for users who didn't check Add to PATH)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" launcher.py
        goto end
    )
)

:: 4. If all failed, show error
echo.
echo =====================================================================
echo [ERROR] Python was not found on your system!
echo.
echo Please install Python 3.10 or higher from: https://www.python.org/
echo IMPORTANT: Make sure to check 'Add python.exe to PATH' when installing!
echo =====================================================================
echo.
pause

:end

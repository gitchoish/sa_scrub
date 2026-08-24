@echo off
cd /d "%~dp0"

echo =================================================================
echo Naver Search Ad Complaint Dashboard Launcher
echo =================================================================
echo.

:: Detecting python command
set PY_CMD=python
where python >nul 2>&1
if %errorlevel% neq 0 set PY_CMD=py
where %PY_CMD% >nul 2>&1
if %errorlevel% neq 0 set PY_CMD=python3

echo [1/2] Starting backend API server...
start /B "" cmd /c "cd backend & %PY_CMD% main.py"

echo [2/2] Starting frontend Vite dev server...
start /B "" cmd /c "cd frontend & npm run dev"

echo.
echo =================================================================
echo All servers are running inside this SINGLE window!
echo Open your browser: http://localhost:5173
echo.
echo Press CTRL+C inside this window or close it to stop the servers.
echo =================================================================
echo.

pause

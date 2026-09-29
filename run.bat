@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo =================================================================
echo [네이버 검색광고 침해 모니터링 시스템 실행기]
echo =================================================================
echo.

:: Python 명령어 감지
set PY_CMD=python
where python >nul 2>&1
if %errorlevel% neq 0 set PY_CMD=py
where %PY_CMD% >nul 2>&1
if %errorlevel% neq 0 set PY_CMD=python3
where %PY_CMD% >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ [오류] Python이 감지되지 않았습니다. Python이 설치되어 있고 PATH에 추가되어 있는지 확인해주세요.
    pause
    exit /b 1
)

echo 🚀 시스템 서버를 시작하는 중입니다...
start /B "" cmd /c "cd backend & %PY_CMD% main.py"

:: 서버 구동 대기 후 기본 웹 브라우저 자동 실행
timeout /t 3 /nobreak >nul
start http://localhost:8989

echo.
echo =================================================================
echo ✅ 시스템이 정상 구동되었습니다!
echo 👉 대시보드 주소: http://localhost:8989
echo (잠시 후 브라우저가 자동으로 열립니다.)
echo.
echo ⚠️ 이 창을 닫으면 프로그램이 종료됩니다.
echo =================================================================
echo.

pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =================================================================
echo [최초 1회 실행] 네이버 검색광고 침해 모니터링 환경 셋업
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
    echo.
    echo ❌ [오류] Python이 설치되어 있지 않거나 PATH에 등록되지 않았습니다!
    echo 👉 Python 설치 시 첫 화면에서 'Add python.exe to PATH'를 반드시 체크해주세요.
    pause
    exit /b 1
)

echo [1/2] 파이썬 필수 패키지 설치 중... (requirements.txt)
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ❌ [오류] 파이썬 라이브러리 설치 실패! 인터넷 연결 상태를 확인해주세요.
    pause
    exit /b 1
)

echo.
echo [2/2] 캡처용 브라우저 엔진 설치 중... (Playwright Chromium)
%PY_CMD% -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo ❌ [오류] Playwright 브라우저 설치 실패!
    pause
    exit /b 1
)

echo.
echo =================================================================
echo 🎉 환경 셋업이 완벽하게 완료되었습니다!
echo 👉 이제 평소에는 'run.bat'만 더블클릭하시면 대시보드가 자동으로 열립니다.
echo =================================================================
echo.
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =================================================================
echo [최초 1회 실행] 네이버 검색광고 침해 모니터링 환경 셋업
echo =================================================================
echo.

echo [1/3] 파이썬 필수 패키지 설치 중... (requirements.txt)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ❌ [오류] 파이썬 패키지 설치 실패! Python이 설치되어 있고 PATH에 등록되어 있는지 확인해주세요.
    pause
    exit /b 1
)

echo.
echo [2/3] Playwright 크롬 브라우저 엔진 설치 중...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo ❌ [오류] Playwright 브라우저 설치 실패!
    pause
    exit /b 1
)

echo.
echo [3/3] 프론트엔드 모듈 설치 중... (npm install)
cd frontend
call npm install
cd ..
if %errorlevel% neq 0 (
    echo.
    echo ❌ [오류] npm install 실패! Node.js가 설치되어 있는지 확인해주세요.
    pause
    exit /b 1
)

echo.
echo =================================================================
echo 🎉 환경 셋업이 완료되었습니다! 
echo 이제 평소에는 'run.bat'만 더블클릭하여 프로그램을 실행하시면 됩니다.
echo =================================================================
echo.
pause

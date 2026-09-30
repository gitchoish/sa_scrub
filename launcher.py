# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import webbrowser
import importlib.util

# 콘솔 출력 인코딩 UTF-8 설정
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, "requirements.txt")

REQUIRED_MODULES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("playwright", "playwright")
]

def print_banner():
    print("=" * 65)
    print(" 🛡️  네이버 검색광고 침해 모니터링 시스템 (SA Scrub)")
    print("=" * 65)
    print()

def check_and_install_dependencies():
    missing = []
    for pkg_name, module_name in REQUIRED_MODULES:
        if importlib.util.find_spec(module_name) is None:
            missing.append(pkg_name)

    if missing:
        print(f"📦 [초기 셋업] 필요한 필수 라이브러리를 설치합니다: {', '.join(missing)}")
        print("   (최초 1회만 실행되며 약 30초~1분 소요됩니다...)")
        print()
        
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        cmd = [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE]
        ret = subprocess.run(cmd)
        if ret.returncode != 0:
            print("❌ [오류] 필수 라이브러리 설치에 실패했습니다. 인터넷 연결을 확인해주세요.")
            input("\n엔터 키를 누르면 종료합니다...")
            sys.exit(1)
        print("✓ 라이브러리 설치 완료!")
        print()

    # Playwright Chromium 브라우저 설치 확인
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # 브라우저 실행 테스트
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        print("🌐 [초기 셋업] 캡처용 크롬 브라우저 엔진을 설치합니다...")
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        ret = subprocess.run(cmd)
        if ret.returncode != 0:
            print("❌ [오류] 크롬 브라우저 엔진 설치에 실패했습니다.")
            input("\n엔터 키를 누르면 종료합니다...")
            sys.exit(1)
        print("✓ 크롬 브라우저 엔진 설치 완료!")
        print()

def run_system():
    print_banner()
    check_and_install_dependencies()
    
    print("🚀 서버를 구동하는 중입니다...")
    
    # backend 디렉토리를 sys.path에 추가하고 이동
    sys.path.insert(0, BACKEND_DIR)
    os.chdir(BACKEND_DIR)
    
    # 2초 후 브라우저 자동 오픈을 위한 타이머 스레드
    import threading
    def open_browser():
        time.sleep(2.5)
        print("✨ 기본 웹 브라우저를 자동으로 실행합니다: http://localhost:8989")
        webbrowser.open("http://localhost:8989")
    
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()
    
    print()
    print("=" * 65)
    print(" ✅ 대시보드가 준비되었습니다!")
    print(" 👉 접속 주소: http://localhost:8989")
    print(" ⚠️  이 창을 닫으면 모니터링 시스템이 종료됩니다.")
    print("=" * 65)
    print()
    
    # FastAPI 백엔드 메인 실행 (직접 모듈로 임포트하여 실행)
    import uvicorn
    from main import kill_port_owner
    kill_port_owner(8989)
    uvicorn.run("main:app", host="0.0.0.0", port=8989, reload=False)

if __name__ == "__main__":
    try:
        run_system()
    except KeyboardInterrupt:
        print("\n시스템을 종료합니다.")
    except Exception as e:
        print(f"\n❌ [오류 발생] {e}")
        import traceback
        traceback.print_exc()
        input("\n엔터 키를 누르면 종료합니다...")

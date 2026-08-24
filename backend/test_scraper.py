# -*- coding: utf-8 -*-
import asyncio
import os
import sys

# scraper 모듈을 찾을 수 있도록 sys.path 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scraper import crawl_all_keywords

async def progress_callback(msg: str):
    try:
        print(f"[TEST LOG] {msg}")
    except UnicodeEncodeError:
        safe_msg = msg.encode('utf-8', errors='ignore').decode('cp949', errors='ignore')
        print(f"[TEST LOG] {safe_msg}")

async def run_test():
    print("[TEST] 백엔드 크롤러 2차 독립 테스트(이원화 제외 필터)를 시작합니다...")
    
    # 가벼운 테스트용 키워드
    keywords = ["종합비타민"]
    
    # 테스트용 제외 목록: 센트룸 도메인과 GNM 몰명 제외
    my_domains = ["centrum"]
    my_stores = ["GNM자연의품격"]
    
    screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "screenshots_test")
    
    # 이전 테스트 결과 정리
    if os.path.exists(screenshot_dir):
        import shutil
        shutil.rmtree(screenshot_dir)
        
    results = await crawl_all_keywords(
        keywords=keywords,
        my_domains=my_domains,
        my_stores=my_stores,
        screenshot_dir=screenshot_dir,
        on_progress=progress_callback
    )
    
    print("\n" + "="*50)
    print(f"[INFO] 테스트 결과: 총 {len(results)}건 수집됨")
    print("="*50)
    for idx, r in enumerate(results, 1):
        try:
            print(f"{idx}. [{r['ad_type']}] {r['company']} - {r['product_name'][:30] if r['product_name'] else 'N/A'}")
            print(f"   URL: {r['url'][:60]}...")
            print(f"   Screenshot: {r['screenshot']}")
        except UnicodeEncodeError:
            print(f"{idx}. [{r['ad_type']}] {r['company'].encode('cp949', errors='ignore').decode('cp949')} - N/A")
        print("-" * 50)
        
    if results:
        print("[SUCCESS] 크롤링 엔진 검증 성공!")
    else:
        print("[WARNING] 발견된 광고가 없습니다. (수집 성공이나 검색 결과에 광고가 노출되지 않았을 수 있음)")

if __name__ == "__main__":
    # Windows 환경을 위한 인코딩 스트림 패치 적용
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    asyncio.run(run_test())

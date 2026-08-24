# -*- coding: utf-8 -*-
import os
import sys
import json
import random
import urllib.parse
import asyncio
from datetime import datetime
from playwright.async_api import Page, Locator

def clean_domain(domain_str: str) -> str:
    """도메인 입력값에서 프로토콜(http/https) 및 불필요한 슬래시(/)를 안전하게 정돈"""
    dom = domain_str.lower().strip()
    for prefix in ["https://", "http://", "www."]:
        if dom.startswith(prefix):
            dom = dom[len(prefix):]
    return dom.strip("/")

def is_my_brand_dynamic(text: str, my_stores: list) -> bool:
    """텍스트에 내 자사 브랜드/스토어명이 포함되어 있는지 양방향으로 확인 (공백 제거 매칭)"""
    if not text or not my_stores:
        return False
    text_lower = text.lower().replace(" ", "")
    for store in my_stores:
        st = store.lower().strip().replace(" ", "")
        if not st:
            continue
        if st in text_lower or text_lower in st:
            return True
    return False

def is_valid_brand_name(name: str) -> bool:
    """추출된 브랜드명(스토어명)이 유효한지 확인 ('광고' 등 뱃지 텍스트 배제)"""
    if not name:
        return False
    clean = name.strip()
    if '광고' in clean or len(clean) < 2:
        return False
    return True

def is_excluded_company(brand_name: str, excluded_list: list) -> bool:
    """수집 제외할 경쟁사 목록에 포함되어 있는지 양방향 공백 제거 부분 일치 확인"""
    if not brand_name or not excluded_list:
        return False
    name_lower = brand_name.lower().replace(" ", "")
    for exc in excluded_list:
        st = exc.lower().strip().replace(" ", "")
        if not st:
            continue
        if st in name_lower or name_lower in st:
            return True
    return False

def extract_brand_name_by_cleaning(parent_text: str) -> str:
    """광고 뱃지 부모 영역의 전체 텍스트에서 뱃지용 특수기호/키워드를 소거하여 순수 스토어명 추출"""
    if not parent_text:
        return ""
    # 광고, ⓘ, 정보 등 뱃지 관련 단어 및 심볼 일괄 소거
    cleaned = parent_text.replace("광고", "").replace("ⓘ", "").replace("정보", "")
    # 줄바꿈 및 좌우 특수문자 클렌징
    cleaned = cleaned.replace("\n", " ").strip(" ⓘ()[]-·•/|:：")
    return cleaned

async def capture_element_screenshot(element: Locator, keyword: str, company: str, ad_type: str, screenshot_dir: str) -> str:
    """광고 요소 스크린샷 캡처 및 저장 (JPEG 초경량화)"""
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        safe_company = "".join(c for c in company if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_', '-')).strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ad_type}_{safe_keyword}_{safe_company}_{timestamp}.jpg"
        filepath = os.path.join(screenshot_dir, filename)
        
        await element.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        
        await element.screenshot(path=filepath, type="jpeg", quality=75)
        return filename
    except Exception as e:
        print(f"      [캡처 실패] {e}")
        return ""

async def crawl_powerlink_mobile(page: Page, keyword: str, my_domains: list, my_stores: list, excluded_companies: list, screenshot_dir: str, on_progress) -> list:
    """모바일 페이지에서 파워링크 크롤링 - daypack.py 코랩 코드 100% 구조적 복원 및 대시보드 캡처 연동"""
    await on_progress(f"  📌 {keyword} - 파워링크 수집 중...")
    results = []
    
    try:
        powerlink_body = page.locator('xpath=//*[@id="power_link_body"]')
        if await powerlink_body.count() == 0:
            await on_progress("    → 파워링크 영역 없음")
            return results
            
        await on_progress("    ✓ 파워링크 영역 발견")
        
        items = powerlink_body.locator('li')
        item_count = await items.count()
        await on_progress(f"    → {item_count}개 파워링크 항목 발견")
        
        for idx in range(item_count):
            try:
                li_item = items.nth(idx)
                
                # 브랜드명 추출
                brand_name = None
                landing_url = None
                
                span_paths = [
                    './/div/div[1]/div/a/div[1]/div/span[2]',
                    './/div/div[1]/div/a/div[1]/div/span[3]',
                    './/div/div[1]/div/a/div[1]/div/span[1]'
                ]
                
                for span_path in span_paths:
                    try:
                        span_elem = li_item.locator(f'xpath={span_path}')
                        if await span_elem.count() > 0:
                            text = await span_elem.first.inner_text()
                            text = text.strip()
                            if text and 2 <= len(text) <= 50:
                                brand_name = text
                                break
                    except:
                        continue
                        
                # URL
                try:
                    link = li_item.locator('a').first
                    if await link.count() > 0:
                        landing_url = await link.get_attribute("href")
                except:
                    pass
                    
                # 표시 URL 추출 (네이버 리다이렉트 URL 암호화 대비 화면 표시 도메인 파싱)
                display_url = ""
                try:
                    all_spans = li_item.locator('span')
                    span_cnt = await all_spans.count()
                    for s_idx in range(span_cnt):
                        s_txt = await all_spans.nth(s_idx).inner_text()
                        s_txt = s_txt.strip()
                        # 한글이 안 들어있고 '.'이 포함된 도메인 형태의 문자열 검출
                        if '.' in s_txt and len(s_txt) >= 4 and not any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in s_txt):
                            display_url = s_txt.lower()
                            break
                except:
                    pass
                    
                if brand_name:
                    # 도메인 클렌징 필터 및 자사 브랜드 필터 체크
                    is_excluded = False
                    
                    # 1. 도메인 필터링 (랜딩 URL 및 화면 표시 URL 교차 검사)
                    if my_domains:
                        for domain in my_domains:
                            dom = clean_domain(domain)
                            if dom:
                                if (landing_url and dom in landing_url.lower()) or (display_url and dom in display_url):
                                    is_excluded = True
                                    break
                                
                    # 2. 브랜드명 필터링 (is_my_brand_dynamic)
                    if not is_excluded and is_my_brand_dynamic(brand_name, my_stores):
                        is_excluded = True
                        
                    # 3. 제외 경쟁사 필터링 (is_excluded_company)
                    if not is_excluded and is_excluded_company(brand_name, excluded_companies):
                        is_excluded = True
                        await on_progress(f"      [제외] 지정 제외 경쟁사 광고 - {brand_name}")
                        
                    if not is_excluded:
                        # 증빙 스크린샷 캡처
                        screenshot_file = await capture_element_screenshot(li_item, keyword, brand_name, "Powerlink", screenshot_dir)
                        
                        results.append({
                            "keyword": keyword,
                            "company": brand_name,
                            "product_name": "",
                            "url": landing_url or "",
                            "ad_type": "파워링크",
                            "screenshot": screenshot_file
                        })
                        await on_progress(f"      ✓ [발견] {len(results)}위 - {brand_name} (캡처완료)")
                    else:
                        await on_progress(f"      [제외] 내 브랜드 광고 - {brand_name} (URL: {landing_url or 'N/A'})")
                        
            except Exception as e:
                import traceback
                await on_progress(f"      [오류] 파워링크 항목 처리 중 에러: {e}")
                traceback.print_exc()
                continue
                
    except Exception as e:
        await on_progress(f"  ⚠️ 파워링크 수집 실패: {e}")
        
    return results

async def crawl_shopping_ads_mobile(page: Page, keyword: str, my_stores: list, excluded_companies: list, screenshot_dir: str, on_progress, max_pages: int = 5) -> list:
    """네이버 쇼핑검색 광고 크롤링 - 쇼핑 전용 섹션 제한 및 광고 트래킹 도메인 교차 판정 마스터 버전"""
    await on_progress(f"  🛒 네이버 쇼핑검색 광고 수집 중 (최대 {max_pages}페이지)...")
    results = []
    
    try:
        # 1단계: 쇼핑 영역 찾기 (수집 스코프 고립)
        await asyncio.sleep(2)
        shopping_section = None
        
        # 방법 A: "네이버 가격비교" 텍스트 조상 section
        price_text_locator = page.locator("text=네이버 가격비교")
        if await price_text_locator.count() > 0:
            shopping_section = price_text_locator.locator('xpath=ancestor::section').first
            await on_progress("    ✓ 쇼핑 영역 특정 성공 ('네이버 가격비교' 조상)")
            
        # 방법 B: "쇼핑" 텍스트 조상 section
        if not shopping_section or await shopping_section.count() == 0:
            shopping_text = page.locator("text=쇼핑")
            if await shopping_text.count() > 0:
                shopping_section = shopping_text.locator('xpath=ancestor::section').first
                await on_progress("    ✓ 쇼핑 영역 특정 성공 ('쇼핑' 조상)")
                
        # 방법 C: 가격비교/쇼핑 텍스트 포함 section
        if not shopping_section or await shopping_section.count() == 0:
            shopping_section = page.locator('section:has-text("가격비교"), section:has-text("쇼핑")').first
            if await shopping_section.count() > 0:
                await on_progress("    ✓ 쇼핑 영역 특정 성공 (has-text)")
                
        # Fallback: 가격비교 섹션이 아예 잡히지 않는 특이 키워드일 때만 페이지 전체 스코핑
        if not shopping_section or await shopping_section.count() == 0:
            shopping_section = page
            await on_progress("    ⚠️ 쇼핑 전용 영역을 특정할 수 없어 페이지 전체를 스캔합니다.")
            
        collected_items = set() # 중복 방지 (URL 기준)
        
        for page_num in range(max_pages):
            await on_progress(f"    📄 페이지 {page_num + 1}/{max_pages} 수집 시작")
            
            # [필수] 레이지 로딩 방지를 위한 하향 스크롤 수행 (동적 렌더링 활성화)
            try:
                for scroll_step in range(4):
                    await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * (0.25 * {scroll_step + 1}))")
                    await asyncio.sleep(0.8)
            except Exception as scroll_err:
                print(f"       [디버그] 스크롤 중 오류 발생: {scroll_err}")
                
            await asyncio.sleep(1.5)
            
            try:
                # 2단계: 쇼핑 영역 내에서 "광고" 텍스트가 들어간 모든 뱃지 요소 추출
                ad_badges = shopping_section.locator('span:has-text("광고"), em:has-text("광고"), div:has-text("광고")')
                badge_count = await ad_badges.count()
                await on_progress(f"       총 {badge_count}개의 광고 후보 요소 발견")
                
                ad_found_in_page = 0
                
                for idx in range(badge_count):
                    try:
                        badge = ad_badges.nth(idx)
                        
                        # 가시성 검사(is_visible) 정밀 부활 (유령/숨겨진 템플릿 제거)
                        if not await badge.is_visible():
                            continue
                            
                        # 진짜 '광고' 뱃지 텍스트인지 판별 (정확히 일치해야 함)
                        ad_text = await badge.inner_text()
                        ad_text = ad_text.strip().replace(" ", "")
                        if ad_text not in ["광고", "광고ⓘ", "광고정보", "ad", "adⓘ"]:
                            continue
                            
                        # 파워링크 영역 내의 뱃지이면 쇼핑 수집에서는 제외
                        is_powerlink_ancestor = await badge.locator('xpath=ancestor::*[contains(@id, "power_link")]').count() > 0
                        if is_powerlink_ancestor:
                            continue
                            
                        # 3단계: 뱃지로부터 부모 카드(li 또는 view_type_guide_ div) 역추적
                        parent_card = None
                        li_ancestor = badge.locator('xpath=ancestor::li').first
                        if await li_ancestor.count() > 0:
                            parent_card = li_ancestor
                        else:
                            div_ancestor = badge.locator('xpath=ancestor::div[contains(@id, "view_type_guide_")]').first
                            if await div_ancestor.count() > 0:
                                parent_card = div_ancestor
                                
                        if not parent_card:
                            continue
                            
                        # 4단계: 브랜드명 추출 (부모 카드 내부 몰이름 탐색 및 부모 텍스트 클렌징 결합)
                        brand_name = None
                        
                        # A. 뱃지 옆이나 부모 카드 내부의 스토어 클래스/텍스트 탐색
                        mall_locators = [
                            parent_card.locator('span[class*="mall"]'),
                            parent_card.locator('span[class*="seller"]'),
                            parent_card.locator('div.mall_area span')
                        ]
                        for m_loc in mall_locators:
                            if await m_loc.count() > 0:
                                txt = await m_loc.first.inner_text()
                                txt = txt.strip()
                                if is_valid_brand_name(txt):
                                    brand_name = txt
                                    break
                                    
                        # B. Fallback 1: 뱃지의 부모 영역 전체 텍스트 클렌징 기법 적용 (가장 정밀)
                        if not brand_name:
                            badge_parent = badge.locator('xpath=..')
                            if await badge_parent.count() > 0:
                                parent_txt = await badge_parent.first.inner_text()
                                cleaned_txt = extract_brand_name_by_cleaning(parent_txt)
                                if is_valid_brand_name(cleaned_txt):
                                    brand_name = cleaned_txt
                                    
                        # C. Fallback 2: 뱃지의 부모 컨테이너 내의 span 중 '광고'가 아닌 것 탐색
                        if not brand_name:
                            badge_parent = badge.locator('xpath=..')
                            if await badge_parent.count() > 0:
                                spans = badge_parent.locator('span')
                                span_cnt = await spans.count()
                                for s_idx in range(span_cnt):
                                    txt = await spans.nth(s_idx).inner_text()
                                    txt = txt.strip()
                                    if is_valid_brand_name(txt):
                                        brand_name = txt
                                        break
                                        
                        if not brand_name:
                            continue
                            
                        # 5단계: 데이팩 브랜드인지 확인 (동적 자사 브랜드 필터링)
                        if is_my_brand_dynamic(brand_name, my_stores):
                            await on_progress(f"       → 내 브랜드 (제외): '{brand_name}'")
                            continue
                            
                        # 5.5단계: 제외 경쟁사 필터링
                        if is_excluded_company(brand_name, excluded_companies):
                            await on_progress(f"       → 지정 제외 경쟁사 (제외): '{brand_name}'")
                            continue
                            
                        # 6단계: 상품명 추출 (strong)
                        product_element = parent_card.locator('strong')
                        product_name = ""
                        if await product_element.count() > 0:
                            product_name = await product_element.first.inner_text()
                            product_name = product_name.strip()
                            
                        # 7단계: 상품 상세페이지 URL 추출 및 [광고 트래킹 도메인 교차 판별]
                        product_url = None
                        is_ad_tracking_url = False
                        
                        # 부모 카드 내부의 모든 a 태그의 href 조사
                        all_links = parent_card.locator('a')
                        link_count = await all_links.count()
                        for link_idx in range(link_count):
                            temp_url = await all_links.nth(link_idx).get_attribute('href')
                            if temp_url:
                                temp_url_lower = temp_url.lower()
                                # 네이버 쇼핑 광고 트래킹 도메인 유무 확인 (adcr 또는 cr2)
                                if 'adcr.naver.com' in temp_url_lower or 'cr2.shopping.naver.com' in temp_url_lower:
                                    is_ad_tracking_url = True
                                    product_url = temp_url
                                    break
                                    
                        # 광고 트래킹 주소 검증을 통과하지 못한 일반 상품은 수집 대상에서 스킵!
                        if not is_ad_tracking_url:
                            continue
                            
                        if not product_url:
                            continue
                            
                        # URL 중복 확인
                        if product_url in collected_items:
                            continue
                            
                        # URL 정규화
                        if not product_url.startswith('http'):
                            product_url = 'https://m.search.naver.com' + product_url
                            
                        collected_items.add(product_url)
                        
                        # 8단계: 증빙 스크린샷 캡처 및 대시보드 저장
                        screenshot_file = await capture_element_screenshot(parent_card, keyword, brand_name, "Shopping", screenshot_dir)
                        
                        results.append({
                            "keyword": keyword,
                            "company": brand_name,
                            "product_name": product_name,
                            "url": product_url,
                            "ad_type": "쇼핑광고",
                            "screenshot": screenshot_file
                        })
                        ad_found_in_page += 1
                        await on_progress(f"       ✓ [발견] {len(results)}위 - {brand_name} / {product_name[:25]}... (캡처완료)")
                        
                    except Exception as e:
                        import traceback
                        await on_progress(f"       [오류] {str(e)[:100]}")
                        traceback.print_exc()
                        continue
                        
                await on_progress(f"       → 이 페이지에서 {ad_found_in_page}개 광고 수집")
                
                # 9단계: 다음 페이지로 이동
                if page_num < max_pages - 1:
                    await on_progress("       다음 페이지 버튼 찾는 중...")
                    next_clicked = False
                    
                    # 특정 섹션 내의 버튼으로 스코핑을 좁혀 오작동 방지
                    next_button = shopping_section.locator('button[aria-label*="다음"], button[aria-label*="next"], a[aria-label*="다음"], a.next').first
                    if await next_button.count() > 0 and await next_button.is_visible():
                        try:
                            await next_button.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await next_button.click()
                            next_clicked = True
                            await on_progress("       ✓ 방법1: 섹션 내 다음 버튼 클릭")
                        except:
                            pass
                            
                    if not next_clicked:
                        # Fallback: 페이지 전체에서 다음 버튼 찾기
                        next_button_fallback = page.locator('button[aria-label*="다음"], button[aria-label*="next"], a[aria-label*="다음"], a.next').first
                        if await next_button_fallback.count() > 0 and await next_button_fallback.is_visible():
                            try:
                                await next_button_fallback.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                await next_button_fallback.click()
                                next_clicked = True
                                await on_progress("       ✓ 방법2: 페이지 내 다음 버튼 클릭")
                            except:
                                pass
                                
                    if next_clicked:
                        await asyncio.sleep(4 + random.uniform(1.0, 2.0))
                    else:
                        await on_progress("       → 다음 버튼을 찾을 수 없음 (마지막 페이지)")
                        break
                        
            except Exception as page_e:
                await on_progress(f"    ⚠️ 페이지 {page_num + 1} 처리 중 오류: {page_e}")
                break
                
    except Exception as e:
        await on_progress(f"  ⚠️ 쇼핑 광고 수집 실패: {e}")
        
    return results

async def crawl_all_keywords(keywords: list, my_domains: list, my_stores: list, excluded_companies: list, screenshot_dir: str, on_progress, naver_cookie: str = "") -> list:
    """모든 키워드에 대해 크롤링 실행 (네이버 로그인 쿠키 세션 주입 옵션 포함)"""
    import sys
    import asyncio
    if sys.platform.startswith('win'):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception as loop_err:
            await on_progress(f"  [경고] 이벤트 루프 정책 변경 실패: {loop_err}")

    from playwright.async_api import async_playwright
    
    all_results = []
    
    async with async_playwright() as p:
        await on_progress("🚀 크롬 브라우저를 시작하는 중...")
        
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
        
        context = await browser.new_context(
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True
        )
        
        # 네이버 로그인 쿠키가 전달된 경우 주입
        if naver_cookie:
            try:
                cookies_to_add = []
                for item in naver_cookie.split(";"):
                    if "=" in item:
                        name, val = item.strip().split("=", 1)
                        cookies_to_add.append({
                            "name": name,
                            "value": val,
                            "domain": ".naver.com",
                            "path": "/"
                        })
                if cookies_to_add:
                    await context.add_cookies(cookies_to_add)
                    await on_progress("🔑 [네이버 세션] 로그인 세션 쿠키 주입 완료 (개인화 가중치 적용)")
            except Exception as cookie_err:
                await on_progress(f"⚠️ [경고] 로그인 쿠키 주입 중 에러 발생: {cookie_err}")
                
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        page = await context.new_page()
        
        for idx, kw in enumerate(keywords, 1):
            await on_progress(f"\n========================================")
            await on_progress(f"[{idx}/{len(keywords)}] 키워드 검색: '{kw}'")
            await on_progress(f"========================================")
            
            encoded = urllib.parse.quote(kw)
            url = f"https://m.search.naver.com/search.naver?query={encoded}"
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(4 + random.uniform(1.0, 2.0))
            except Exception as e:
                await on_progress(f"  ⚠️ 페이지 로드 실패: {e}")
                continue
                
            # 1. 파워링크 수집
            powerlink_results = await crawl_powerlink_mobile(page, kw, my_domains, my_stores, excluded_companies, screenshot_dir, on_progress)
            all_results.extend(powerlink_results)
            
            await asyncio.sleep(1.5)
            
            # 2. 쇼핑 광고 수집 (max_pages=5 로 설정)
            shopping_results = await crawl_shopping_ads_mobile(page, kw, my_stores, excluded_companies, screenshot_dir, on_progress, max_pages=5)
            all_results.extend(shopping_results)
            
            if idx < len(keywords):
                delay = random.uniform(6.0, 10.0)
                await on_progress(f"⏳ 다음 키워드를 위해 {delay:.1f}초 대기 중...")
                await asyncio.sleep(delay)
                
        await browser.close()
        await on_progress("🏁 크롤링 작업이 종료되었습니다.")
        
    return all_results

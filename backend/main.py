# -*- coding: utf-8 -*-
import sys
import io
import asyncio
import subprocess
import signal

# Windows 환경에서 asyncio subprocess를 사용하기 위해 ProactorEventLoop 지정
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def kill_port_owner(port: int):
    """지정한 로컬 포트를 점유 중인 프로세스를 강제 종료"""
    if sys.platform.startswith('win'):
        try:
            cmd = f"netstat -aon | findstr :{port}"
            res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            lines = res.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5 and "LISTENING" in line:
                    pid = parts[-1]
                    if pid != str(os.getpid()) and pid != "0":
                        pids.add(int(pid))
            for pid in pids:
                try:
                    subprocess.run(f"taskkill /f /pid {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except:
                    pass
        except:
            pass

import os
import json
import shutil
import zipfile
import smtplib
from io import BytesIO
from typing import List, Optional
from datetime import datetime
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# scraper 모듈 임포트
from scraper import crawl_all_keywords

app = FastAPI(title="Naver Search Ad Complaint Platform API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 디렉토리 구성
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "static", "screenshots")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# SMTP 및 스케줄러 전역 상태 관리
class AppState:
    def __init__(self):
        self.is_running = False
        self.progress_percent = 0
        self.logs = []
        self.results = []
        self.last_run_timestamp = ""
        
        # 설정 보존 대상 필드
        self.target_keywords = []
        self.my_domains = []
        self.my_stores = []
        self.scheduler_active = False
        self.scheduler_interval = 30 # 기본 30분
        self.smtp_server = ""
        self.smtp_port = 587
        self.smtp_user = ""
        self.smtp_password = ""
        self.receiver_email = ""
        self.naver_cookie = ""
        self.excluded_companies = []
        self.current_task = None

state = AppState()

# 설정 파일 로드/저장 유틸리티
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                state.target_keywords = data.get("target_keywords", [])
                state.my_domains = data.get("my_domains", ["daypack"])
                state.my_stores = data.get("my_stores", ["데이팩"])
                state.scheduler_active = data.get("scheduler_active", False)
                state.scheduler_interval = data.get("scheduler_interval", 30)
                state.smtp_server = data.get("smtp_server", "")
                state.smtp_port = data.get("smtp_port", 587)
                state.smtp_user = data.get("smtp_user", "")
                state.smtp_password = data.get("smtp_password", "")
                state.receiver_email = data.get("receiver_email", "")
                state.naver_cookie = data.get("naver_cookie", "")
                state.excluded_companies = data.get("excluded_companies", [])
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")

def save_settings():
    try:
        data = {
            "target_keywords": state.target_keywords,
            "my_domains": state.my_domains,
            "my_stores": state.my_stores,
            "scheduler_active": state.scheduler_active,
            "scheduler_interval": state.scheduler_interval,
            "smtp_server": state.smtp_server,
            "smtp_port": state.smtp_port,
            "smtp_user": state.smtp_user,
            "smtp_password": state.smtp_password,
            "receiver_email": state.receiver_email,
            "naver_cookie": state.naver_cookie,
            "excluded_companies": state.excluded_companies
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"설정 파일 저장 실패: {e}")

# 스키마 정의
class StartCrawlRequest(BaseModel):
    keywords: List[str]
    my_domains: List[str]
    my_stores: List[str]
    excluded_companies: List[str] = []
    naver_cookie: Optional[str] = ""
    send_email: Optional[bool] = True

class SaveConfigRequest(BaseModel):
    keywords: List[str]
    my_domains: List[str]
    my_stores: List[str]
    excluded_companies: List[str]
    naver_cookie: Optional[str] = ""

class SchedulerConfigRequest(BaseModel):
    scheduler_active: bool
    scheduler_interval: int
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    receiver_email: str

class TestEmailRequest(BaseModel):
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    receiver_email: str

# ----------------- 이메일 발송 유틸리티 -----------------

def create_excel_bytes(data_list: list, sheet_mode: str = "original") -> bytes:
    """엑셀 메모리 파일 생성"""
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if sheet_mode == "original":
            export_df = df.drop(columns=['screenshot']) if 'screenshot' in df.columns else df
            # 컬럼 보기 좋게 재배치 (device 우선)
            col_order = [c for c in ['device', 'ad_type', 'keyword', 'company', 'product_name', 'url'] if c in export_df.columns]
            other_cols = [c for c in export_df.columns if c not in col_order]
            export_df = export_df[col_order + other_cols]
            export_df.to_excel(writer, sheet_name='전체', index=False)
            
            powerlink_df = export_df[export_df['ad_type'] == '파워링크']
            if len(powerlink_df) > 0:
                powerlink_df.to_excel(writer, sheet_name='파워링크', index=False)
                
            shopping_df = export_df[export_df['ad_type'] == '쇼핑광고']
            if len(shopping_df) > 0:
                shopping_df.to_excel(writer, sheet_name='쇼핑광고', index=False)
        else: # complaint용 간소화 포맷
            columns_to_keep = [c for c in ['device', 'ad_type', 'keyword', 'company', 'product_name', 'url'] if c in df.columns]
            if not columns_to_keep:
                columns_to_keep = ['keyword', 'company', 'product_name', 'url']
            for col in columns_to_keep:
                if col not in df.columns:
                    df[col] = ""
            df[columns_to_keep].to_excel(writer, index=False)
            
    output.seek(0)
    return output.getvalue()

def create_screenshots_zip_bytes() -> Optional[bytes]:
    """스크린샷 폴더 내 파일을 ZIP 메모리 버퍼로 변환"""
    if not os.path.exists(SCREENSHOT_DIR) or not os.listdir(SCREENSHOT_DIR):
        return None
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for root, _, files in os.walk(SCREENSHOT_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                zip_file.write(filepath, file)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def send_report_email(smtp_server, smtp_port, smtp_user, smtp_password, receiver_email, results_list, timestamp) -> tuple:
    """메일 작성 및 SMTP 전송 핵심 로직 (콤마/세미콜론 구분으로 다중 수신인 발송 지원)"""
    try:
        # 이메일 수신처 목록 파싱 (콤마 , 또는 세미콜론 ; 기준) 및 중복 제거
        recipients_raw = []
        for r in receiver_email.replace(";", ",").split(","):
            r_clean = r.strip()
            if r_clean:
                recipients_raw.append(r_clean)
        
        # 중복 이메일 주소 제거
        recipients = sorted(list(set(recipients_raw)))
                 
        if not recipients:
            return False, "수신 이메일 주소가 비어있습니다."
 
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"[경쟁사광고 리포트] 브랜드 키워드 침해 검출 보고 ({timestamp})"
        
        complaint_body = format_complaint_text(results_list)
        
        # 스크린샷 증빙 파일 용량 확인 (네이버 SMTP 10MB 전송 규격 대비 초과 검사)
        zip_bytes = create_screenshots_zip_bytes()
        zip_size_limit = 10 * 1024 * 1024  # 10MB
        zip_oversized = False
        if zip_bytes and len(zip_bytes) > zip_size_limit:
            zip_oversized = True
            
        body_text = "안녕하세요, 브랜드 키워드 침해 모니터링 시스템 자동 발송 메일입니다.\n\n"
        body_text += f"검출 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        body_text += f"검출된 위반 건수: 총 {len(results_list)}건\n\n"
        
        if zip_oversized:
            body_text += "⚠️ [경고] 수집된 증빙 이미지들의 압축 파일 용량이 네이버 이메일 발송 제한(10MB)을 초과하여 메일 첨부에서 제외되었습니다.\n"
            body_text += f"실제 압축 용량: {len(zip_bytes) / (1024 * 1024):.2f}MB\n"
            body_text += "캡처된 스크린샷 증빙들은 크롤링 구동 PC의 'backend/static/screenshots' 폴더 내에 안전하게 보관되어 있습니다. 해당 폴더에서 직접 이미지를 검토 후 신고 접수해 주십시오.\n\n"
        else:
            body_text += "아래 제재요청 텍스트 양식과 첨부된 증빙 서류(엑셀 및 스크린샷 압축파일)를 검토하시어 네이버 권리침해 신고를 접수해 주십시오.\n"
            
        body_text += "=================================================================\n\n"
        body_text += complaint_body
        
        msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
        
        # 1. 원본 데이터 엑셀 첨부
        orig_excel = create_excel_bytes(results_list, "original")
        part1 = MIMEBase('application', 'octet-stream')
        part1.set_payload(orig_excel)
        encoders.encode_base64(part1)
        part1.add_header('Content-Disposition', f'attachment; filename="naver_ads_{timestamp}.xlsx"')
        msg.attach(part1)
        
        # 2. 신고 규격 엑셀 첨부
        compl_excel = create_excel_bytes(results_list, "complaint")
        part2 = MIMEBase('application', 'octet-stream')
        part2.set_payload(compl_excel)
        encoders.encode_base64(part2)
        part2.add_header('Content-Disposition', f'attachment; filename="complaint_format_{timestamp}.xlsx"')
        msg.attach(part2)
        
        # 3. 스크린샷 증빙 파일 ZIP 첨부 (10MB 이하인 경우에만 메일에 첨부)
        if zip_bytes and not zip_oversized:
            part3 = MIMEBase('application', 'octet-stream')
            part3.set_payload(zip_bytes)
            encoders.encode_base64(part3)
            part3.add_header('Content-Disposition', f'attachment; filename="screenshots_{timestamp}.zip"')
            msg.attach(part3)
            
        # SMTP 전송
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()
            
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())
        server.quit()
        return True, ""
    except Exception as e:
        print(f"이메일 전송 실패: {e}")
        return False, str(e)

# ----------------- 신고 양식 포맷 생성 유틸리티 -----------------

def format_complaint_text(results_list: list) -> str:
    """기존 daypack.py의 신고용 텍스트 포맷 재현"""
    if not results_list:
        return "경쟁사 광고가 발견된 키워드가 없습니다."
        
    df = pd.DataFrame(results_list)
    keywords_with_ads = df['keyword'].unique()
    keyword_list = ', '.join(keywords_with_ads)
    
    complaint_text = f"담당자님 안녕하세요, 브랜드키워드({keyword_list})에서 관련 없는 경쟁사 광고 노출 확인되어 노출제재 요청드립니다. 확인 부탁드립니다.\n\n"
    
    for _, row in df.iterrows():
        dev = row.get('device') or '모바일'
        ad_t = row.get('ad_type') or '광고'
        complaint_text += f"구분: [{dev}] {ad_t}\n"
        complaint_text += f"키워드: {row['keyword']}\n"
        complaint_text += f"업체명: {row['company']}\n"
        if row.get('product_name'):
            complaint_text += f"상품명: {row['product_name']}\n"
        complaint_text += f"URL: {row['url']}\n\n"
        
    return complaint_text

# ----------------- FastAPI 엔드포인트 -----------------

@app.on_event("startup")
async def startup_event():
    """서브 앱 시작 시 기존 세팅을 불러옴"""
    load_settings()
    # 백그라운드 스케줄러 루프를 asyncio 태스크로 시동
    asyncio.create_task(scheduler_loop())

@app.get("/api/config")
async def get_config():
    """초기 세팅 값 조회"""
    default_keywords = [
        '데이팩',
        '데이팩올인원',
        '데이팩올인원영양제',
        '데이팩영양제',
        '데이팩종합영양제',
        '데이팩멀티비타민',
        '데이팩종합비타민'
    ]
    return {
        "default_keywords": state.target_keywords if state.target_keywords else default_keywords,
        "default_my_domains": state.my_domains if state.my_domains else ["daypack"],
        "default_my_stores": state.my_stores if state.my_stores else ["데이팩"],
        "default_excluded_companies": state.excluded_companies,
        "default_naver_cookie": state.naver_cookie
    }

@app.post("/api/config/save")
async def save_config(req: SaveConfigRequest):
    """키워드 및 각종 필터 설정 정보 실시간 영구 보존"""
    state.target_keywords = req.keywords
    state.my_domains = req.my_domains
    state.my_stores = req.my_stores
    state.excluded_companies = req.excluded_companies
    state.naver_cookie = req.naver_cookie or ""
    save_settings()
    return {"message": "설정이 성공적으로 동기화 저장되었습니다."}

@app.get("/api/status")
async def get_status():
    return {
        "is_running": state.is_running,
        "progress_percent": state.progress_percent,
        "logs": state.logs,
        "last_run_timestamp": state.last_run_timestamp,
        "results_count": len(state.results)
    }

@app.get("/api/results")
async def get_results():
    complaint_txt = format_complaint_text(state.results)
    return {
        "results": state.results,
        "complaint_text": complaint_txt,
        "last_run_timestamp": state.last_run_timestamp
    }

# ----------------- 스케줄러 제어 API -----------------

@app.get("/api/scheduler/config")
async def get_scheduler_config():
    """현재 스케줄러 및 SMTP 설정 반환"""
    return {
        "scheduler_active": state.scheduler_active,
        "scheduler_interval": state.scheduler_interval,
        "smtp_server": state.smtp_server,
        "smtp_port": state.smtp_port,
        "smtp_user": state.smtp_user,
        "smtp_password": "●●●●●●●●" if state.smtp_password else "",
        "receiver_email": state.receiver_email
    }

@app.post("/api/scheduler/config")
async def save_scheduler_config(req: SchedulerConfigRequest):
    """스케줄러 및 SMTP 설정 저장"""
    state.scheduler_active = req.scheduler_active
    state.scheduler_interval = req.scheduler_interval
    state.smtp_server = req.smtp_server
    state.smtp_port = req.smtp_port
    state.smtp_user = req.smtp_user
    
    # 패스워드가 마스킹된 기입이 아니라면 갱신
    if req.smtp_password and req.smtp_password != "●●●●●●●●":
        state.smtp_password = req.smtp_password
        
    state.receiver_email = req.receiver_email
    
    save_settings()
    return {"message": "스케줄러 설정이 저장되었습니다."}

@app.post("/api/scheduler/test-email")
async def send_test_email(req: TestEmailRequest):
    """SMTP 테스트 전송"""
    test_results = [
        {
            "keyword": "테스트키워드",
            "company": "테스트경쟁사",
            "product_name": "테스트상품명",
            "url": "https://smartstore.naver.com/test",
            "ad_type": "쇼핑광고",
            "screenshot": ""
        }
    ]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 패스워드 마스킹 체크 우회
    pwd = req.smtp_password
    if pwd == "●●●●●●●●":
        pwd = state.smtp_password
        
    success, err_msg = send_report_email(
        smtp_server=req.smtp_server,
        smtp_port=req.smtp_port,
        smtp_user=req.smtp_user,
        smtp_password=pwd,
        receiver_email=req.receiver_email,
        results_list=test_results,
        timestamp=timestamp
    )
    if not success:
        raise HTTPException(status_code=400, detail=f"SMTP 테스트 메일 발송에 실패했습니다. (원인: {err_msg})")
    return {"message": "테스트 메일이 성공적으로 발송되었습니다."}

# ----------------- 크롤링 기동 로직 -----------------

async def background_crawl_task(keywords: List[str], my_domains: List[str], my_stores: List[str], excluded_companies: List[str] = None, is_auto: bool = False, send_email: bool = True):
    """백그라운드 크롤링 프로세스 수행 (도메인/스토어 매칭 필터 적용)"""
    state.is_running = True
    state.progress_percent = 5
    
    # 자동(스케줄) 구동이 아닐 때만 로그 초기화
    if not is_auto:
        state.logs = ["🧹 이전 임시 스크린샷 폴더 정리 중..."]
        state.results = []
    else:
        state.logs.append(f"\n⏰ [정기 스캔] 자동 모니터링 기동 ({datetime.now().strftime('%H:%M:%S')})")
        
    state.last_run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    state.target_keywords = keywords
    state.my_domains = my_domains
    state.my_stores = my_stores
    if excluded_companies is not None:
        state.excluded_companies = excluded_companies
    
    # 키워드 설정을 항상 로컬 보존하도록 연동
    save_settings()
    
    try:
        if os.path.exists(SCREENSHOT_DIR) and not is_auto:
            shutil.rmtree(SCREENSHOT_DIR)
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    except Exception as e:
        print(f"Failed to clear screenshots dir: {e}")
        
    if not is_auto:
        state.logs.append("✅ 폴더 정리가 완료되었습니다.")
    state.progress_percent = 10
    
    total_steps = len(keywords)
    step_count = 0
    
    async def on_progress_log(message: str):
        state.logs.append(message)
        nonlocal step_count
        if "키워드 검색:" in message:
            step_count += 1
            percent = 10 + int((step_count / total_steps) * 85)
            state.progress_percent = min(percent, 95)
            
    try:
        results = await crawl_all_keywords(
            keywords=keywords,
            my_domains=my_domains,
            my_stores=my_stores,
            excluded_companies=state.excluded_companies,
            screenshot_dir=SCREENSHOT_DIR,
            on_progress=on_progress_log,
            naver_cookie=state.naver_cookie
        )
        
        # 자동 크롤링의 경우 결과 누적 또는 리셋 처리
        if is_auto:
            state.results = results # 정기 리포트이므로 해당 회차 결과만 갱신
        else:
            state.results = results
            
        state.logs.append(f"🎉 모든 키워드 수집이 완료되었습니다! (총 {len(results)}건 수집)")
        state.progress_percent = 100
        
        # 경쟁사 광고가 발견되었을 때 이메일 리포트 발송 (자동/수동 스캔 공통 즉시 발송, send_email이 True인 경우만)
        if len(results) > 0 and state.smtp_server and state.smtp_user and send_email:
            state.logs.append(f"✉️ 검출 결과가 존재하여 즉시 이메일 전송을 시작합니다... (수신: {state.receiver_email})")
            mail_sent, err_msg = send_report_email(
                smtp_server=state.smtp_server,
                smtp_port=state.smtp_port,
                smtp_user=state.smtp_user,
                smtp_password=state.smtp_password,
                receiver_email=state.receiver_email,
                results_list=results,
                timestamp=state.last_run_timestamp
            )
            if mail_sent:
                state.logs.append("✅ 리포트 이메일이 성공적으로 전송되었습니다.")
            else:
                state.logs.append(f"❌ 이메일 전송에 실패했습니다. (원인: {err_msg})")
                
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        state.logs.append(f"❌ 크롤링 중 치명적인 오류 발생: {str(e)}")
        state.logs.append("상세 에러 내용:")
        for line in tb_str.split('\n'):
            if line.strip():
                state.logs.append(f"  {line}")
        state.progress_percent = 100
    finally:
        state.is_running = False

@app.post("/api/start-crawl")
async def start_crawl(req: StartCrawlRequest):
    """크롤링 시작 요청"""
    # 만약 이전 태스크가 존재하고 실행 중이라면 강제 취소 (중복 기동 차단)
    if state.current_task and not state.current_task.done():
        try:
            state.current_task.cancel()
            state.logs.append("🛑 [시스템] 이전 동작 중인 수집 프로세스를 강제 중단 및 초기화했습니다.")
            await asyncio.sleep(0.5)
        except Exception as cancel_err:
            print(f"이전 태스크 취소 중 예외: {cancel_err}")

    state.naver_cookie = req.naver_cookie or ""
    save_settings()
    
    task = asyncio.create_task(
        background_crawl_task(
            keywords=req.keywords,
            my_domains=req.my_domains,
            my_stores=req.my_stores,
            excluded_companies=req.excluded_companies,
            is_auto=False,
            send_email=req.send_email
        )
    )
    state.current_task = task
    return {"message": "크롤링 태스크가 시작되었습니다."}

@app.post("/api/stop-crawl")
async def stop_crawl():
    if state.current_task and not state.current_task.done():
        try:
            state.current_task.cancel()
        except Exception as e:
            print(f"태스크 중단 중 오류: {e}")
            
    state.is_running = False
    state.progress_percent = 0
    state.logs.append("🛑 사용자에 의해 크롤링이 중단되었습니다.")
    return {"message": "크롤링 태스크를 중단했습니다."}

# ----------------- 이메일 리포트용 자동 비동기 스케줄러 -----------------

async def scheduler_loop():
    """백엔드 정기 스캔 비동기 루프 (30초마다 설정 확인)"""
    await asyncio.sleep(15) # 부팅 후 잠시 대기
    print("⏰ [System] 정기 모니터링 백엔드 스케줄러가 구동되었습니다.")
    
    last_run_time = None
    
    while True:
        try:
            if state.scheduler_active and state.target_keywords and not state.is_running:
                now = datetime.now()
                # 최초 실행이거나 설정된 주기(분) 이상 경과한 경우
                if last_run_time is None or (now - last_run_time).total_seconds() >= (state.scheduler_interval * 60):
                    last_run_time = now
                    # 백그라운드로 자동 스크랩 수행
                    await background_crawl_task(
                        keywords=state.target_keywords,
                        my_domains=state.my_domains,
                        my_stores=state.my_stores,
                        is_auto=True
                    )
        except Exception as se:
            print(f"Scheduler Loop Error: {se}")
            
        await asyncio.sleep(30) # 30초마다 기상하여 체크

# ----------------- 파일 다운로드 API -----------------

@app.get("/api/download/original-excel")
async def download_original_excel():
    if not state.results:
        raise HTTPException(status_code=400, detail="다운로드할 데이터가 존재하지 않습니다.")
    df = pd.DataFrame(state.results)
    export_df = df.drop(columns=['screenshot']) if 'screenshot' in df.columns else df
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, sheet_name='전체', index=False)
        powerlink_df = export_df[export_df['ad_type'] == '파워링크']
        if len(powerlink_df) > 0:
            powerlink_df.to_excel(writer, sheet_name='파워링크', index=False)
        shopping_df = export_df[export_df['ad_type'] == '쇼핑광고']
        if len(shopping_df) > 0:
            shopping_df.to_excel(writer, sheet_name='쇼핑광고', index=False)
            
    output.seek(0)
    filename = f"naver_ads_{state.last_run_timestamp or 'empty'}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/download/complaint-excel")
async def download_complaint_excel():
    if not state.results:
        raise HTTPException(status_code=400, detail="다운로드할 데이터가 존재하지 않습니다.")
    df = pd.DataFrame(state.results)
    columns_to_keep = ['keyword', 'company', 'product_name', 'url']
    for col in columns_to_keep:
        if col not in df.columns:
            df[col] = ""
    complaint_df = df[columns_to_keep].copy()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        complaint_df.to_excel(writer, index=False)
        
    output.seek(0)
    filename = f"complaint_format_{state.last_run_timestamp or 'empty'}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/download/complaint-text")
async def download_complaint_text():
    if not state.results:
        raise HTTPException(status_code=400, detail="다운로드할 데이터가 존재하지 않습니다.")
    text_content = format_complaint_text(state.results)
    output = BytesIO(text_content.encode('utf-8'))
    filename = f"complaint_text_{state.last_run_timestamp or 'empty'}.txt"
    return StreamingResponse(
        output,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/download/screenshots")
async def download_screenshots():
    zip_bytes = create_screenshots_zip_bytes()
    if not zip_bytes:
        raise HTTPException(status_code=400, detail="다운로드할 스크린샷 이미지 파일이 존재하지 않습니다.")
    filename = f"screenshots_{state.last_run_timestamp or 'empty'}.zip"
    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# 빌드된 프론트엔드 정적 서빙 (Node.js 미설치 환경에서도 단일 파이썬 서버로 완전 구동)
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # uvicorn 기동 전에 8989 포트를 정리
    kill_port_owner(8989)
    # Windows Playwright 비동기 subprocess 호환성을 위해 reload=False로 고정
    uvicorn.run("main:app", host="0.0.0.0", port=8989, reload=False)

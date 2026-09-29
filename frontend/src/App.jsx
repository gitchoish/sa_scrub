import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Square, 
  Download, 
  Copy, 
  Plus, 
  Trash2, 
  ExternalLink, 
  FileText, 
  Image as ImageIcon, 
  ShieldCheck, 
  Loader2, 
  Target, 
  X,
  FileSpreadsheet,
  Globe,
  Store,
  Mail,
  Clock,
  Send,
  Save,
  Info,
  CheckCircle2,
  Key,
  ShieldAlert
} from 'lucide-react';
import './App.css';

const API_BASE = 'http://127.0.0.1:8989';

// 타임스탬프 파싱 헬퍼 (YYYYMMDD_HHmmss -> Date 객체)
const parseTimestamp = (ts) => {
  if (!ts || ts.length < 15) return null;
  const year = parseInt(ts.substring(0, 4));
  const month = parseInt(ts.substring(4, 6)) - 1;
  const day = parseInt(ts.substring(6, 8));
  const hour = parseInt(ts.substring(9, 11));
  const minute = parseInt(ts.substring(11, 13));
  const second = parseInt(ts.substring(13, 15));
  return new Date(year, month, day, hour, minute, second);
};

// 경과 상대시간 포맷터
const formatRelativeTime = (ts) => {
  const date = parseTimestamp(ts);
  if (!date) return '기록 없음';
  
  const diffMs = new Date() - date;
  if (diffMs < 0) return '방금 전';
  
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return '방금 전';
  if (diffMins < 60) return `${diffMins}분 전`;
  
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}시간 전`;
  
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}일 전`;
};

function App() {
  // 키워드 및 제외 설정 상태
  const [targetKeywords, setTargetKeywords] = useState([]);
  const [myDomains, setMyDomains] = useState([]);
  const [myStores, setMyStores] = useState([]);
  const [naverCookie, setNaverCookie] = useState('');
  
  const [newTarget, setNewTarget] = useState('');
  const [newDomain, setNewDomain] = useState('');
  const [newStore, setNewStore] = useState('');
  const [excludedCompanies, setExcludedCompanies] = useState([]);
  const [newExcludedCompany, setNewExcludedCompany] = useState('');

  // 스케줄러 & SMTP 설정 상태
  const [schedulerActive, setSchedulerActive] = useState(false);
  const [schedulerInterval, setSchedulerInterval] = useState(30);
  const [smtpPreset, setSmtpPreset] = useState('gmail'); // gmail, naver, custom
  const [smtpServer, setSmtpServer] = useState('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [receiverEmail, setReceiverEmail] = useState('');
  const [isMailTesting, setIsMailTesting] = useState(false);

  // 크롤링 진행 상태
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [results, setResults] = useState([]);
  const [complaintText, setComplaintText] = useState('');
  const [lastTimestamp, setLastTimestamp] = useState('');
  const [isLoaded, setIsLoaded] = useState(false);

  // UI 상태
  const [activeTab, setActiveTab] = useState('all'); // all, powerlink, shopping
  const [modalImage, setModalImage] = useState(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [timeTick, setTimeTick] = useState(0); // 상대시간 실시간 갱신용
  
  const logEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // 초기 로드
  useEffect(() => {
    fetchConfig();
    fetchSchedulerConfig();
    fetchCurrentStatus();
    return () => clearInterval(pollIntervalRef.current);
  }, []);

  // 30초마다 화면 상대 경과시간 업데이트
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeTick(prev => prev + 1);
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  // 로그 스크롤
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // 상태 폴링
  useEffect(() => {
    if (isRunning) {
      pollIntervalRef.current = setInterval(fetchCurrentStatus, 1500);
    } else {
      clearInterval(pollIntervalRef.current);
      fetchResults();
    }
    return () => clearInterval(pollIntervalRef.current);
  }, [isRunning]);

  // 프리셋 선택 시 서버 정보 자동 세팅
  useEffect(() => {
    if (smtpPreset === 'gmail') {
      setSmtpServer('smtp.gmail.com');
      setSmtpPort(587);
    } else if (smtpPreset === 'naver') {
      setSmtpServer('smtp.naver.com');
      setSmtpPort(587);
    }
  }, [smtpPreset]);

  // 이메일 및 스케줄 설정 변경 시 1.5초 디바운스로 백엔드 자동 보존
  useEffect(() => {
    if (!smtpUser && !smtpPassword && !receiverEmail) return;
    const delayDebounce = setTimeout(() => {
      autoSaveSchedulerConfig();
    }, 1500);
    return () => clearTimeout(delayDebounce);
  }, [schedulerActive, schedulerInterval, smtpServer, smtpPort, smtpUser, smtpPassword, receiverEmail]);

  const autoSaveSchedulerConfig = async () => {
    try {
      await fetch(`${API_BASE}/api/scheduler/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scheduler_active: schedulerActive,
          scheduler_interval: parseInt(schedulerInterval),
          smtp_server: smtpServer,
          smtp_port: parseInt(smtpPort),
          smtp_user: smtpUser,
          smtp_password: smtpPassword,
          receiver_email: receiverEmail
        })
      });
      console.log("⚙️ 이메일 및 스케줄러 설정 백그라운드 자동 저장 완료");
    } catch (e) {
      console.error("Auto-save failed:", e);
    }
  };

  // 키워드 및 각종 필터/쿠키 설정 변경 시 1초 디바운스로 백엔드 동기화 자동 저장
  useEffect(() => {
    if (!isLoaded) return;
    const delayDebounce = setTimeout(() => {
      autoSaveConfig();
    }, 1000);
    return () => clearTimeout(delayDebounce);
  }, [isLoaded, targetKeywords, myDomains, myStores, excludedCompanies, naverCookie]);

  const autoSaveConfig = async () => {
    try {
      await fetch(`${API_BASE}/api/config/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: targetKeywords,
          my_domains: myDomains,
          my_stores: myStores,
          excluded_companies: excludedCompanies,
          naver_cookie: naverCookie
        })
      });
      console.log("⚙️ 키워드 및 필터 설정 백엔드 동기화 완료");
    } catch (e) {
      console.error("Config save failed:", e);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config`);
      const data = await res.json();
      setTargetKeywords(data.default_keywords || []);
      setMyDomains(data.default_my_domains || []);
      setMyStores(data.default_my_stores || []);
      setExcludedCompanies(data.default_excluded_companies || []);
      setNaverCookie(data.default_naver_cookie || '');
      setIsLoaded(true);
    } catch (e) {
      addLocalLog(`❌ 백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요. (${e.message})`);
    }
  };

  const fetchSchedulerConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/scheduler/config`);
      const data = await res.json();
      setSchedulerActive(data.scheduler_active);
      setSchedulerInterval(data.scheduler_interval);
      setSmtpServer(data.smtp_server || 'smtp.gmail.com');
      setSmtpPort(data.smtp_port || 587);
      setSmtpUser(data.smtp_user || '');
      setSmtpPassword(data.smtp_password || '');
      setReceiverEmail(data.receiver_email || '');
      
      // 불러온 서버 도메인에 따라 프리셋 역지정
      if (data.smtp_server === 'smtp.gmail.com') {
        setSmtpPreset('gmail');
      } else if (data.smtp_server === 'smtp.naver.com') {
        setSmtpPreset('naver');
      } else if (data.smtp_server) {
        setSmtpPreset('custom');
      }
    } catch (e) {
      console.error("Error fetching scheduler config:", e);
    }
  };

  const fetchCurrentStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setIsRunning(data.is_running);
      setProgress(data.progress_percent);
      setLogs(data.logs || []);
      
      if (!data.is_running && isRunning) {
        fetchResults();
      }
    } catch (e) {
      console.error("Error fetching status:", e);
    }
  };

  const fetchResults = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/results`);
      const data = await res.json();
      setResults(data.results || []);
      setComplaintText(data.complaint_text || '');
      setLastTimestamp(data.last_run_timestamp || '');
    } catch (e) {
      console.error("Error fetching results:", e);
    }
  };

  const addLocalLog = (msg) => {
    setLogs(prev => [...prev, `[시스템] ${msg}`]);
  };

  // 키워드 관리 핸들러
  const handleAddTarget = () => {
    const val = newTarget.trim();
    if (!val) return;
    if (targetKeywords.includes(val)) {
      alert("이미 등록된 키워드입니다.");
      return;
    }
    setTargetKeywords([...targetKeywords, val]);
    setNewTarget('');
  };

  const handleRemoveTarget = (index) => {
    setTargetKeywords(targetKeywords.filter((_, i) => i !== index));
  };

  const handleAddDomain = () => {
    const val = newDomain.trim();
    if (!val) return;
    if (myDomains.includes(val)) {
      alert("이미 등록된 도메인 주소입니다.");
      return;
    }
    setMyDomains([...myDomains, val]);
    setNewDomain('');
  };

  const handleRemoveDomain = (index) => {
    setMyDomains(myDomains.filter((_, i) => i !== index));
  };

  const handleAddStore = () => {
    const val = newStore.trim();
    if (!val) return;
    if (myStores.includes(val)) {
      alert("이미 등록된 스토어 이름입니다.");
      return;
    }
    setMyStores([...myStores, val]);
    setNewStore('');
  };

  const handleRemoveStore = (index) => {
    setMyStores(myStores.filter((_, i) => i !== index));
  };
  
  const handleAddExcluded = () => {
    const val = newExcludedCompany.trim();
    if (!val) return;
    if (excludedCompanies.includes(val)) {
      alert("이미 등록된 경쟁사 이름입니다.");
      return;
    }
    setExcludedCompanies([...excludedCompanies, val]);
    setNewExcludedCompany('');
  };

  const handleRemoveExcluded = (index) => {
    setExcludedCompanies(excludedCompanies.filter((_, i) => i !== index));
  };

  const handleQuickScan = async (keyword) => {
    if (isRunning) return;
    try {
      setIsRunning(true);
      setProgress(0);
      setLogs([`🚀 키워드 '${keyword}' 개별 즉시 스캔 요청 중...`]);
      
      const res = await fetch(`${API_BASE}/api/start-crawl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: [keyword],
          my_domains: myDomains,
          my_stores: myStores,
          excluded_companies: excludedCompanies,
          naver_cookie: naverCookie,
          send_email: false
        })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "퀵 스캔 시작 실패");
      }
    } catch (e) {
      setIsRunning(false);
      addLocalLog(`❌ 퀵 스캔 오류: ${e.message}`);
    }
  };

  // 스케줄러 & SMTP 설정 저장
  const handleSaveScheduler = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/scheduler/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scheduler_active: schedulerActive,
          scheduler_interval: parseInt(schedulerInterval),
          smtp_server: smtpServer,
          smtp_port: parseInt(smtpPort),
          smtp_user: smtpUser,
          smtp_password: smtpPassword,
          receiver_email: receiverEmail
        })
      });
      if (res.ok) {
        alert("스케줄러 및 이메일 설정이 저장되었습니다.");
      } else {
        alert("설정 저장 실패");
      }
    } catch (e) {
      alert(`오류: ${e.message}`);
    }
  };

  // 테스트 메일 발송
  const handleSendTestEmail = async () => {
    if (!smtpUser || !smtpPassword || !receiverEmail) {
      alert("보내는 메일(계정), 비밀번호, 받는 메일 주소를 모두 기입해 주세요.");
      return;
    }
    try {
      setIsMailTesting(true);
      const res = await fetch(`${API_BASE}/api/scheduler/test-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          smtp_server: smtpServer,
          smtp_port: parseInt(smtpPort),
          smtp_user: smtpUser,
          smtp_password: smtpPassword,
          receiver_email: receiverEmail
        })
      });
      const data = await res.json();
      setIsMailTesting(false);
      if (res.ok) {
        alert("테스트 이메일이 발송되었습니다! 수신함을 확인하세요.");
      } else {
        alert(`발송 실패: ${data.detail || "알 수 없는 오류"}`);
      }
    } catch (e) {
      setIsMailTesting(false);
      alert(`오류: ${e.message}`);
    }
  };

  // 실행 제어
  const startScraping = async () => {
    if (targetKeywords.length === 0) {
      alert("스캔할 타겟 키워드를 최소 1개 이상 등록해 주세요.");
      return;
    }

    try {
      setIsRunning(true);
      setProgress(0);
      setLogs(["🚀 백엔드 크롤러에 요청 전달 중..."]);
      
      const res = await fetch(`${API_BASE}/api/start-crawl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: targetKeywords,
          my_domains: myDomains,
          my_stores: myStores,
          excluded_companies: excludedCompanies,
          naver_cookie: naverCookie
        })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "크롤링 시작 실패");
      }
    } catch (e) {
      setIsRunning(false);
      addLocalLog(`❌ 시작 오류: ${e.message}`);
      
      // "이미 진행 중" 또는 유령 락 상태 감지 시 자동 락 해제
      if (e.message.includes("이미 진행 중")) {
        try {
          await fetch(`${API_BASE}/api/stop-crawl`, { method: 'POST' });
          addLocalLog("⚙️ 진행 상태 락을 자동으로 감지하여 강제 초기화(리셋)했습니다. [광고 모니터링 시작]을 다시 한 번 클릭하시면 즉시 시작됩니다!");
        } catch (resetErr) {
          console.error("Auto reset failed:", resetErr);
        }
      }
    }
  };

  const stopScraping = async () => {
    try {
      await fetch(`${API_BASE}/api/stop-crawl`, { method: 'POST' });
      setIsRunning(false);
    } catch (e) {
      console.error(e);
    }
  };

  const copyToClipboard = () => {
    if (!complaintText) return;
    navigator.clipboard.writeText(complaintText);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const filteredResults = results.filter(item => {
    if (activeTab === 'all') return true;
    if (activeTab === 'powerlink') return item.ad_type === '파워링크';
    if (activeTab === 'shopping') return item.ad_type === '쇼핑광고';
    if (activeTab === 'pc') return item.device === 'PC';
    if (activeTab === 'mobile') return item.device === '모바일';
    return true;
  });

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '40px 20px' }}>
      
      {/* Header */}
      <header style={{ marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, background: 'linear-gradient(90deg, #818cf8, #22d3ee)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', letterSpacing: '-0.5px' }}>
            네이버 검색광고 침해 모니터링 & 신고 시스템
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginTop: '4px' }}>
            브랜드 키워드를 도용 중인 무단 경쟁사 광고를 수집하고 제재 양식을 자동으로 조립합니다.
          </p>
        </div>
        
        {/* Status Indicator */}
        <div className="glass-panel" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isRunning ? (
            <>
              <Loader2 className="spin" style={{ color: 'var(--accent-secondary)', width: '18px', height: '18px' }} />
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-secondary)' }}>모니터링 분석 진행 중</span>
            </>
          ) : (
            <>
              <ShieldCheck style={{ color: 'var(--accent-success)', width: '18px', height: '18px' }} />
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>대기 중 / 스캔 완료</span>
            </>
          )}
        </div>
      </header>

      {/* Main Dashboard Grid */}
      <div className="dashboard-grid">
        
        {/* Left Control Panel */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Target Keywords Panel */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Target style={{ color: 'var(--accent-primary)', width: '20px', height: '20px' }} />
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>모니터링 대상 키워드</h2>
            </div>
            
            <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
              <input 
                type="text" 
                className="glass-input" 
                placeholder="스캔할 키워드 입력" 
                value={newTarget}
                onChange={e => setNewTarget(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAddTarget()}
                style={{ flex: 1, fontSize: '0.85rem' }}
                disabled={isRunning}
              />
              <button 
                onClick={handleAddTarget}
                style={{ background: 'var(--accent-primary)', border: 'none', borderRadius: '8px', width: '38px', cursor: 'pointer', display: 'grid', placeContent: 'center', color: 'white' }}
                disabled={isRunning}
              >
                <Plus width={18} height={18} />
              </button>
            </div>

            <div style={{ maxHeight: '150px', overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: '8px', padding: '6px' }}>
              {targetKeywords.length === 0 ? (
                <div style={{ color: 'var(--text-dark)', fontSize: '0.8rem', textAlign: 'center', padding: '20px' }}>등록된 키워드가 없습니다.</div>
              ) : (
                targetKeywords.map((kw, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', marginBottom: '4px', fontSize: '0.85rem' }}>
                    <span style={{ color: 'var(--text-primary)' }}>{kw}</span>
                    {!isRunning && (
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <button 
                          onClick={() => handleQuickScan(kw)}
                          title="이 키워드만 즉시 스캔 (메일 발송 안 함)"
                          style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                        >
                          <Play width={14} height={14} className="hover-green" style={{ transition: 'var(--transition-smooth)' }} />
                        </button>
                        <button 
                          onClick={() => handleRemoveTarget(idx)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                        >
                          <Trash2 width={14} height={14} className="hover-red" style={{ transition: 'var(--transition-smooth)' }} />
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Excluded My Brands */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <ShieldCheck style={{ color: 'var(--accent-success)', width: '20px', height: '20px' }} />
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>내 브랜드 제외 필터 설정</h2>
            </div>
            
            {/* 1. Powerlink Exclusion (Domain Match) */}
            <div style={{ marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                <Globe style={{ color: 'var(--accent-secondary)', width: '14px', height: '14px' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>내 도메인 주소 (파워링크 제외)</span>
              </div>
              <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                <input 
                  type="text" 
                  className="glass-input" 
                  placeholder="예: daypack (도메인 일부)" 
                  value={newDomain}
                  onChange={e => setNewDomain(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddDomain()}
                  style={{ flex: 1, fontSize: '0.8rem', padding: '8px 10px' }}
                  disabled={isRunning}
                />
                <button 
                  onClick={handleAddDomain}
                  style={{ background: 'var(--accent-secondary)', border: 'none', borderRadius: '8px', width: '32px', cursor: 'pointer', display: 'grid', placeContent: 'center', color: 'white' }}
                  disabled={isRunning}
                >
                  <Plus width={16} height={16} />
                </button>
              </div>
              <div style={{ maxHeight: '90px', overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: '8px', padding: '4px' }}>
                {myDomains.length === 0 ? (
                  <div style={{ color: 'var(--text-dark)', fontSize: '0.75rem', textAlign: 'center', padding: '10px' }}>등록된 제외 도메인이 없습니다.</div>
                ) : (
                  myDomains.map((domain, idx) => (
                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.01)', marginBottom: '3px', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text-primary)' }}>{domain}</span>
                      {!isRunning && (
                        <button 
                          onClick={() => handleRemoveDomain(idx)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer' }}
                        >
                          <Trash2 width={12} height={12} className="hover-red" />
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 2. Shopping Exclusion (Store Name Match) */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                <Store style={{ color: 'var(--accent-success)', width: '14px', height: '14px' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>내 스토어명 (쇼핑광고 제외)</span>
              </div>
              <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                <input 
                  type="text" 
                  className="glass-input" 
                  placeholder="예: 데이팩 (상호명 일부)" 
                  value={newStore}
                  onChange={e => setNewStore(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddStore()}
                  style={{ flex: 1, fontSize: '0.8rem', padding: '8px 10px' }}
                  disabled={isRunning}
                />
                <button 
                  onClick={handleAddStore}
                  style={{ background: 'var(--accent-success)', border: 'none', borderRadius: '8px', width: '32px', cursor: 'pointer', display: 'grid', placeContent: 'center', color: 'white' }}
                  disabled={isRunning}
                >
                  <Plus width={16} height={16} />
                </button>
              </div>
              <div style={{ maxHeight: '90px', overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: '8px', padding: '4px' }}>
                {myStores.length === 0 ? (
                  <div style={{ color: 'var(--text-dark)', fontSize: '0.75rem', textAlign: 'center', padding: '10px' }}>등록된 제외 스토어명이 없습니다.</div>
                ) : (
                  myStores.map((store, idx) => (
                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.01)', marginBottom: '3px', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text-primary)' }}>{store}</span>
                      {!isRunning && (
                        <button 
                          onClick={() => handleRemoveStore(idx)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer' }}
                        >
                          <Trash2 width={12} height={12} className="hover-red" />
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
            
            {/* Excluded Competitors Panel */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <ShieldAlert style={{ color: 'var(--accent-secondary)', width: '20px', height: '20px' }} />
                <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>수집 제외 경쟁사 설정</h2>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.4', marginBottom: '12px' }}>
                수집 리스트에 노출시키고 싶지 않은 대형 오픈마켓이나 특정 경쟁사명을 지정합니다. (예: 쿠팡, G마켓)
              </p>
              
              <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                <input 
                  type="text" 
                  className="glass-input" 
                  placeholder="제외할 경쟁사명 입력" 
                  value={newExcludedCompany}
                  onChange={e => setNewExcludedCompany(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddExcluded()}
                  style={{ flex: 1, fontSize: '0.8rem', padding: '8px 10px' }}
                  disabled={isRunning}
                />
                <button 
                  onClick={handleAddExcluded}
                  style={{ background: 'var(--accent-secondary)', border: 'none', borderRadius: '8px', width: '32px', cursor: 'pointer', display: 'grid', placeContent: 'center', color: 'white' }}
                  disabled={isRunning}
                >
                  <Plus width={16} height={16} />
                </button>
              </div>
              
              <div style={{ maxHeight: '110px', overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: '8px', padding: '4px' }}>
                {excludedCompanies.length === 0 ? (
                  <div style={{ color: 'var(--text-dark)', fontSize: '0.75rem', textAlign: 'center', padding: '10px' }}>등록된 제외 경쟁사가 없습니다.</div>
                ) : (
                  excludedCompanies.map((comp, idx) => (
                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.01)', marginBottom: '3px', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text-primary)' }}>{comp}</span>
                      {!isRunning && (
                        <button 
                          onClick={() => handleRemoveExcluded(idx)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer' }}
                        >
                          <Trash2 width={12} height={12} className="hover-red" />
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>

          {/* Naver Login Session Cookie Panel */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Key style={{ color: 'var(--accent-secondary)', width: '20px', height: '20px' }} />
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>네이버 로그인 세션 쿠키</h2>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.4', marginBottom: '12px' }}>
              연령대/성별 가중치가 적용된 광고 소재를 정확하게 수집하기 위해 본인의 네이버 세션 쿠키 문자열을 기입합니다.
            </p>
            <textarea 
              className="glass-input" 
              placeholder="쿠키 문자열 (ex: NID_AUT=...; NID_SES=...)"
              value={naverCookie}
              onChange={e => setNaverCookie(e.target.value)}
              style={{ width: '100%', height: '110px', fontSize: '0.75rem', padding: '8px 10px', resize: 'none', fontFamily: 'monospace' }}
              disabled={isRunning}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
              <span style={{ fontSize: '0.7rem', color: naverCookie ? 'var(--accent-success)' : 'var(--text-dark)', fontWeight: 600 }}>
                {naverCookie ? "✓ 로그인 쿠키 기입됨" : "쿠키 미입력 (비로그인 스캔)"}
              </span>
            </div>
          </div>

        </aside>

        {/* Right Main Screen */}
        <main style={{ display: 'flex', flexDirection: 'column', gap: '24px', minWidth: 0 }}>
          
          {/* Action Trigger & Progress Bar Panel */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>작업 제어 장치</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>네이버 모바일 및 PC 통합 광고 스크랩 및 증빙 수집 태스크를 실행합니다.</p>
              </div>
              
              <div style={{ display: 'flex', gap: '12px' }}>
                {isRunning ? (
                  <button 
                    onClick={stopScraping}
                    style={{ background: 'var(--accent-danger)', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontWeight: 600, transition: 'var(--transition-smooth)' }}
                  >
                    <Square width={16} height={16} fill="white" />
                    스캔 중단
                  </button>
                ) : (
                  <button 
                    onClick={startScraping}
                    style={{ background: 'var(--accent-primary)', border: 'none', padding: '10px 24px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontWeight: 600, transition: 'var(--transition-smooth)' }}
                  >
                    <Play width={16} height={16} fill="white" />
                    광고 모니터링 시작
                  </button>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>진행 속도 및 게이지</span>
                <span style={{ fontWeight: 700, color: 'var(--accent-secondary)' }}>{progress}%</span>
              </div>
              <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '9999px', overflow: 'hidden' }}>
                <div style={{ width: `${progress}%`, height: '100%', background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))', borderRadius: '9999px', transition: 'width 0.4s ease' }}></div>
              </div>
            </div>

            {/* Crawler Terminal Logs */}
            <div style={{ background: '#070a13', border: '1px solid var(--card-border)', borderRadius: '10px', padding: '16px', height: '160px', overflowY: 'auto', fontFamily: 'Courier New, Courier, monospace', fontSize: '0.8rem' }}>
              {logs.length === 0 ? (
                <div style={{ color: 'var(--text-dark)', fontStyle: 'italic' }}>스캔 로그가 이곳에 출력됩니다...</div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} style={{ 
                    color: log.includes('⚠️') ? '#f59e0b' : log.includes('❌') ? '#ef4444' : log.includes('✓') ? '#10b981' : '#a1a1aa',
                    marginBottom: '4px',
                    whiteSpace: 'pre-wrap'
                  }}>
                    {log}
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* Email Scheduler settings panel */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Mail style={{ color: 'var(--accent-primary)', width: '20px', height: '20px' }} />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>정기 스케줄 및 이메일 자동 리포트 설정</h3>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }} className="dashboard-grid">
              
              {/* Left Column: Schedule settings */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.02)', padding: '12px', border: '1px solid var(--card-border)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Clock style={{ width: '18px', height: '18px', color: 'var(--accent-secondary)' }} />
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>정기 자동 스캔 활성화</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>로컬 런처 실행 중 주기적으로 수집</div>
                    </div>
                  </div>
                  <label style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
                    <input 
                      type="checkbox" 
                      className="custom-checkbox" 
                      checked={schedulerActive} 
                      onChange={e => setSchedulerActive(e.target.checked)} 
                    />
                  </label>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '6px' }}>
                    <span style={{ fontWeight: 600 }}>자동 실행 간격 (주기)</span>
                    <span style={{ color: 'var(--accent-secondary)', fontWeight: 700 }}>{schedulerInterval}분 간격</span>
                  </div>
                  <input 
                    type="range" 
                    min="5" 
                    max="180" 
                    step="5"
                    value={schedulerInterval}
                    onChange={e => setSchedulerInterval(e.target.value)}
                    style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                    <span>최소 5분</span>
                    <span>1시간</span>
                    <span>최대 3시간 (180분)</span>
                  </div>
                </div>

                <div style={{ background: 'rgba(99, 102, 241, 0.05)', border: '1px solid rgba(99, 102, 241, 0.2)', padding: '12px', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  <Info width={16} height={16} style={{ color: 'var(--accent-primary)', flexShrink: 0, marginTop: '2px' }} />
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                    **주의**: 정기 자동 스캔은 런처 터미널 창(`run.bat`)이 켜져 있는 동안에만 백그라운드에서 동작합니다. 경쟁사가 검출될 때만 리포트 메일이 발송됩니다.
                  </p>
                </div>
              </div>

              {/* Right Column: SMTP mail settings */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', gap: '8px', fontSize: '0.8rem', marginBottom: '4px' }}>
                  <button 
                    onClick={() => setSmtpPreset('gmail')}
                    style={{ flex: 1, padding: '6px', background: smtpPreset === 'gmail' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', borderRadius: '6px', color: 'white', fontSize: '0.75rem', cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    Gmail
                  </button>
                  <button 
                    onClick={() => setSmtpPreset('naver')}
                    style={{ flex: 1, padding: '6px', background: smtpPreset === 'naver' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', borderRadius: '6px', color: 'white', fontSize: '0.75rem', cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    네이버 메일
                  </button>
                  <button 
                    onClick={() => setSmtpPreset('custom')}
                    style={{ flex: 1, padding: '6px', background: smtpPreset === 'custom' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', borderRadius: '6px', color: 'white', fontSize: '0.75rem', cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    직접 기입
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px', gap: '10px' }}>
                  <input 
                    type="text" 
                    className="glass-input" 
                    placeholder="SMTP 서버 주소"
                    value={smtpServer}
                    onChange={e => { setSmtpServer(e.target.value); setSmtpPreset('custom'); }}
                    style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                  />
                  <input 
                    type="number" 
                    className="glass-input" 
                    placeholder="Port"
                    value={smtpPort}
                    onChange={e => { setSmtpPort(e.target.value); setSmtpPreset('custom'); }}
                    style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                  />
                </div>

                <input 
                  type="text" 
                  className="glass-input" 
                  placeholder="보내는 메일 (ID 또는 전체 이메일 주소)"
                  value={smtpUser}
                  onChange={e => setSmtpUser(e.target.value)}
                  style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                />
                
                <input 
                  type="password" 
                  className="glass-input" 
                  placeholder="비밀번호 (Gmail의 경우 '앱 비밀번호')"
                  value={smtpPassword}
                  onChange={e => setSmtpPassword(e.target.value)}
                  style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                />

                <input 
                  type="email" 
                  className="glass-input" 
                  placeholder="리포트 보고를 받을 이메일 주소"
                  value={receiverEmail}
                  onChange={e => setReceiverEmail(e.target.value)}
                  style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                />

                <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                  <button 
                    onClick={handleSaveScheduler}
                    style={{ flex: 1.5, background: 'var(--accent-primary)', border: 'none', color: 'white', padding: '8px 12px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'var(--transition-smooth)' }}
                    className="btn-hover-glow"
                  >
                    <Save width={14} height={14} />
                    설정 저장
                  </button>
                  <button 
                    onClick={handleSendTestEmail}
                    disabled={isMailTesting}
                    style={{ flex: 1, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', color: 'white', padding: '8px 12px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'var(--transition-smooth)' }}
                  >
                    {isMailTesting ? (
                      <Loader2 className="spin" width={14} height={14} />
                    ) : (
                      <Send width={14} height={14} />
                    )}
                    테스트 전송
                  </button>
                </div>
              </div>

            </div>
          </div>

          {/* Results Analysis & Download Center */}
          {results.length > 0 && (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>검출된 경쟁사 광고 목록</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '2px' }}>
                    총 {results.length}개의 타사 브랜드 침해 광고가 발견되었습니다. (최근 분석: <span style={{ color: 'var(--accent-secondary)', fontWeight: 700 }}>{formatRelativeTime(lastTimestamp)}</span>{lastTimestamp ? ` / ${lastTimestamp.substring(0,4)}-${lastTimestamp.substring(4,6)}-${lastTimestamp.substring(6,8)} ${lastTimestamp.substring(9,11)}:${lastTimestamp.substring(11,13)}` : ''})
                  </p>
                </div>
                
                {/* Result Tabs */}
                <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '8px', border: '1px solid var(--card-border)', flexWrap: 'wrap' }}>
                  <button 
                    onClick={() => setActiveTab('all')} 
                    style={{ background: activeTab === 'all' ? 'var(--accent-primary)' : 'none', border: 'none', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    전체 ({results.length})
                  </button>
                  <button 
                    onClick={() => setActiveTab('powerlink')} 
                    style={{ background: activeTab === 'powerlink' ? 'var(--accent-primary)' : 'none', border: 'none', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    파워링크 ({results.filter(r => r.ad_type === '파워링크').length})
                  </button>
                  <button 
                    onClick={() => setActiveTab('shopping')} 
                    style={{ background: activeTab === 'shopping' ? 'var(--accent-primary)' : 'none', border: 'none', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    쇼핑광고 ({results.filter(r => r.ad_type === '쇼핑광고').length})
                  </button>
                  <button 
                    onClick={() => setActiveTab('pc')} 
                    style={{ background: activeTab === 'pc' ? '#3b82f6' : 'none', border: 'none', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    💻 PC ({results.filter(r => r.device === 'PC').length})
                  </button>
                  <button 
                    onClick={() => setActiveTab('mobile')} 
                    style={{ background: activeTab === 'mobile' ? '#10b981' : 'none', border: 'none', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'var(--transition-smooth)' }}
                  >
                    📱 모바일 ({results.filter(r => r.device === '모바일').length})
                  </button>
                </div>
              </div>

              {/* Result Table */}
              <div style={{ overflowX: 'auto', border: '1px solid var(--card-border)', borderRadius: '10px', marginBottom: '24px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--card-border)', background: 'rgba(255,255,255,0.02)' }}>
                      <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>구분</th>
                      <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>키워드</th>
                      <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>경쟁사명</th>
                      <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>노출상품명</th>
                      <th style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>랜딩 URL</th>
                      <th style={{ padding: '12px 16px', color: 'var(--text-muted)', textAlign: 'center' }}>증빙자료</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredResults.length === 0 ? (
                      <tr>
                        <td colSpan="6" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-dark)' }}>해당 분류에 검출된 결과가 없습니다.</td>
                      </tr>
                    ) : (
                      filteredResults.map((item, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', height: '48px', verticalAlign: 'middle' }}>
                          <td style={{ padding: '8px 16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span className={`status-badge ${item.ad_type === '파워링크' ? 'powerlink' : 'shopping'}`}>
                                {item.ad_type}
                              </span>
                              <span style={{ 
                                fontSize: '0.7rem', 
                                padding: '2px 6px', 
                                borderRadius: '4px', 
                                background: item.device === 'PC' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(16, 185, 129, 0.15)', 
                                color: item.device === 'PC' ? '#60a5fa' : '#34d399', 
                                fontWeight: 600,
                                border: `1px solid ${item.device === 'PC' ? 'rgba(59, 130, 246, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`
                              }}>
                                {item.device || '모바일'}
                              </span>
                            </div>
                          </td>
                          <td style={{ padding: '8px 16px', fontWeight: 600 }}>{item.keyword}</td>
                          <td style={{ padding: '8px 16px', color: '#6366f1' }}>{item.company}</td>
                          <td style={{ padding: '8px 16px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '160px' }}>
                            {item.product_name || '-'}
                          </td>
                          <td style={{ padding: '8px 16px' }}>
                            {item.url ? (
                              <a href={item.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-secondary)', display: 'inline-flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }} className="hover-underline">
                                URL 열기
                                <ExternalLink width={12} height={12} />
                              </a>
                            ) : '-'}
                          </td>
                          <td style={{ padding: '8px 16px', textAlign: 'center' }}>
                            {item.screenshot ? (
                              <button 
                                onClick={() => setModalImage(`${API_BASE}/static/screenshots/${item.screenshot}`)}
                                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--card-border)', borderRadius: '6px', color: 'white', padding: '4px 10px', fontSize: '0.75rem', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                                className="btn-hover-glow"
                              >
                                <ImageIcon width={12} height={12} />
                                보기
                              </button>
                            ) : (
                              <span style={{ color: 'var(--text-dark)', fontSize: '0.75rem' }}>없음</span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Complaint Text & Export Center */}
              <div className="bottom-grid-layout">
                
                {/* Generated Complaint text preview */}
                <div className="glass-panel" style={{ padding: '20px', background: 'rgba(0,0,0,0.15)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileText style={{ color: 'var(--accent-primary)', width: '18px', height: '18px' }} />
                      <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>신고용 요청서 양식</h4>
                    </div>
                    <button 
                      onClick={copyToClipboard}
                      style={{ 
                        background: copySuccess ? 'var(--accent-success)' : 'rgba(99, 102, 241, 0.1)', 
                        border: '1px solid rgba(99, 102, 241, 0.3)', 
                        color: 'white', 
                        padding: '6px 12px', 
                        borderRadius: '6px', 
                        fontSize: '0.75rem', 
                        fontWeight: 600, 
                        cursor: 'pointer', 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '6px',
                        transition: 'var(--transition-smooth)'
                      }}
                    >
                      {copySuccess ? (
                        <>
                          <CheckCircle2 width={12} height={12} />
                          복사 완료!
                        </>
                      ) : (
                        <>
                          <Copy width={12} height={12} />
                          텍스트 복사
                        </>
                      )}
                    </button>
                  </div>

                  <textarea 
                    readOnly
                    value={complaintText}
                    style={{ 
                      width: '100%', 
                      height: '220px', 
                      background: 'rgba(15, 23, 42, 0.4)', 
                      border: '1px solid var(--card-border)', 
                      borderRadius: '8px', 
                      padding: '12px', 
                      color: 'var(--text-muted)', 
                      fontSize: '0.8rem', 
                      resize: 'none',
                      outline: 'none',
                      fontFamily: 'inherit'
                    }}
                  />
                </div>

                {/* Export Center downloads */}
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div className="glass-panel" style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '4px' }}>다운로드 센터</h4>
                    
                    <a href={`${API_BASE}/api/download/original-excel`} style={{ textDecoration: 'none' }}>
                      <button 
                        style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', color: 'white', padding: '12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 600, transition: 'var(--transition-smooth)' }}
                        className="btn-hover-glow"
                      >
                        <FileSpreadsheet width={16} height={16} style={{ color: 'var(--accent-success)' }} />
                        원본 데이터 엑셀 다운로드
                      </button>
                    </a>

                    <a href={`${API_BASE}/api/download/complaint-excel`} style={{ textDecoration: 'none' }}>
                      <button 
                        style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', color: 'white', padding: '12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 600, transition: 'var(--transition-smooth)' }}
                        className="btn-hover-glow"
                      >
                        <FileSpreadsheet width={16} height={16} style={{ color: 'var(--accent-primary)' }} />
                        신고 전용 포맷 엑셀 다운로드
                      </button>
                    </a>

                    <a href={`${API_BASE}/api/download/complaint-text`} style={{ textDecoration: 'none' }}>
                      <button 
                        style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', color: 'white', padding: '12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 600, transition: 'var(--transition-smooth)' }}
                        className="btn-hover-glow"
                      >
                        <FileText width={16} height={16} style={{ color: 'var(--accent-secondary)' }} />
                        신고 요청서 텍스트 파일 (.txt) 받기
                      </button>
                    </a>

                    <a href={`${API_BASE}/api/download/screenshots`} style={{ textDecoration: 'none' }}>
                      <button 
                        style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--card-border)', color: 'white', padding: '12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 600, transition: 'var(--transition-smooth)' }}
                        className="btn-hover-glow"
                      >
                        <ImageIcon width={16} height={16} style={{ color: '#ec4899' }} />
                        증빙 스크린샷 묶음 (.zip) 다운로드
                      </button>
                    </a>
                  </div>

                  <a 
                    href="https://inoti.naver.com/" 
                    target="_blank" 
                    rel="noreferrer"
                    style={{ textDecoration: 'none', marginTop: '16px' }}
                  >
                    <button 
                      style={{ width: '100%', background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))', border: 'none', color: 'white', padding: '12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '0.9rem', fontWeight: 700, transition: 'var(--transition-smooth)' }}
                    >
                      네이버 권리침해 신고센터 바로가기
                      <ExternalLink width={16} height={16} />
                    </button>
                  </a>
                </div>

              </div>
            </div>
          )}

        </main>

      </div>

      {/* Image Preview Modal */}
      {modalImage && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', display: 'grid', placeContent: 'center', zIndex: 1000 }}>
          <div style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }}>
            <button 
              onClick={() => setModalImage(null)}
              style={{ position: 'absolute', top: '-40px', right: '0px', background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%', color: 'white', width: '32px', height: '32px', cursor: 'pointer', display: 'grid', placeContent: 'center' }}
            >
              <X width={18} height={18} />
            </button>
            <img 
              src={modalImage} 
              alt="Ad evidence screenshot" 
              style={{ maxWidth: '100%', maxHeight: '80vh', border: '2px solid rgba(255,255,255,0.15)', borderRadius: '8px', boxShadow: '0 10px 40px rgba(0,0,0,0.8)' }}
            />
          </div>
        </div>
      )}

    </div>
  );
}

export default App;

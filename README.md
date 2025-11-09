# 🤖 HAMA Backend

**Human-in-the-Loop AI Multiagent Investment System**

> "AI가 분석하고, 당신이 결정한다"

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**완성도: 90%** | **Phase: 1 (MVP)** | **Status: Active Development**

---

## 📋 목차

- [프로젝트 개요](#-프로젝트-개요)
- [핵심 기능](#-핵심-기능)
- [아키텍처](#-아키텍처)
- [기술 스택](#-기술-스택)
- [빠른 시작](#-빠른-시작)
- [API 문서](#-api-문서)
- [프로젝트 구조](#-프로젝트-구조)
- [테스트](#-테스트)
- [문서](#-문서)
- [로드맵](#-로드맵)

---

## 🎯 프로젝트 개요

**HAMA**는 개인 투자자를 위한 **LangGraph 기반 멀티 에이전트 AI 투자 시스템**입니다.

### 핵심 가설
> **투자자는 귀찮은 정보 분석은 하기 싫어하지만, 종목 선택과 매매 실행은 직접 하고 싶어한다.**

### Vision
- 🤖 **AI가 분석**: 종목 리서치, 재무 분석, 시장 전망
- 👤 **당신이 결정**: 매매 실행, 포트폴리오 구성
- ⚖️ **유연한 자동화**: 3단계 자동화 레벨 (Pilot / Copilot / Advisor)

---

## 📌 현재 구현 현황 (2025-11-09 기준)

| 영역 | 구현 내용 | 주요 경로 |
|------|-----------|-----------|
| **LangGraph 다중 에이전트** | Supervisor + Router 조합으로 Research/Strategy/Risk/Trading/Portfolio/Monitoring/Report Generator 서브그래프 운영, SSE 스트리밍 지원 | `src/agents/*`, `src/api/routes/multi_agent_stream.py` |
| **HITL & 자동화 레벨** | `ApprovalRequest`/`UserDecision` 모델, Automation preset API, 승인 이력 조회 API, 인터럽트/승인 기록 저장 | `src/models/agent.py`, `src/api/routes/settings.py`, `src/api/routes/approvals.py`, `src/services/approval_service.py` |
| **시장·거시 데이터 수집** | pykrx + FinanceDataReader 이중화, KIS 실시간 시세, DART 공시, 한국은행 거시지표, 네이버 뉴스 API, Redis 실시간 캐시 | `src/services/stock_data_service.py`, `src/services/kis_service.py`, `src/services/dart_service.py`, `src/services/bok_service.py`, `src/services/news_crawler_service.py`, `src/services/realtime_cache_service.py` |
| **포트폴리오 & 매매 파이프라인** | DB 기반 포트폴리오 스냅샷, 리밸런싱/리스크 계산, Trading Agent 체결 시뮬레이터, Artifact/Onboarding API | `src/services/portfolio_service.py`, `src/agents/trading/*`, `src/api/routes/portfolio.py`, `src/api/routes/artifacts.py`, `src/api/routes/onboarding.py` |
| **인프라 & 운영** | SQLAlchemy 모델, Chat history/Artifact 저장소, Redis/LangGraph 캐시, Celery 워커/비트 스케줄, dotenv 설정 | `src/models/*`, `src/services/chat_history_service.py`, `src/services/cache_manager.py`, `src/workers/*`, `src/config/settings.py` |
| **테스트 & 툴링** | 단위/통합/E2E 테스트, KIS/Trading 플로우 디버깅 스크립트, 풍부한 픽스처/로그 | `tests/unit`, `tests/integration`, `tests/e2e`, `tests/test_trading_flow.py`, `tests/test_kis_index.py` |

---

## ✨ 핵심 기능

### 1. **멀티 에이전트 AI 시스템** (LangGraph Supervisor 패턴)

```
마스터 에이전트 (Supervisor)
        ↓
┌───────┬─────────┬────────┬────────┬──────────┬────────────┐
↓       ↓         ↓        ↓        ↓          ↓
Research Strategy Risk  Trading Portfolio Monitoring (+Report Generator)
```

**서브그래프 & 노드:**
- 🔍 **Research**: 재무제표·실적·뉴스 감정 분석, Bull/Bear 비교 (`src/agents/research/*`)
- 📈 **Strategy**: 시장 시나리오, 섹터 로테이션, 자산 배분 제안 (`src/agents/strategy/*`)
- ⚠️ **Risk**: 포트폴리오 집중도·VaR·드로우다운 진단 (`src/agents/risk/*`)
- 💰 **Trading**: 주문 시뮬레이션, HITL 승인 조건 생성, 체결 결과 요약 (`src/agents/trading/*`)
- 📊 **Portfolio**: 스냅샷 생성, 최적 비중 계산, 차트 데이터 제공 (`src/agents/portfolio/*`)
- 🛰️ **Monitoring**: 실시간 뉴스/이벤트 모니터링, 경보 생성 (`src/agents/monitoring/*`)
- 🧾 **Report Generator**: Research/Strategy 결과를 하이라이트 카드로 재구성 (`src/agents/report_generator/*`)

### 2. **HITL (Human-in-the-Loop)** 🔔

중요한 결정은 사용자 승인 필요:
- ✅ 매매 실행
- ✅ 포트폴리오 리밸런싱
- ✅ 고위험 거래

**3단계 자동화 레벨:**
```
Level 1 (Pilot)   → 거의 자동 실행
Level 2 (Copilot) → 매매/리밸런싱 승인 필요 ⭐ (기본값)
Level 3 (Advisor) → 모든 결정 승인 필요
```

### 3. **실제 데이터 연동** 📡

| 데이터 소스 | 상태 | 제공 데이터 |
|------------|------|------------|
| **pykrx** | ✅ 연동 완료 | 주가, 거래량, 종목 리스트 |
| **한국투자증권 API** | ✅ 연동 완료 | 실시간 시세, 차트, 호가 |
| **DART API** | ✅ 연동 완료 | 재무제표, 공시, 기업 정보 |
| **한국은행 API** | ✅ 연동 완료 | 금리, 거시경제 지표 |
| **Redis** | ✅ 작동 중 | 캐싱 (TTL 60초) |
| **네이버 뉴스 API** | ✅ (API 키 필요) | 종목 키워드 기반 최신 뉴스/요약 |
| **Celery 워커** | ✅ 작동 중 | 실시간 시세/거시지표 스케줄링 |

### 4. **API 영역 & 라우터** (FastAPI)

| 범주 | Method | Endpoint | 설명 / 구현 위치 |
|------|--------|----------|------------------|
| **Chat & HITL** | `POST` | `/api/v1/chat/multi-stream` | SSE 기반 멀티에이전트 실행·Thinking Trace 스트리밍<br>`src/api/routes/multi_agent_stream.py` |
| **Approvals** | `GET` | `/api/v1/approvals` | 승인 이력 조회, 상태/타입 필터, 페이지네이션<br>`src/api/routes/approvals.py` |
| **Approvals** | `GET` | `/api/v1/approvals/{request_id}` | 단일 승인 요청 상세 보기 |
| **Automation** | `GET` | `/api/v1/settings/automation-level` | 사용자 HITL 설정 조회 (없으면 Copilot 프리셋)<br>`src/api/routes/settings.py` |
| **Automation** | `PUT` | `/api/v1/settings/automation-level` | 사용자 정의·프리셋 저장 (confirm=true 필요) |
| **Automation** | `GET` | `/api/v1/settings/automation-levels` | Pilot/Copilot/Advisor 프리셋 메타데이터 |
| **Dashboard** | `GET` | `/api/v1/dashboard` | 총자산/상위 보유/활동 로그 요약 |
| **Portfolio** | `GET` | `/api/v1/portfolio` | 기본 포트폴리오 스냅샷 자동 해석 |
| **Portfolio** | `GET` | `/api/v1/portfolio/{portfolio_id}` | 특정 포트폴리오 요약/리스크/구성 |
| **Portfolio** | `GET` | `/api/v1/portfolio/{portfolio_id}/performance` | 기간별 성과·지표 |
| **Portfolio** | `GET` | `/api/v1/portfolio/chart-data` | 차트/밸런싱 데이터 (프런트 차트용) |
| **Portfolio** | `POST` | `/api/v1/portfolio/{portfolio_id}/rebalance` | 리밸런싱 시뮬레이션/행동 계획 기록 |
| **Stocks** | `GET` | `/api/v1/stocks/search` | 종목/코드 검색 + 최신 시세 |
| **Stocks** | `GET` | `/api/v1/stocks/{code}` | 단일 종목 기본 정보 |
| **Stocks** | `GET` | `/api/v1/stocks/{code}/price-history` | 기간별 시세 (pykrx → KIS fallback) |
| **Stocks** | `GET` | `/api/v1/stocks/{code}/analysis` | Research Agent 호출 결과 |
| **News** | `GET` | `/api/v1/news/{stock_code}` | 종목별 저장된 뉴스 |
| **News** | `POST` | `/api/v1/news/fetch` | 네이버 뉴스 API 호출 + DB 저장 |
| **News** | `GET` | `/api/v1/news/recent` | 전체 종목 최신 뉴스 |
| **Artifacts** | `POST/GET/PUT/DELETE` | `/api/v1/artifacts[...]` | AI 생성 보고서 CRUD |
| **Onboarding** | `POST` | `/api/v1/onboarding/screening` | 스크리닝 응답 → AI 프로파일 생성 |
| **Onboarding** | `GET` | `/api/v1/onboarding/profile/{user_id}` | 투자 프로파일 조회 |

#### SSE 기반 멀티에이전트 호출 예시

```bash
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
        "message": "삼성전자 10주 매수해도 될까?",
        "user_id": "3bd04ffb-350a-5fa4-bee5-6ce019fdad9c",
        "conversation_id": "4e51a4fd-6d30-4bfd-9f31-1fba6dd51b0d",
        "automation_level": 2,
        "stream_thinking": true
      }' \
  http://localhost:8000/api/v1/chat/multi-stream
```

수신되는 이벤트 타입: `master_start`, `agent_start`, `agent_thinking`, `agent_complete`, `approval_required`, `final_answer` 등. `approval_required` 이벤트에는 `request_id`가 포함되며, 프런트는 이를 `/api/v1/approvals` API로 조회하거나 UI에 저장한다.

#### 승인/설정/데이터 조회 예시

```bash
# 승인 목록
curl "http://localhost:8000/api/v1/approvals?status=pending&limit=10"

# 자동화 프리셋
curl http://localhost:8000/api/v1/settings/automation-levels

# 상위 보유 종목이 포함된 대시보드
curl http://localhost:8000/api/v1/dashboard

# 뉴스 수집 (네이버 API 키 필요)
curl -X POST http://localhost:8000/api/v1/news/fetch \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"005930","stock_name":"삼성전자","max_articles":10}'
```

---

## 🏗️ 아키텍처

### **LangGraph Supervisor 패턴**

```python
# Master Agent (Supervisor)
supervisor = create_supervisor(
    agents=[research_agent, strategy_agent, risk_agent, ...],
    model=ChatAnthropic(model="claude-3-5-sonnet"),
    parallel_tool_calls=True  # 에이전트 선택 시 병렬 가능
    # 실제 실행은 의존성에 따라 순차적으로 조율
)

# HITL Interrupt 메커니즘
if state.next:  # Interrupt 발생
    return {
        "requires_approval": True,
        "approval_request": {
            "thread_id": conversation_id,
            "interrupt_data": {...}
        }
    }
```

### **데이터 플로우**

```
사용자 질의 → Master Agent → 의도 분석 (LLM)
                    ↓
        적절한 에이전트 선택 (동적 라우팅)
                    ↓
              Research Agent
        (내부 노드: Bull/Bear 병렬 분석)
                    ↓
             Strategy Agent
      (내부 노드: 시장/섹터/자산배분 순차)
                    ↓
               Risk Agent
       (내부 노드: 집중도/시장리스크 순차)
                    ↓
            결과 통합 → HITL 체크
                    ↓
        승인 필요? → Interrupt 발생
                    ↓
        사용자 승인 → 거래 실행

⚠️ 에이전트 간: 순차 실행 (의존성)
✅ 에이전트 내부 노드: 병렬 실행 가능
```

---

## 🛠️ 기술 스택

### **Backend**
- **FastAPI** 0.104+ - 고성능 비동기 웹 프레임워크
- **Python** 3.12
- **PostgreSQL** - 관계형 데이터베이스 (19개 테이블)
- **Redis** - 캐싱 시스템

### **AI Framework**
- **LangGraph** 0.2+ - 에이전트 오케스트레이션
- **LangChain** - LLM 통합
- **Anthropic Claude** 3.5 Sonnet - 메인 LLM
- **Supervisor 패턴** - 멀티 에이전트 조율

### **Data Sources**
- **pykrx** - KRX 시장 데이터
- **한국투자증권 API** - 실시간 시세, 차트, 호가
- **DART Open API** - 금융감독원 공시 시스템
- **한국은행 API** - 금리, 거시경제 지표

### **DevOps**
- **Docker & Docker Compose** ✅ - 컨테이너화
- **Railway** ✅ - 클라우드 배포 (자동 CI/CD)
- **pytest** - 테스트 프레임워크
- **Git** - 버전 관리

---

## 🚀 빠른 시작

두 가지 방법으로 실행할 수 있습니다:
- **Option A: Docker Compose** ⭐ (추천 - 5분 설정)
- **Option B: 로컬 설치** (개발자용)

### **Option A: Docker Compose로 실행** ⭐

**장점:**
- ✅ 한 번에 모든 서비스 실행 (PostgreSQL, Redis, FastAPI, Celery)
- ✅ 환경 격리
- ✅ 팀원 온보딩 간편

**1. 사전 요구사항**
- Docker Desktop 설치 (https://www.docker.com/products/docker-desktop)
- API 키 (Anthropic, DART 등)

**2. 환경 변수 설정**
```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (API 키 입력)
# ANTHROPIC_API_KEY=your-key
# DART_API_KEY=your-key
# ...
```

**3. Docker Compose 실행**
```bash
# 모든 서비스 시작 (백그라운드)
docker-compose up -d

# 로그 확인
docker-compose logs -f fastapi

# 서비스 상태 확인
docker-compose ps
```

**4. 접속**
- FastAPI: http://localhost:8000
- Swagger 문서: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

**5. 중지/재시작**
```bash
# 중지
docker-compose down

# 재시작
docker-compose restart

# 전체 삭제 (데이터 포함)
docker-compose down -v
```

---

### **Option B: 로컬 설치**

**사전 요구사항**
- Python 3.12+
- PostgreSQL 13+
- Redis 6+
- API 키:
  - Anthropic API Key
  - DART API Key (선택)

### **2. 설치**

```bash
# 저장소 클론
git clone https://github.com/your-org/HAMA-backend.git
cd HAMA-backend

# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### **3. 환경 변수 설정**

```bash
# .env 파일 생성
cp .env.example .env
```

**.env 파일 내용:**
```bash
# LLM API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_key_here  # 선택

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/hama_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# DART API (선택)
DART_API_KEY=your_dart_api_key_here

# 캐시 TTL
CACHE_TTL_MARKET_DATA=60
```

### **4. 데이터베이스 설정**

```bash
# PostgreSQL 데이터베이스 생성
createdb hama_db

# Alembic 마이그레이션 (채팅 히스토리 테이블 포함)
alembic upgrade head
```

### **5. 서버 실행**

```bash
# 개발 서버 (Hot Reload)
python -m uvicorn src.main:app --reload

# 또는
python -m src.main
```

**서버 주소:**
- API: http://localhost:8000
- Swagger 문서: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### **6. API 테스트**

```bash
# SSE 기반 다중 에이전트 호출
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
        "message": "코스피/코스닥 시장 위험 요약 알려줘",
        "conversation_id": "f013f096-89be-4f1f-b0da-5ac486521111",
        "user_id": "3bd04ffb-350a-5fa4-bee5-6ce019fdad9c",
        "automation_level": 2,
        "stream_thinking": true
      }' \
  http://localhost:8000/api/v1/chat/multi-stream

# 승인 히스토리
curl "http://localhost:8000/api/v1/approvals?status=pending&limit=5"

# 자동화 레벨 변경
curl -X PUT http://localhost:8000/api/v1/settings/automation-level \
  -H "Content-Type: application/json" \
  -d '{
        "confirm": true,
        "hitl_config": {
          "preset": "pilot",
          "phases": {"analysis": false, "portfolio": false, "risk": false, "trade": "conditional"}
        }
      }'
```

### **7. 채팅 히스토리 & 테스트 모드**

- 대화·승인 컨텍스트는 `chat_sessions`, `chat_messages`, `approval_requests`, `user_decisions` 테이블에 저장됩니다. (`alembic upgrade head`로 최초 스키마 구축)
- `.env`의 `ENV=test` 또는 LLM 키 제거 시 에이전트가 모의 응답을 반환하여 외부 API 없이 흐름을 검증할 수 있습니다.
- `tests/test_trading_flow.py`, `tests/test_kis_index.py`는 LangGraph/서비스 흐름을 단독으로 재현하는 디버깅 스크립트입니다.

---

## 📡 API 문서

- Swagger / ReDoc: `http://localhost:8000/docs`, `http://localhost:8000/redoc`
- 샘플 통합 시나리오: `docs/complete_user_scenarios.md`
- 프런트엔드 연동 가이드: `docs/frontend/frontend-integration-guide.md`
- 운영/워커 관리: `docs/operations/celery-management.md`
- 배포 가이드: `docs/deployment/railway-deployment.md`

---

## 🗂️ 데이터 구조 하이라이트

- `chat_sessions`: 사용자, 자동화 레벨, 요약 정보 등을 포함한 채팅 세션 메타데이터
- `chat_messages`: 세션별 사용자/에이전트 메시지 기록
- `portfolios`, `positions`, `orders`, `transactions`: 투자 계정 및 체결 내역
- `stocks`, `financial_statements`, `disclosures`: 종목/재무/공시 정보 캐시

---

## 📂 프로젝트 구조

```
HAMA-backend/
├── src/
│   ├── agents/              # LangGraph 에이전트
│   │   ├── monitoring/       ✅ 뉴스/경보 모니터링 서브그래프
│   │   ├── portfolio/        ✅ 포트폴리오 서브그래프
│   │   ├── report_generator/ ✅ 결과 카드 합성
│   │   ├── research/         ✅ 종목 분석 서브그래프
│   │   ├── risk/             ✅ 리스크 평가 서브그래프
│   │   ├── router/           ✅ LLM 기반 라우터
│   │   ├── strategy/         ✅ 전략 서브그래프
│   │   ├── trading/          ✅ HITL·체결 서브그래프
│   │   └── thinking_trace.py ✅ SSE 이벤트 포맷터
│   ├── api/
│   │   ├── middleware/logging.py
│   │   └── routes/
│   │       ├── multi_agent_stream.py ✅ SSE 스트리밍 엔드포인트
│   │       ├── approvals.py          ✅ 승인 이력 API
│   │       ├── settings.py           ✅ 자동화 레벨 API
│   │       ├── portfolio.py          ✅ 포트폴리오/리밸런싱 API
│   │       ├── onboarding.py         ✅ 스크리닝 → 프로파일 API
│   │       ├── stocks.py             ✅ 종목/시세/리서치 API
│   │       ├── dashboard.py          ✅ 대시보드 요약 API
│   │       ├── news.py               ✅ 네이버 뉴스 연동
│   │       └── artifacts.py          ✅ AI 산출물 CRUD
│   ├── services/             # 데이터 서비스
│   │   ├── stock_data_service.py      ✅ pykrx + KIS + Redis 캐시
│   │   ├── kis_service.py             ✅ 한국투자증권 OAuth + 주문
│   │   ├── dart_service.py            ✅ 공시 수집
│   │   ├── bok_service.py             ✅ 한국은행 지표
│   │   ├── news_crawler_service.py    ✅ 네이버 뉴스 API
│   │   ├── realtime_cache_service.py  ✅ 실시간 시세 Redis 캐시
│   │   ├── portfolio_service.py       ✅ 포트폴리오/리스크 계산
│   │   ├── approval_service.py        ✅ ApprovalRequest 리포지토리
│   │   ├── user_profile_service.py    ✅ 투자 성향 프로파일
│   │   └── portfolio_optimizer.py · macro_data_service.py 등 15+ 서비스
│   ├── models/               # SQLAlchemy 모델
│   │   ├── agent.py          ✅ ApprovalRequest/TradingSignal 등
│   │   ├── chat.py           ✅ 세션/메시지 기록
│   │   ├── portfolio.py      ✅ Portfolio/Position/Transaction
│   │   ├── stock.py          ✅ 종목·재무·뉴스 테이블
│   │   └── user_profile.py   ✅ 투자 성향 저장
│   ├── repositories/         # Repository 패턴
│   │   ├── news_repository.py
│   │   ├── stock_repository.py
│   │   └── user_settings_repository.py
│   ├── schemas/              # Pydantic 스키마 (자동화/포트폴리오/뉴스 등 20+)
│   ├── utils/                # LLM·지표·종목명 추출 유틸
│   ├── workers/              # Celery 앱/태스크
│   ├── config/               # Settings, 환경 변수
│   └── main.py               # FastAPI 엔트리포인트
├── tests/
│   ├── unit/test_agents/*   ✅ 에이전트 단위 테스트
│   ├── unit/test_services/* ✅ 서비스 단위 테스트
│   ├── integration/         ✅ HITL/뉴스/시세 통합 테스트
│   ├── e2e/                 ✅ LangGraph 시나리오 스크립트
│   ├── test_kis_index.py    ✅ KIS API 수동 테스트
│   └── test_trading_flow.py ✅ Trading 서브그래프 시뮬레이터
├── docs/
│   ├── PRD.md
│   ├── schema.md
│   ├── complete_user_scenarios.md
│   ├── frontend/
│   │   ├── frontend-integration-guide.md
│   │   └── frontend-backend-gap-analysis.md
│   ├── deployment/railway-deployment.md
│   ├── operations/celery-management.md
│   └── plan/ (phase 문서, completed 기록)
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 🧪 테스트

### **실행 가이드**

```bash
# 전체 스위트 (pytest.ini에 async/strict marker 설정)
pytest

# 에이전트 단위 테스트
pytest tests/unit/test_agents/test_trading_agent.py -vv

# HITL 플로우 통합 테스트
pytest tests/integration/test_hitl_integration.py -vv

# KIS/Trading 스모크 (환경 변수 필요)
python tests/test_kis_index.py
python tests/test_trading_flow.py
```

### **범위 & 커버리지 현황**

| 범주 | 주요 파일 | 하이라이트 |
|------|-----------|-------------|
| Unit – Agents | `tests/unit/test_agents/*.py` | Research/Strategy/Trading 상태 머신 검증, Routing worker 선택 테스트 |
| Unit – Services | `tests/unit/test_services/test_news_crawler_service.py` 등 | 네이버 뉴스, Approval, Cache 로직 스텁 |
| Integration | `tests/integration/test_hitl_integration.py`, `tests/integration/test_stock_data_integration.py`, `tests/integration/test_news_api.py` | HITL 승인 시나리오, pykrx/KIS 혼합 시세, 뉴스 API 라운드트립 |
| System Smoke | `tests/test_trading_flow.py`, `tests/test_kis_index.py` | LangGraph 서브그래프 단독 실행, KIS 실계좌·모의계좌 API 검증 |
| Fixtures & Logs | `tests/fixtures/*.json`, `tests/logs/` | 결정적 데이터셋/로그로 CI 재현성 유지 |

---

## 📚 문서

### **핵심 문서**

| 문서 | 설명 |
|------|------|
| [docs/PRD.md](docs/PRD.md) | 전체 기능/비즈니스 요구사항 |
| [docs/schema.md](docs/schema.md) | 19개 테이블·ERD 정리 |
| [docs/complete_user_scenarios.md](docs/complete_user_scenarios.md) | E2E 사용자 여정 & API 호출 순서 |
| [docs/frontend/frontend-integration-guide.md](docs/frontend/frontend-integration-guide.md) | SSE/Redux 연동 예시, UI 요구사항 |
| [CLAUDE.md](CLAUDE.md) | 에이전트 개발 가이드라인 |

### **계획 문서**

| 문서 | 설명 |
|------|------|
| [docs/plan/legacy-agent-migration.md](docs/plan/legacy-agent-migration.md) | 기존 파이프라인 → LangGraph 전환 계획 |
| [docs/plan/completed/phase1/tech-stack-setup.md](docs/plan/completed/phase1/tech-stack-setup.md) | lint/format/type-check 규칙 |
| [docs/frontend/frontend-backend-gap-analysis.md](docs/frontend/frontend-backend-gap-analysis.md) | UX 요구 대비 서버 구현 갭 |
| [docs/operations/celery-management.md](docs/operations/celery-management.md) | 워커 배포/모니터링 지침 |
| [docs/deployment/railway-deployment.md](docs/deployment/railway-deployment.md) | Railway 배포 체크리스트 |

---

## 🗺️ 로드맵

### **Phase 1 (현재) - MVP 완성** 🔵 90% 완료

- [x] LangGraph Supervisor + Router + SSE 스트리밍 파이프라인
- [x] 7개 서브그래프 (Research/Strategy/Risk/Trading/Portfolio/Monitoring/Report Generator)
- [x] HITL 시스템
  - [x] Automation Preset (Pilot/Copilot/Advisor) & Custom 저장
  - [x] ApprovalRequest/UserDecision 모델 & API
  - [x] SSE Interrupt → 승인 기록 연동
- [x] 실거래소 데이터 통합
  - [x] pykrx + FinanceDataReader 이중화
  - [x] 한국투자증권 API (실시간 시세·지수·주문)
  - [x] DART / 한국은행 / 네이버 뉴스 API
- [x] Redis + Celery 기반 실시간 캐시/워커
- [x] 종목명 추출기 (LLM 구조화 출력)
- [x] 15+ 서비스/리포지토리 계층
- [x] 프론트엔드 통합/데이터 시나리오 문서
- [ ] 자동 테스트 커버리지 80%+
- [ ] API 인증/권한 계층
- [ ] 프론트엔드 (Copilot UI) 1차 버전

### **Phase 2 - 확장 기능** 🔵 예정

- [ ] 실거래 주문/체결 웹훅 연동 (KIS real env)
- [ ] LangGraph 체크포인트 영속화 (Redis/Postgres)
- [ ] WebSocket 실시간 대시보드/알림
- [ ] 사용자 인증 (JWT + OAuth) 및 다중 계정
- [ ] 포트폴리오 백테스트 + 퍼포먼스 리포트
- [ ] HITL 세분화 (조건부 필터, 한도 관리)
- [ ] SSE → WebRTC/HMR 시각화 모듈

### **Phase 3 - 확장** ⚪ 계획 중

- [ ] 해외 주식/ETF 데이터 소스 편입
- [ ] 자동 리밸런싱 스케줄러 + 캘린더
- [ ] 모바일/데스크톱 클라이언트
- [ ] 성과 분석 대시보드 + 목표 대비 추적
- [ ] 커뮤니티/토론 기능 (Bull/Bear 시각화)

---

## 📊 완성도

| 컴포넌트 | 완성도 | 비고 |
|---------|--------|------|
| Backend Core | 🟢 95% | FastAPI + LangGraph + Celery |
| Agents | 🟢 90% | 7개 서브그래프 + Router + SSE |
| HITL System | 🟢 95% | HITLConfig + Settings API |
| Data Integration | 🟢 95% | pykrx + KIS + DART + BOK + Naver News |
| API Endpoints | 🟢 95% | Chat/Portfolio/News 등 10+ 라우터 |
| Services | 🟢 90% | 15+ 서비스/리포지토리 |
| Documentation | 🟢 90% | PRD + 시나리오 + 배포/운영 문서 |
| Testing | 🟡 70% | 단위/통합 대비 시스템 테스트 확대 예정 |
| Frontend | 🔴 0% | 개발 대기 중 |
| Deployment | 🟢 90% | Docker + Railway |

**전체: 90%** 🎯

---

## 🚢 배포 (Railway)

### **프로덕션 배포**

Railway로 손쉽게 배포할 수 있습니다 (무료 티어 제공).

**1단계: Railway 회원가입**
- https://railway.app
- GitHub 계정으로 로그인

**2단계: 프로젝트 생성**
- "New Project" → "Deploy from GitHub repo"
- `HAMA-backend` 저장소 선택

**3단계: 서비스 추가**
- PostgreSQL 데이터베이스 추가
- Redis 추가
- FastAPI, Celery Worker, Celery Beat 배포

**4단계: 환경 변수 설정**
- Railway 대시보드에서 API 키 등록
- `${{Postgres.DATABASE_URL}}` 형식으로 자동 연결

**5단계: 배포 완료!**
- 고정 URL: `https://hama-backend-production.up.railway.app`
- HTTPS 자동 적용
- GitHub Push → 자동 재배포

**자세한 가이드:**
📄 [Railway 배포 가이드](docs/deployment/railway-deployment.md)

---

## 🤝 기여

이 프로젝트는 캡스톤 프로젝트로 진행 중입니다.

---

## 📝 라이선스

MIT License

---

## 👥 팀

**HAMA Development Team**
- Backend Architecture & AI Agents
- LangGraph Integration
- Data Pipeline

---

## 📞 연락처

- **이슈 트래커**: GitHub Issues
- **문서**: `docs/` 디렉토리
- **API 문서**: http://localhost:8000/docs

---

**Built with ❤️ using LangGraph & FastAPI**

Last Updated: 2025-11-09

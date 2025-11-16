# HAMA 시스템 아키텍처

**Version**: 1.0
**Last Updated**: 2025-11-16
**Status**: Phase 1 MVP (95% 완성)

---

## 📋 목차

1. [시스템 개요](#-시스템-개요)
2. [아키텍처 전체 구조](#-아키텍처-전체-구조)
3. [핵심 컴포넌트](#-핵심-컴포넌트)
4. [데이터 플로우](#-데이터-플로우)
5. [기술 스택](#-기술-스택)
6. [배포 아키텍처](#-배포-아키텍처)

---

## 🎯 시스템 개요

**HAMA (Human-in-the-Loop AI Multiagent)**는 개인 투자자를 위한 AI 기반 투자 분석 및 의사결정 지원 시스템입니다.

### 핵심 가설
> **투자자는 귀찮은 정보 분석은 하기 싫어하지만, 종목 선택과 매매 실행은 직접 하고 싶어한다.**

### Vision
- 🤖 **AI가 분석**: 종목 리서치, 재무 분석, 시장 전망
- 👤 **당신이 결정**: 매매 실행, 포트폴리오 구성
- ⚖️ **유연한 자동화**: 3단계 자동화 레벨 (Pilot / Copilot / Advisor)

---

## 🏗️ 아키텍처 전체 구조

### **레이어 구조**

```
┌─────────────────────────────────────────────────────────────┐
│                    🌐 API Layer (FastAPI)                    │
│  9개 라우트: chat, portfolio, stocks, dashboard, settings... │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              🤖 Agent Layer (LangGraph Supervisor)           │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Supervisor (Master)                   │  │
│  │  - 간단한 조회: 직접 처리 (Tools 사용)                │  │
│  │  - 복잡한 분석: SubGraph에 위임                        │  │
│  │  - HITL 승인 관리                                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                 ↓                         ↓                  │
│  ┌─────────────────────┐   ┌─────────────────────────────┐  │
│  │  Research SubGraph   │   │  Quantitative SubGraph      │  │
│  │  - 종목 분석          │   │  - 투자 전략 (시장 사이클)  │  │
│  │  - 재무제표 분석      │   │  - 리스크 평가 (VaR)        │  │
│  │  - 기술적 지표        │   │  - 섹터 로테이션            │  │
│  │  - 뉴스 감정 분석     │   │  - 자산 배분               │  │
│  └─────────────────────┘   └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            💼 Service Layer (Business Logic)                 │
│                                                               │
│  📊 Portfolio Service    📈 Stock Data Service               │
│  💰 Trading Service      🏦 KIS Service (한국투자증권)       │
│  ⚠️  Risk Service         📰 DART Service (공시)             │
│  🔔 Approval Service     🏛️  BOK Service (한국은행)          │
│  👤 User Profile Service ... (20+ 서비스)                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              🗄️ Data Layer (PostgreSQL)                     │
│                                                               │
│  19개 테이블:                                                 │
│  - users, portfolios, positions, orders, transactions        │
│  - chat_sessions, chat_messages, approval_requests           │
│  - stocks, financial_statements, disclosures, news_articles  │
│  - user_settings, hitl_configs, artifacts, ...               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              🌍 External Data Sources                        │
│                                                               │
│  📊 pykrx (주가, 거래량)     🏦 KIS API (실시간 시세)         │
│  📰 DART API (재무, 공시)    🏛️  BOK API (금리, 경제지표)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 핵심 컴포넌트

### 1. **Supervisor (Master Agent)** 📌

**파일**: `src/subgraphs/graph_master.py`

**역할**:
- **동적 라우팅**: 사용자 질의 의도 분석 → 적절한 SubGraph 선택
- **직접 처리**: 간단한 조회는 Tool 호출로 즉시 응답
- **Trading Pipeline 관리**: 매매 요청 → 시뮬레이션 → HITL → 실행
- **HITL 승인 관리**: Interrupt 발생 → 사용자 승인 대기 → 재개

**주요 노드**:
```python
# Trading Pipeline
- portfolio_simulator_node   # 매매 시뮬레이션
- trade_planner_node         # 매매 계획 생성
- trade_hitl_node            # HITL 승인 요청
- trade_executor_node        # 매매 실행
```

**사용하는 Tools**:
- `search_ticker`: 종목 검색
- `get_current_price`: 현재가 조회
- `get_portfolio`: 포트폴리오 조회
- `request_trade`: 매매 요청
- `calculate_risk`: 리스크 계산

### 2. **Research SubGraph** 🔍

**파일**: `src/subgraphs/research_subgraph/`

**역할**:
- 종목 심층 분석 (재무, 기술적 지표, 뉴스 감정)
- Bull/Bear 관점 병렬 분석
- 종합 투자 의견 생성

**주요 노드**:
```python
- coordinator_node           # 분석 조율
- bull_analyst_node          # 낙관적 관점 분석
- bear_analyst_node          # 비관적 관점 분석
- fundamental_analyst_node   # 재무 분석
- technical_analyst_node     # 기술적 분석
- sentiment_analyst_node     # 뉴스 감정 분석
- synthesizer_node           # 의견 통합
```

**데이터 소스**:
- DART API (재무제표, 공시)
- pykrx (주가, 거래량)
- KIS API (실시간 시세)

### 3. **Quantitative SubGraph** 📊

**파일**: `src/subgraphs/quantitative_subgraph/`

**역할**:
- 투자 전략 생성 (시장 사이클, 섹터 로테이션)
- 리스크 평가 (VaR, 집중도, 시장 리스크)
- 자산 배분 제안

**주요 노드**:
```python
# Strategy Nodes
- market_cycle_node          # 시장 사이클 분석
- sector_rotation_node       # 섹터 로테이션
- asset_allocation_node      # 자산 배분

# Risk Nodes
- concentration_risk_node    # 집중도 리스크
- market_risk_node           # 시장 리스크
- risk_synthesizer_node      # 리스크 통합
```

**분석 기법**:
- VaR (Value at Risk)
- 베타 계산
- 샤프 비율
- 집중도 지수 (HHI)

### 4. **Trading Pipeline** 💰

**플로우**:
```
사용자 매매 요청
        ↓
portfolio_simulator_node
  (전/후 비교 시뮬레이션)
        ↓
trade_planner_node
  (주문 구조화)
        ↓
trade_hitl_node
  (HITL 승인 요청)
        ↓
[Interrupt 발생]
        ↓
사용자 승인/거부/수정
        ↓
trade_executor_node
  (매매 실행)
```

**안전 장치**:
- ✅ 멱등성 보장 (중복 실행 방지)
- ✅ 트랜잭션 관리
- ✅ 재시뮬레이션 (수정 시)

### 5. **Service Layer** 💼

**20+ 서비스**:

| 서비스 | 역할 |
|--------|------|
| **portfolio_service** | 포트폴리오 조회, 리밸런싱, 최적화 |
| **trading_service** | 매매 주문 생성, 실행, 체결 확인 |
| **kis_service** | 한국투자증권 API 연동 (실시간 시세) |
| **stock_data_service** | pykrx 연동 (주가, 거래량) |
| **dart_service** | DART API 연동 (재무, 공시) |
| **bok_service** | 한국은행 API 연동 (금리, 경제지표) |
| **portfolio_optimizer** | 포트폴리오 최적화 (평균-분산) |
| **approval_service** | HITL 승인 요청 관리 |
| **user_profile_service** | 사용자 프로필 관리 |
| **chat_history_service** | 대화 이력 저장/조회 |
| ... | ... |

### 6. **API Layer** 🌐

**9개 라우트**:

| 라우트 | 엔드포인트 | 역할 |
|--------|-----------|------|
| **chat** | `/api/v1/chat/` | 대화형 인터페이스 |
| **multi_agent_stream** | `/api/v1/chat/multi-agent-stream` | 스트리밍 응답 |
| **approvals** | `/api/v1/approvals/` | 승인 요청 처리 |
| **settings** | `/api/v1/settings/` | 자동화 레벨 설정 |
| **portfolio** | `/api/v1/portfolio/` | 포트폴리오 관리 |
| **stocks** | `/api/v1/stocks/` | 종목 정보 조회 |
| **dashboard** | `/api/v1/dashboard/` | 대시보드 데이터 |
| **artifacts** | `/api/v1/artifacts/` | AI 생성 콘텐츠 |
| **news** | `/api/v1/news/` | 뉴스 검색 |

---

## 🔄 데이터 플로우

### **일반 질의 플로우**

```
1. 사용자 질의
   └─> POST /api/v1/chat/

2. Supervisor 의도 분석 (LLM)
   └─> 간단한 조회? → Tool 호출 → 즉시 응답
   └─> 복잡한 분석? → SubGraph 위임

3. SubGraph 실행
   Research SubGraph:
   ├─> Bull Analyst (병렬)
   ├─> Bear Analyst (병렬)
   ├─> Fundamental Analyst
   ├─> Technical Analyst
   └─> Synthesizer → 통합 의견

   Quantitative SubGraph:
   ├─> Market Cycle Analysis
   ├─> Sector Rotation
   ├─> Risk Assessment
   └─> Strategy 생성

4. 결과 통합 → 사용자 응답
```

### **매매 요청 플로우**

```
1. 사용자 매매 요청
   └─> "삼성전자 10주 매수해줘"

2. Supervisor → request_trade Tool 호출
   └─> stock_code, quantity, price 추출

3. Trading Pipeline 시작
   ├─> Portfolio Simulator
   │   └─> 매매 전/후 비교 (위험도, 비중 등)
   │
   ├─> Trade Planner
   │   └─> 주문 구조화 (trade_proposal)
   │
   ├─> Trade HITL
   │   └─> Interrupt 발생
   │   └─> 사용자에게 승인 요청
   │       (전/후 비교 데이터 포함)

4. 사용자 승인
   └─> POST /api/v1/chat/approve
       ├─> decision: "approved"
       ├─> decision: "rejected"
       └─> decision: "modified" → 재시뮬레이션

5. Trade Executor
   └─> 실제 매매 주문 생성 (KIS API)
   └─> DB 저장 (orders, transactions)

6. 결과 반환
   └─> 체결 확인 → 사용자 응답
```

### **HITL 승인 플로우**

```
┌─────────────────────────────────────────────────────┐
│  1. Supervisor → request_trade Tool 호출             │
│     (매매 의도 감지)                                  │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│  2. Portfolio Simulator                              │
│     - 매매 전 포트폴리오 상태 계산                    │
│     - 매매 후 포트폴리오 상태 계산                    │
│     - 리스크 변화 계산 (VaR, 변동성)                 │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│  3. Trade HITL Node                                  │
│     - Interrupt 발생 (LangGraph)                     │
│     - approval_request DB 저장                       │
│     - API 응답: requires_approval=True               │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│  4. 사용자 승인 대기                                  │
│     - 프론트엔드: 전/후 비교 표시                     │
│     - 사용자: 승인/거부/수정 결정                     │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│  5. POST /api/v1/chat/approve                        │
│     - decision: approved → 실행                       │
│     - decision: rejected → 취소                       │
│     - decision: modified → 재시뮬레이션               │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│  6. Trade Executor (승인 시)                         │
│     - 실제 매매 주문 생성                             │
│     - KIS API 호출 (Phase 2)                         │
│     - DB 저장 및 결과 반환                            │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ 기술 스택

### **Backend**
- **FastAPI** 0.104+ - 비동기 웹 프레임워크
- **Python** 3.12
- **SQLAlchemy** - ORM (동기식)
- **Alembic** - 데이터베이스 마이그레이션
- **PostgreSQL** - 관계형 데이터베이스

### **AI Framework**
- **LangGraph** 0.2+ - 에이전트 오케스트레이션
- **LangChain** - LLM 통합
- **Anthropic Claude** 3.5 Sonnet - 메인 LLM
- **OpenAI** GPT-5 - 종목명 추출

### **Data Sources**
- **pykrx** - KRX 시장 데이터
- **한국투자증권 API** - 실시간 시세, 차트, 호가
- **DART Open API** - 금융감독원 공시 시스템
- **한국은행 API** - 금리, 거시경제 지표

### **DevOps**
- **Docker** - 컨테이너화
- **Docker Compose** - 로컬 개발 환경
- **Railway** - 클라우드 배포 (자동 CI/CD)
- **pytest** - 테스트 프레임워크
- **Git** - 버전 관리

---

## 🚀 배포 아키텍처

### **로컬 개발 환경**

```
┌─────────────────────────────────────────────────────┐
│                 Docker Compose                       │
│                                                       │
│  ┌─────────────────┐    ┌─────────────────┐         │
│  │   FastAPI       │    │   PostgreSQL    │         │
│  │   (Port 8000)   │◄───│   (Port 5432)   │         │
│  └─────────────────┘    └─────────────────┘         │
│                                                       │
│  Volume Mounts:                                       │
│  - ./src → /app/src                                   │
│  - ./tests → /app/tests                               │
│  - ./.env → /app/.env                                 │
└─────────────────────────────────────────────────────┘
```

### **프로덕션 환경 (Railway)**

```
┌─────────────────────────────────────────────────────┐
│                    Railway Platform                  │
│                                                       │
│  ┌─────────────────┐    ┌─────────────────┐         │
│  │  FastAPI Service│    │  PostgreSQL DB  │         │
│  │  (Auto Deploy)  │◄───│  (Managed)      │         │
│  └─────────────────┘    └─────────────────┘         │
│          ↑                                            │
│  ┌─────────────────┐                                 │
│  │  GitHub Repo    │                                 │
│  │  (Auto Trigger) │                                 │
│  └─────────────────┘                                 │
│                                                       │
│  Features:                                            │
│  - HTTPS 자동 적용                                    │
│  - 환경 변수 관리                                     │
│  - 자동 재배포 (Git Push)                             │
│  - 로그 모니터링                                      │
└─────────────────────────────────────────────────────┘
```

---

## 📊 성능 고려사항

### **캐싱 전략**
- 인메모리 캐싱 (TTL 60초)
- API 응답 캐싱 (pykrx, DART)
- 종목 정보 캐싱

### **비동기 처리**
- FastAPI 비동기 엔드포인트
- 서비스 레이어는 동기식 (SQLAlchemy)
- 외부 API 호출 병렬화

### **스케일링**
- **수평 확장**: Railway 복제 가능
- **데이터베이스**: PostgreSQL 읽기 복제본 (Phase 2)
- **캐싱**: Redis 도입 (Phase 2)

---

## 🔒 보안

### **인증/권한**
- Phase 1: 인증 없음 (로컬 개발)
- Phase 2: JWT 기반 인증
- Phase 3: OAuth 2.0 (소셜 로그인)

### **API 키 관리**
- 환경 변수 (.env)
- Railway Secrets (프로덕션)
- 절대 코드에 하드코딩 금지

### **데이터 보호**
- HTTPS 통신
- SQL Injection 방지 (ORM 사용)
- XSS 방지 (입력 검증)

---

## 📈 모니터링 & 로깅

### **로깅**
- **FastAPI**: RequestLoggingMiddleware
- **LangGraph**: graph_logger
- **서비스**: Python logging 모듈
- **레벨**: DEBUG, INFO, WARNING, ERROR

### **메트릭**
- API 응답 시간
- LLM 호출 횟수
- 데이터베이스 쿼리 시간
- 에러율

---

## 🗺️ 향후 계획

### **Phase 2 (예정)**
- 실제 매매 주문 실행
- WebSocket 실시간 알림
- Redis 캐싱
- JWT 인증

### **Phase 3 (계획 중)**
- 해외 주식 지원
- 모바일 앱
- 자동 리밸런싱 스케줄러
- 성과 분석 대시보드

---

## 📚 관련 문서

- [PRD.md](../PRD.md) - 제품 요구사항 정의
- [schema.md](../schema.md) - 데이터베이스 스키마
- [LangGraph 패턴 가이드](../guides/langgraph-patterns.md)
- [데이터베이스 가이드](../guides/database-guide.md)
- [테스트 작성 가이드](../guides/testing-guide.md)
- [프론트엔드 통합 가이드](../frontend/frontend-integration-guide.md)

---

**Built with ❤️ using LangGraph & FastAPI**

Last Updated: 2025-11-16

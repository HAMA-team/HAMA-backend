# 🤖 HAMA Backend

**Human-in-the-Loop AI Multiagent Investment System**

> "AI가 분석하고, 당신이 결정한다"

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**완성도: 80%** | **Phase: 1 (MVP)** | **Status: Active Development**

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

## ✨ 핵심 기능

### 1. **멀티 에이전트 AI 시스템** (LangGraph Supervisor 패턴)

```
마스터 에이전트 (Supervisor)
        ↓
┌───────┼───────┬───────┬───────┬───────┐
↓       ↓       ↓       ↓       ↓       ↓
Research Strategy Risk  Trading Portfolio General
```

**6개 서브그래프 에이전트:**
- 🔍 **Research**: 종목 분석 (재무, 기술적 지표, 뉴스 감정)
- 📈 **Strategy**: 투자 전략 (시장 사이클, 섹터 로테이션, 자산 배분)
- ⚠️ **Risk**: 리스크 평가 (VaR, 집중도, 경고 생성)
- 💰 **Trading**: 매매 실행 (주문 생성, HITL 승인, 실행)
- 📊 **Portfolio**: 포트폴리오 관리 (최적화, 리밸런싱)
- 💬 **General**: 일반 질의응답 (투자 용어, 시장 교육)

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
| **FinanceDataReader** | ✅ 연동 완료 | 주가, 거래량, 종목 리스트 |
| **DART API** | ✅ 연동 완료 | 재무제표, 공시, 기업 정보 |
| **Redis** | ✅ 작동 중 | 캐싱 (TTL 60초) |
| **한국투자증권 API** | ⏸️ Phase 2 | 실시간 시세 |
| **네이버 금융** | ⏸️ Phase 2 | 뉴스 크롤링 |

### 4. **RESTful API** (FastAPI)

- `POST /api/v1/chat/` - 대화형 인터페이스
- `POST /api/v1/chat/approve` - HITL 승인/거부
- `GET /api/v1/chat/history/{id}` - 대화 이력 조회

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
- **FinanceDataReader** - KRX 시장 데이터
- **DART Open API** - 금융감독원 공시 시스템

### **DevOps**
- **Docker** (예정) - 컨테이너화
- **pytest** - 테스트 프레임워크
- **Git** - 버전 관리

---

## 🚀 빠른 시작

### **1. 사전 요구사항**

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
# 간단한 질문
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "삼성전자 주가는 얼마야?",
    "automation_level": 2
  }'

# 매매 요청 (HITL 발생)
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "삼성전자 10주 매수해줘",
    "automation_level": 2
  }'
```

### **7. 채팅 히스토리 & 테스트 모드**

- 채팅 세션과 메시지는 `chat_sessions`, `chat_messages` 테이블에 저장됩니다. 최초 설정 시 `alembic upgrade head` 명령으로 테이블을 생성하세요.
- `.env`에서 `ENV=test`로 설정하거나 `ANTHROPIC_API_KEY`를 비워 두면 LangGraph가 외부 LLM 대신 모의 응답/승인 플로우를 반환해 안전하게 테스트할 수 있습니다.

---

## 📡 API 문서

### **주요 엔드포인트**

#### **POST `/api/v1/chat/`** - 대화 처리

**Request:**
```json
{
  "message": "삼성전자 10주 매수해줘",
  "conversation_id": "optional-thread-id",
  "automation_level": 2
}
```

**Response (HITL 발생):**
```json
{
  "message": "🔔 사용자 승인이 필요합니다.",
  "conversation_id": "abc123-def456",
  "requires_approval": true,
  "approval_request": {
    "type": "trade_approval",
    "thread_id": "abc123-def456",
    "interrupt_data": {
      "order_id": "ORDER_a1b2c3d4",
      "stock_code": "005930",
      "quantity": 10,
      "order_type": "buy"
    }
  }
}
```

#### **POST `/api/v1/chat/approve`** - 승인/거부

**Request:**
```json
{
  "thread_id": "abc123-def456",
  "decision": "approved",  // "approved" | "rejected" | "modified"
  "automation_level": 2,
  "user_notes": "좋은 타이밍"
}
```

**Response:**
```json
{
  "status": "approved",
  "message": "승인 완료 - 매매가 실행되었습니다.",
  "result": {
    "order_id": "ORDER_a1b2c3d4",
    "status": "executed",
    "total": 890000
  }
}
```

#### **GET `/api/v1/chat/history/{conversation_id}`** - 대화 히스토리 조회

```bash
curl http://localhost:8000/api/v1/chat/history/abc123-def456
```

```json
{
  "conversation_id": "abc123-def456",
  "automation_level": 2,
  "messages": [
    {"role": "user", "content": "삼성전자 10주 매수해줘"},
    {"role": "assistant", "content": "🔔 사용자 승인이 필요합니다."}
  ]
}
```

#### **DELETE `/api/v1/chat/history/{conversation_id}`** - 히스토리 삭제

```bash
curl -X DELETE http://localhost:8000/api/v1/chat/history/abc123-def456
```

### **자세한 문서**

- 📄 [프론트엔드 통합 가이드](docs/frontend-integration-guide.md) - React 예시 포함
- 📄 [API 빠른 참조](docs/api-quick-reference.md)
- 🌐 [OpenAPI Swagger](http://localhost:8000/docs)

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
│   │   ├── research/        ✅ 서브그래프 (종목 분석)
│   │   ├── strategy/        ✅ 서브그래프 (투자 전략)
│   │   ├── risk/            ✅ 서브그래프 (리스크 평가)
│   │   ├── trading/         ✅ 서브그래프 (매매 실행)
│   │   ├── portfolio/       ✅ 서브그래프 (포트폴리오)
│   │   ├── general/         ✅ 서브그래프 (일반 QA)
│   │   ├── graph_master.py  ✅ Supervisor (마스터 에이전트)
│   │   └── legacy/          ⚠️ 마이그레이션 중
│   ├── api/
│   │   └── routes/
│   │       ├── chat.py      ✅ 대화 API + HITL
│   │       ├── portfolio.py
│   │       └── stocks.py
│   ├── services/            # 데이터 서비스
│   │   ├── stock_data_service.py   ✅ FinanceDataReader
│   │   ├── dart_service.py         ✅ DART API
│   │   └── cache_manager.py        ✅ Redis 캐싱
│   ├── models/              # SQLAlchemy 모델
│   ├── schemas/             # Pydantic 스키마
│   ├── config/              # 설정
│   └── main.py              # FastAPI 앱
├── tests/
│   ├── test_agents/
│   │   ├── test_end_to_end.py           ✅ E2E 테스트 (6개 통과)
│   │   └── test_research_data_collection.py  ✅ 데이터 연동 검증
│   └── test_api_chat.py     ✅ API + HITL 테스트
├── docs/
│   ├── PRD.md               # 제품 요구사항
│   ├── schema.md            # DB 스키마
│   ├── frontend-integration-guide.md  ✅ 프론트엔드 가이드
│   ├── api-quick-reference.md         ✅ API 빠른 참조
│   └── plan/
│       ├── legacy-agent-migration.md  # 마이그레이션 계획
│       └── completed/       # 완료된 문서
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 🧪 테스트

### **테스트 실행**

```bash
# 전체 테스트
pytest

# E2E 테스트
pytest tests/test_agents/test_end_to_end.py -v

# 특정 테스트
pytest tests/test_agents/test_end_to_end.py::TestEndToEndIntegration::test_full_investment_workflow -v

# 데이터 연동 테스트
python tests/test_research_data_collection.py
```

### **테스트 커버리지**

| 테스트 카테고리 | 상태 | 비고 |
|---------------|------|------|
| End-to-End | ✅ 6/6 통과 | 전체 투자 워크플로우 |
| Research Agent | ✅ 3/3 통과 | 실제 데이터 연동 검증 |
| API + HITL | ✅ 작성 완료 | chat, approve 엔드포인트 |
| Unit Tests | 🔄 진행 중 | 개별 노드 테스트 |

---

## 📚 문서

### **핵심 문서**

| 문서 | 설명 |
|------|------|
| [PRD.md](docs/PRD.md) | 제품 요구사항 정의 |
| [schema.md](docs/schema.md) | 데이터베이스 스키마 (19개 테이블) |
| [frontend-integration-guide.md](docs/frontend-integration-guide.md) | 프론트엔드 통합 가이드 ⭐ |
| [api-quick-reference.md](docs/api-quick-reference.md) | API 빠른 참조 |
| [CLAUDE.md](CLAUDE.md) | 개발 가이드라인 |

### **계획 문서**

| 문서 | 설명 |
|------|------|
| [legacy-agent-migration.md](docs/plan/legacy-agent-migration.md) | Legacy 마이그레이션 계획 |
| [next-steps.md](docs/plan/next-steps.md) | Phase 2 계획 |

---

## 🗺️ 로드맵

### **Phase 1 (현재) - MVP 완성** 🔵 80% 완료

- [x] LangGraph Supervisor 패턴 아키텍처
- [x] 6개 서브그래프 에이전트 구현
- [x] HITL (Human-in-the-Loop) API
- [x] 실제 데이터 연동 (FinanceDataReader, DART)
- [x] Redis 캐싱 시스템
- [x] E2E 테스트 (6개 통과)
- [x] 프론트엔드 통합 가이드
- [ ] Legacy Agent 완전 제거 (1/3 완료)
- [ ] API 인증/권한 시스템
- [ ] 프론트엔드 개발

### **Phase 2 - 실제 매매 연동** 🔵 예정

- [ ] 한국투자증권 API 연동 (실시간 시세)
- [ ] 실제 매매 주문 실행
- [ ] WebSocket 실시간 알림
- [ ] 뉴스 크롤링 (네이버 금융)
- [ ] 대화 이력 저장 (DB)
- [ ] 사용자 인증 시스템 (JWT)
- [ ] 포트폴리오 백테스팅

### **Phase 3 - 확장** ⚪ 계획 중

- [ ] 해외 주식 지원
- [ ] 모바일 앱
- [ ] 자동 리밸런싱 스케줄러
- [ ] 성과 분석 대시보드
- [ ] 커뮤니티 기능

---

## 📊 완성도

| 컴포넌트 | 완성도 | 비고 |
|---------|--------|------|
| Backend Core | 🟢 90% | FastAPI + LangGraph |
| Agents | 🟢 85% | 6/9 서브그래프 완성 |
| Data Integration | 🟢 80% | FDR + DART 연동 |
| API Endpoints | 🟢 95% | HITL 포함 완성 |
| Documentation | 🟢 90% | 프론트엔드 가이드 완성 |
| Testing | 🟡 70% | E2E + API 테스트 |
| Frontend | 🔴 0% | 개발 대기 중 |
| Deployment | 🔴 0% | Phase 2 |

**전체: 80%** 🎯

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

Last Updated: 2025-10-06

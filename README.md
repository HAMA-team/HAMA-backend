# HAMA (Human-in-the-loop AI Investment Manager)

**AI가 분석하고, 당신이 결정한다**

HAMA는 LangGraph Supervisor 패턴 기반의 멀티 에이전트 AI 투자 시스템입니다. 사용자가 복잡한 시장 분석과 포트폴리오 관리의 부담을 줄이면서도, 최종 투자 결정권을 유지할 수 있도록 설계되었습니다.

## 🎯 핵심 가치

### Human-in-the-Loop (HITL)
- **3단계 자동화 레벨**: Pilot (자동화) / Copilot (승인 필요) / Advisor (정보만 제공)
- 매매 실행, 포트폴리오 변경, 리밸런싱 등 중요한 결정은 사용자가 승인
- 투자 과정의 투명성과 통제감 보장

### 멀티 에이전트 시스템
- **Master Agent (Supervisor)**: LLM 기반 동적 라우팅으로 사용자 의도 분석
- **Research Agent**: 종목 심층 분석 (펀더멘털, 기술적, 거시경제)
- **Quantitative Agent**: 정량적 전략 수립 및 매매 신호 생성
- **Direct Tools**: 실시간 시세, 포트폴리오 최적화, 리스크 계산

## 🚀 주요 기능

### 1. 지능형 종목 분석
- **펀더멘털 분석**: DART API 연동으로 재무제표, 공시 정보 자동 수집
- **기술적 분석**: RSI, MACD, Bollinger Bands 등 15+ 지표 자동 계산
- **거시경제 분석**: 한국은행 API 연동으로 금리, 환율, GDP 데이터 활용
- **뉴스 분석**: 네이버 금융 뉴스 크롤링 및 컨텍스트 제공

### 2. 포트폴리오 관리
- **시뮬레이션**: 매매 전/후 포트폴리오 변화 미리보기
- **리스크 계산**: VaR, 변동성, Sharpe Ratio 자동 계산
- **포트폴리오 최적화**: 현대 포트폴리오 이론(MPT) 기반 자산 배분
- **리밸런싱**: 목표 비중 대비 자동 조정 제안

### 3. 실시간 데이터 연동
- **pykrx**: 주가, 거래량, 종목 리스트
- **DART API**: 재무제표, 공시, 기업 정보
- **한국은행 API**: 금리, 거시경제 지표
- **한국투자증권 API**: 실시간 시세 조회 (Phase 2: 실제 매매)

### 4. 대화형 인터페이스
- **Chat API**: 자연어 기반 투자 상담 및 명령 실행
- **SSE 스트리밍**: 에이전트 실행 과정 실시간 확인
- **승인 관리**: 중요 결정에 대한 승인/거부/수정 처리

## 📐 시스템 아키텍처

### LangGraph Supervisor 패턴

```
                    사용자 (Chat Interface)
                            ↕
        ┌─────────────────────────────────────────┐
        │    Master Agent (Supervisor)            │
        │  - LLM 기반 동적 라우팅                  │
        │  - 의존성 기반 순차/병렬 조율             │
        │  - HITL 승인 관리                        │
        └─────────────────────────────────────────┘
                            ↓
    ┌───────────────────────┼───────────────────────┐
    ↓                       ↓                       ↓
┌─────────┐         ┌──────────────┐        ┌─────────────┐
│Research │         │Quantitative  │        │Direct Tools │
│SubGraph │         │SubGraph      │        │(10개)       │
├─────────┤         ├──────────────┤        ├─────────────┤
│• Planner│         │• Market Cycle│        │• KIS API    │
│• 6 Workers        │• Asset Alloc │        │• Risk Calc  │
│  (병렬)  │         │• Fund/Tech   │        │• Portfolio  │
│• Synthesis│       │• Buy/Sell    │        │  Optimizer  │
└─────────┘         └──────────────┘        │• Trading    │
                                             └─────────────┘
```

### 핵심 개념

#### SubGraph (서브그래프)
각 에이전트는 독립적인 LangGraph로 구현되어 복잡한 태스크를 병렬 처리합니다.

**Research SubGraph** (`src/subgraphs/research_subgraph/`)
- Planner: 사용자 선호도 기반 분석 계획 수립 (HITL Interrupt 지원)
- 6개 Worker 병렬 실행:
  - Data Worker: 재무제표, 기업정보
  - Technical Analyst: 기술적 지표 분석
  - Trading Flow Analyst: 기관/외국인/개인 순매수
  - Macro Worker: 거시경제 분석
  - Bull/Bear Worker: 강세/약세 시나리오
- Synthesis: 모든 분석 결과 통합

**Quantitative SubGraph** (`src/subgraphs/quantitative_subgraph/`)
- 거시 분석 → 섹터 배분 → 자산 배분
- 데이터 수집 → 펀더멘털/기술적 분석
- 매수/매도 신호 → 위험-수익 분석 → 전략 합성

#### Direct Tools (10개)
Supervisor가 직접 호출할 수 있는 도구들 (`src/subgraphs/tools/`)
- `get_current_price()`: 실시간 주가 조회
- `resolve_ticker()`: 종목명 → 코드 변환
- `calculate_portfolio_risk()`: VaR, 변동성 계산
- `optimize_portfolio()`: MPT 기반 최적화
- `rebalance_portfolio()`: 리밸런싱 계획 생성
- `generate_investment_report()`: 분석 보고서 생성
- `request_trade()`: 매매 주문 (HITL)

## 🛠️ 기술 스택

### 백엔드
- **Framework**: FastAPI 0.120.0
- **LangGraph**: 1.0.2 (Supervisor 패턴, SubGraph)
- **LangChain**: 1.0.7 (OpenAI, Anthropic, Google LLM 통합)
- **Database**: PostgreSQL (SQLAlchemy 2.0.44, 동기식)
- **Checkpointer**: LangGraph PostgreSQL Checkpointer

### 데이터 소스
- **pykrx**: 주가, 거래량, 종목 리스트
- **DART API**: 재무제표, 공시
- **한국은행 API**: 금리, 거시경제 지표
- **한국투자증권 API**: 실시간 시세 (Phase 2: 매매)
- **네이버 금융**: 뉴스 크롤링

### AI/ML
- **LLM**: Claude (Haiku/Sonnet), GPT-4o-mini, Gemini
- **기술지표**: pandas-ta, numpy
- **포트폴리오 최적화**: scipy (MPT)

## 📦 시작하기

### 필수 요구사항
- Python 3.11+
- PostgreSQL 14+
- uv (권장) 또는 pip

### 설치

1. **저장소 클론**
```bash
git clone https://github.com/your-org/HAMA-backend.git
cd HAMA-backend
```

2. **가상환경 설정**
```bash
# uv 사용 (권장)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 또는 venv
python -m venv .venv
source .venv/bin/activate
```

3. **의존성 설치**
```bash
uv pip install -r requirements.txt
# 또는
pip install -r requirements.txt
```

4. **환경 변수 설정**
```bash
cp .env.example .env
```

`.env` 파일 편집:
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/hama

# LLM (최소 하나 필수)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key

# External APIs
DART_API_KEY=your_dart_key  # https://opendart.fss.or.kr/
BOK_API_KEY=your_bok_key    # https://ecos.bok.or.kr/

# KIS (Phase 2, 선택)
KIS_APP_KEY=your_kis_key
KIS_APP_SECRET=your_kis_secret
KIS_ACCOUNT_NUMBER=your_account

# App Settings
LLM_MODE=anthropic  # openai, anthropic, google
ENV=development
DEBUG=True
```

5. **데이터베이스 마이그레이션**
```bash
# PostgreSQL 데이터베이스 생성
createdb hama

# Alembic 마이그레이션 실행
alembic upgrade head
```

6. **서버 실행**
```bash
uvicorn src.main:app --reload --port 8000
```

### API 문서 확인
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔌 API 엔드포인트

### Chat API (`/api/v1/chat`)
```bash
# 메시지 전송 (에이전트 실행)
POST /api/v1/chat/
{
  "user_id": "user-uuid",
  "conversation_id": "conv-uuid",  # 선택
  "message": "삼성전자 분석해줘"
}

# 승인 처리 (HITL)
POST /api/v1/chat/approve
{
  "conversation_id": "conv-uuid",
  "user_decision": "approved",  # approved/rejected/modified
  "modifications": {}  # 수정사항 (선택)
}

# SSE 스트리밍
POST /api/v1/chat/multi-stream
```

### Portfolio API (`/api/v1/portfolio`)
```bash
# 포트폴리오 조회
GET /api/v1/portfolio/?user_id=user-uuid

# 성과 지표
GET /api/v1/portfolio/{portfolio_id}/performance

# 리밸런싱
POST /api/v1/portfolio/{portfolio_id}/rebalance
```

### Stocks API (`/api/v1/stocks`)
```bash
# 종목 검색
GET /api/v1/stocks/search?query=삼성

# 종목 상세
GET /api/v1/stocks/{stock_code}
```

### Settings API (`/api/v1/settings`)
```bash
# 자동화 레벨 조회
GET /api/v1/settings/intervention?user_id=user-uuid

# 자동화 레벨 변경
PUT /api/v1/settings/intervention
{
  "user_id": "user-uuid",
  "automation_level": 2,  # 1:Pilot, 2:Copilot, 3:Advisor
  "required_approvals": ["trade", "portfolio"]
}
```

전체 엔드포인트: [API 문서](http://localhost:8000/docs)

## 🧪 테스트

### 테스트 실행

```bash
# 전체 테스트
pytest

# 특정 카테고리
pytest -m unit          # 단위 테스트
pytest -m integration   # 통합 테스트
pytest -m e2e           # E2E 테스트

# 커버리지
pytest --cov=src --cov-report=html
```

### 테스트 구조
```
tests/
├── conftest.py                          # 123개 Fixtures
├── test_graph_build.py                  # Supervisor 그래프
├── test_llm_configuration.py            # LLM 설정
├── test_kis_index.py                    # KIS API
├── test_trading_hitl_flow.py            # HITL 플로우
├── test_services/
│   └── test_trading_execution.py        # 거래 실행
└── unit/test_services/
    └── test_news_crawler_service.py     # 뉴스 크롤러
```

## 📁 프로젝트 구조

```
HAMA-backend/
├── src/
│   ├── main.py                          # FastAPI 앱 진입점
│   ├── langgraph_studio_entry.py        # LangGraph Studio 진입점
│   ├── subgraphs/                       # ⭐ LangGraph 핵심
│   │   ├── graph_master.py              # Supervisor 그래프
│   │   ├── research_subgraph/           # Research Agent
│   │   ├── quantitative_subgraph/       # Quantitative Agent
│   │   └── tools/                       # Direct Tools (10개)
│   ├── api/                             # FastAPI 라우터
│   │   ├── routes/                      # 11개 엔드포인트
│   │   └── middleware/                  # 로깅, 에러 핸들러
│   ├── services/                        # 비즈니스 로직 (19개)
│   ├── models/                          # SQLAlchemy 모델 (11개)
│   ├── schemas/                         # Pydantic 스키마 (10개)
│   ├── repositories/                    # 데이터 접근 계층 (8개)
│   ├── prompts/                         # LLM 프롬프트 (8 카테고리)
│   ├── utils/                           # 유틸리티 (9개)
│   ├── config/                          # 설정 파일
│   └── constants/                       # 상수 정의
├── tests/                               # 테스트 (11개)
├── docs/                                # 문서
│   ├── PRD.md                           # 제품 요구사항
│   ├── schema.md                        # 데이터베이스 스키마
│   └── guides/                          # 개발 가이드
│       ├── langgraph-patterns.md        # LangGraph 패턴
│       ├── clean-architecture.md        # 클린 아키텍처
│       ├── database-guide.md            # 데이터베이스
│       └── testing-guide.md             # 테스트
├── alembic/                             # DB 마이그레이션
├── requirements.txt                     # 의존성
├── pyproject.toml                       # 프로젝트 설정
├── pytest.ini                           # Pytest 설정
├── langgraph.json                       # LangGraph Studio 설정
├── CLAUDE.md                            # 개발 가이드 (AI용)
└── README.md                            # 이 파일
```

## 🎓 개발 가이드

### 핵심 원칙

1. **State-First 설계** (LangGraph 표준)
   - 모든 노드는 State를 받아서 State를 반환
   - 부작용(DB 쓰기, API 호출)은 Interrupt 전에 실행 금지

2. **Interrupt 재실행 안전 패턴**
   ```python
   # ✅ 올바른 예
   if state.get("action_prepared") and not state.get("action_executed"):
       # Interrupt 후 재진입 시 건너뛰기
       return state

   # 부작용 코드 실행
   db.execute(...)
   state["action_executed"] = True
   ```

3. **동기식 SQLAlchemy**
   ```python
   # ✅ 올바른 예
   from sqlalchemy.orm import Session
   from src.models.database import get_db

   @router.post("/api/endpoint")
   async def endpoint(db: Session = Depends(get_db)):
       user = db.query(User).filter(User.id == user_id).first()

   # ❌ 금지
   from sqlalchemy.ext.asyncio import AsyncSession  # 사용 금지
   ```

4. **의존성 방향**: API → Services → Repositories → Models

### 문서 참조
- [LangGraph 패턴 가이드](./docs/guides/langgraph-patterns.md)
- [데이터베이스 가이드](./docs/guides/database-guide.md)
- [테스트 작성 가이드](./docs/guides/testing-guide.md)
- [클린 아키텍처](./docs/guides/clean-architecture.md)

### 브랜치 전략
- `main`: 안정 버전
- `develop`: 개발 버전
- `feature/*`: 기능 개발
- `refactor/*`: 리팩토링
- `fix/*`: 버그 수정

### 커밋 메시지
```
Feat: Research Agent 기술적 분석 강화
Fix: 포트폴리오 계산 오류 수정
Refactor: KIS API 서비스 레이어 분리
Docs: LangGraph 패턴 가이드 업데이트
Test: HITL 플로우 E2E 테스트 추가
```

## 📊 현재 개발 상태

### Phase 1 (MVP) - 92% 완성

#### ✅ 완료
- LangGraph Supervisor 패턴 아키텍처
- Research & Quantitative SubGraphs
- HITL 시스템 (3단계 자동화 레벨)
- pykrx, DART, BOK API 연동
- 포트폴리오 시뮬레이션
- Chat API (SSE 스트리밍)
- 테스트 기본 구조

#### ⏳ Phase 2 예정
- 사용자 인증 (JWT)
- WebSocket 실시간 알림
- 사전 구성 스케쥴링을 통한 자동매매
- AWS/Docker 배포

## 📄 라이선스

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 문의

프로젝트 링크: [https://github.com/your-org/HAMA-backend](https://github.com/your-org/HAMA-backend)

---
**Built by HAMA Team**

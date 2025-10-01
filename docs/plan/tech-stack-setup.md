# 기술 스택 설정 가이드

**버전**: 1.0
**작성일**: 2025-10-01
**목적**: Phase 1 개발을 위한 기술 스택 및 프로젝트 초기 설정

---

## 목차

1. [기술 스택 개요](#기술-스택-개요)
2. [프로젝트 구조](#프로젝트-구조)
3. [개발 환경 설정](#개발-환경-설정)
4. [주요 라이브러리](#주요-라이브러리)
5. [데이터베이스 설정](#데이터베이스-설정)
6. [LangGraph 설정](#langgraph-설정)
7. [환경 변수](#환경-변수)

---

## 기술 스택 개요

### Phase 1 기술 스택

| 구성 요소 | 기술 | 버전 | 용도 |
|----------|------|------|-----|
| **언어** | Python | 3.11+ | 백엔드 |
| **웹 프레임워크** | FastAPI | 0.104+ | REST API |
| **AI/LLM** | OpenAI API, Claude API | - | LLM |
| **에이전트 프레임워크** | LangChain, LangGraph | 0.1+ | 멀티 에이전트 |
| **데이터베이스** | PostgreSQL | 15+ | 사용자 데이터 |
| **ORM** | SQLAlchemy | 2.0+ | DB 연동 |
| **데이터 처리** | pandas, numpy | - | 분석 |
| **금융 분석** | TA-Lib | - | 기술적 지표 |
| **데이터 소스** | pykrx, OpenDartReader, pykis | - | 주식 데이터 |
| **캐싱** | Python lru_cache | - | 메모리 캐싱 |
| **테스트** | pytest, pytest-asyncio | - | 단위/통합 테스트 |

### Phase 1에서 제외

- ❌ Redis (Phase 2에서 도입)
- ❌ Message Queue (Phase 2)
- ❌ Vector DB (Phase 2, RAG 고도화 시)

---

## 프로젝트 구조

### 디렉터리 구조

```
HAMA-backend/
├── src/
│   ├── agents/                  # 에이전트 구현
│   │   ├── __init__.py
│   │   ├── base.py              # 공통 인터페이스
│   │   ├── master_agent.py
│   │   ├── personalization_agent.py
│   │   ├── data_collection_agent.py
│   │   ├── research_agent.py
│   │   ├── strategy_agent.py
│   │   ├── portfolio_agent.py
│   │   ├── risk_agent.py
│   │   ├── monitoring_agent.py
│   │   └── education_agent.py
│   │
│   ├── subagents/               # 서브에이전트
│   │   ├── __init__.py
│   │   ├── bull_analyst.py
│   │   └── bear_analyst.py
│   │
│   ├── api/                     # 외부 API 클라이언트
│   │   ├── __init__.py
│   │   ├── dart_client.py
│   │   ├── kis_client.py
│   │   ├── pykrx_client.py
│   │   └── naver_news_scraper.py
│   │
│   ├── core/                    # 핵심 로직
│   │   ├── __init__.py
│   │   ├── state.py             # LangGraph State
│   │   ├── graph.py             # LangGraph 정의
│   │   ├── hitl.py              # HITL 로직
│   │   └── routing.py           # 라우팅 로직
│   │
│   ├── models/                  # 데이터 모델
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic 스키마
│   │   ├── database.py          # SQLAlchemy 모델
│   │   └── types.py             # 공통 타입
│   │
│   ├── services/                # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── analysis.py          # 분석 서비스
│   │   └── portfolio.py         # 포트폴리오 서비스
│   │
│   ├── utils/                   # 유틸리티
│   │   ├── __init__.py
│   │   ├── cache.py             # 캐싱
│   │   ├── logger.py            # 로깅
│   │   └── financial.py         # 금융 계산
│   │
│   ├── mock/                    # Mock 데이터
│   │   ├── __init__.py
│   │   └── mock_data.py
│   │
│   ├── config.py                # 설정
│   ├── database.py              # DB 연결
│   └── main.py                  # FastAPI 앱
│
├── tests/                       # 테스트
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                        # 문서
│   ├── plan/                    # 계획 문서
│   ├── PRD.md
│   └── 에이전트 아키텍쳐.md
│
├── scripts/                     # 스크립트
│   ├── init_db.py
│   └── seed_data.py
│
├── .env                         # 환경 변수
├── .gitignore
├── requirements.txt             # Python 의존성
├── pyproject.toml               # 프로젝트 설정
└── README.md
```

---

## 개발 환경 설정

### 1. Python 환경 설정

```bash
# Python 3.11+ 설치 확인
python --version

# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# pip 업그레이드
pip install --upgrade pip
```

### 2. 의존성 설치

#### requirements.txt 생성

```txt
# Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# AI/LLM
openai==1.3.0
anthropic==0.7.0
langchain==0.1.0
langgraph==0.0.20

# Database
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
alembic==1.12.1

# Data Processing
pandas==2.1.3
numpy==1.26.2
scipy==1.11.4

# Financial Analysis
TA-Lib==0.4.28  # 별도 설치 필요
pykrx==1.0.40
opendart-reader==0.1.5
pykis==1.0.0  # 선택

# Web Scraping (선택)
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3

# Utilities
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2

# Development
black==23.11.0
flake8==6.1.0
mypy==1.7.1
```

#### 설치 명령

```bash
pip install -r requirements.txt
```

#### TA-Lib 별도 설치 (기술적 지표용)

**macOS**:
```bash
brew install ta-lib
pip install TA-Lib
```

**Ubuntu/Debian**:
```bash
sudo apt-get install libta-lib0-dev
pip install TA-Lib
```

**Windows**:
```bash
# Wheel 파일 다운로드 후 설치
# https://github.com/cgohlke/talib-build/releases
pip install TA_Lib‑0.4.28‑cp311‑cp311‑win_amd64.whl
```

### 3. PostgreSQL 설치

```bash
# macOS
brew install postgresql@15
brew services start postgresql@15

# Ubuntu/Debian
sudo apt-get install postgresql-15

# 데이터베이스 생성
createdb hama_dev
```

---

## 주요 라이브러리

### FastAPI 기본 설정

#### src/main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="HAMA Investment System",
    description="Human-in-the-Loop AI Investment Platform",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "HAMA API v1.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# 에이전트 엔드포인트
@app.post("/api/v1/chat")
async def chat(message: str):
    # TODO: 마스터 에이전트 호출
    return {"response": "Mock response"}
```

#### 실행

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 데이터베이스 설정

### SQLAlchemy 설정

#### src/database.py

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config import settings

# 비동기 엔진
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True
)

# 세션
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Dependency
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

#### src/config.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://localhost/hama_dev"

    # API Keys
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    DART_API_KEY: str
    KIS_APP_KEY: str = ""
    KIS_APP_SECRET: str = ""

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
```

### 모델 정의

#### src/models/database.py

```python
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
from sqlalchemy.sql import func
from src.database import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    risk_tolerance = Column(String, nullable=False)
    investment_goal = Column(String, nullable=False)
    investment_horizon = Column(String, nullable=False)
    automation_level = Column(Integer, default=2)
    preferred_sectors = Column(JSON, default=[])
    avoided_stocks = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    ticker = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 마이그레이션

#### Alembic 초기화

```bash
alembic init alembic
```

#### alembic/env.py 수정

```python
from src.database import Base
from src.models.database import UserProfile, Portfolio

target_metadata = Base.metadata
```

#### 마이그레이션 생성 및 적용

```bash
# 마이그레이션 파일 생성
alembic revision --autogenerate -m "Initial tables"

# 적용
alembic upgrade head
```

---

## LangGraph 설정

### State 정의

#### src/core/state.py

```python
from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    """LangGraph 전역 상태"""
    request_id: str
    user_id: str
    automation_level: int
    query: str
    intent: Optional[str]
    user_profile: Optional[Dict]
    data_collection_result: Optional[Dict]
    research_result: Optional[Dict]
    strategy_result: Optional[Dict]
    portfolio_result: Optional[Dict]
    risk_result: Optional[Dict]
    final_response: Optional[str]
    hitl_required: bool
    hitl_trigger: Optional[Dict]
```

### Graph 정의

#### src/core/graph.py

```python
from langgraph.graph import StateGraph, END
from src.core.state import AgentState
from src.agents import (
    MasterAgent,
    PersonalizationAgent,
    DataCollectionAgent,
    # ... 다른 에이전트들
)

def create_agent_graph():
    """LangGraph 생성"""

    # 에이전트 초기화
    master = MasterAgent()
    personalization = PersonalizationAgent()
    # ... 다른 에이전트들

    # Graph 생성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("master", master.process)
    workflow.add_node("personalization", personalization.process)
    workflow.add_node("data_collection", data_collection.process)
    workflow.add_node("research", research.process)
    workflow.add_node("strategy", strategy.process)

    # 엣지 정의
    workflow.set_entry_point("master")

    workflow.add_conditional_edges(
        "master",
        lambda state: state["intent"],
        {
            "stock_analysis": "data_collection",
            "trade_execution": "strategy",
            "portfolio_review": "portfolio",
            # ...
        }
    )

    workflow.add_edge("data_collection", "research")
    workflow.add_edge("research", "strategy")
    workflow.add_edge("strategy", END)

    return workflow.compile()
```

---

## 환경 변수

### .env 파일 예시

```bash
# Environment
ENVIRONMENT=development
DEBUG=True

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/hama_dev

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Data Sources
DART_API_KEY=your_dart_api_key_here

# 한국투자증권 API (선택)
KIS_APP_KEY=your_kis_app_key
KIS_APP_SECRET=your_kis_app_secret
KIS_ACCOUNT_NO=your_account_number

# Logging
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### .env.example 파일 생성

```bash
cp .env.example .env
# .env 파일 수정
```

---

## 초기 설정 스크립트

### scripts/init_db.py

```python
import asyncio
from src.database import engine, Base
from src.models.database import UserProfile, Portfolio

async def init_db():
    """데이터베이스 초기화"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized!")

if __name__ == "__main__":
    asyncio.run(init_db())
```

### 실행

```bash
python scripts/init_db.py
```

---

## 개발 워크플로우

### 1. 개발 서버 실행

```bash
uvicorn src.main:app --reload
```

### 2. 테스트 실행

```bash
# 전체 테스트
pytest

# 커버리지
pytest --cov=src tests/

# 특정 테스트
pytest tests/unit/test_master_agent.py
```

### 3. 코드 포맷팅

```bash
# Black
black src/ tests/

# Flake8
flake8 src/ tests/

# MyPy (타입 체크)
mypy src/
```

---

## 다음 단계

1. ✅ 개발 환경 설정
2. ⏭️ 기본 인프라 구현 (FastAPI, DB)
3. ⏭️ 에이전트 Mock 구현
4. ⏭️ LangGraph 통합
5. ⏭️ 데이터 소스 연동

---

**문서 끝**

**다음 문서**: [Phase 1 타임라인](./timeline-phase1.md)
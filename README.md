# HAMA Backend - Phase 1 MVP

**Human-in-the-Loop AI Investment System**

## 프로젝트 개요

개인 투자자를 위한 멀티 에이전트 AI 투자 시스템입니다. AI가 데이터 수집 및 분석을 자동화하되, 전략 수립과 매매 결정에서는 사용자가 원하는 만큼의 통제권을 행사할 수 있습니다.

### Phase 1 목표

- ✅ FastAPI 기반 백엔드 구조 완성
- ✅ PostgreSQL 데이터베이스 스키마 설계
- ✅ 9개 에이전트 Mock 구현 (Master + 8개 서브 에이전트)
- ✅ 기본 API 엔드포인트 (/chat, /portfolio, /stocks)
- 🔄 Mock → 실제 구현 단계적 전환 예정

## 기술 스택

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL
- **AI Framework**: LangChain, LangGraph
- **LLM**: OpenAI GPT-4o
- **Data Sources**: pykrx, DART API, 네이버 금융

## 설치 및 실행

### 1. 환경 설정

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일 수정 필요
```

### 3. 서버 실행

```bash
python -m src.main
```

서버: http://localhost:8000
API 문서: http://localhost:8000/docs

## 참고 문서

- [PRD v1.2](docs/PRD.md)
- [데이터 스키마](docs/schema.md)
- [Phase 1 계획](docs/plan/phase1-overview.md)

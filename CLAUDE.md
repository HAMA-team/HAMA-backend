# HAMA 프로젝트 개발 가이드

## 프로젝트 개요

**Human-in-the-Loop(HITL) 기반 멀티 에이전트 AI 투자 시스템**

### 핵심 가설
투자자는 귀찮은 정보 분석은 하기 싫어하지만, 종목 선택과 매매 실행은 직접 하고 싶어한다.

### Vision
**"AI가 분석하고, 당신이 결정한다"**

---

## 📚 문서 참조 우선순위

1. **PRD.md** (docs/PRD.md) - 제품 요구사항 정의
2. **schema.md** (docs/schema.md) - 데이터베이스 스키마
3. **phase1-overview.md** (docs/plan/) - 구현 계획
4. **상세 가이드** (docs/guides/) - 아래 섹션 참조

---

## 🏗️ 핵심 아키텍처

### LangGraph Supervisor 패턴 기반 멀티 에이전트 시스템

**현재 구현 상태 (Phase 1 MVP - 85% 완성):**

```
사용자 (Chat Interface)
        ↕
Master Agent (LangGraph Supervisor)
  - LLM 기반 동적 라우팅
  - 의존성 기반 순차/병렬 조율
        ↓
┌───────┼───────┬───────┬───────┬───────┐
↓       ↓       ↓       ↓       ↓       ↓
Research Strategy Risk Trading Portfolio General
(✅)     (✅)    (✅)    (✅)     (✅)     (✅)
```

**에이전트 실행 방식:**
- **에이전트 간**: 의존성에 따라 **순차 실행** (Research → Strategy → Risk)
- **에이전트 내부 노드**: LangGraph로 **병렬 실행 가능** (예: Bull/Bear 분석)
- **Supervisor**: LLM이 의도를 분석하여 필요한 에이전트만 선택

### 자동화 레벨 시스템

- **Level 1 (Pilot)**: AI가 거의 모든 것을 처리, 월 1회 확인
- **Level 2 (Copilot) ⭐**: AI가 제안, 큰 결정만 승인 (기본값)
- **Level 3 (Advisor)**: AI는 정보만 제공, 사용자가 결정

---

## 🎯 개발 원칙 (Quick Reference)

### 1. Phase별 구현 전략

**Phase 1 (MVP)**: 실제 데이터 연동 완료 ✅ (85% 완성)
- ✅ LangGraph Supervisor 패턴 아키텍처
- ✅ 6개 서브그래프 에이전트 구현
- ✅ 실제 데이터 연동 (pykrx, DART API)
- ✅ 인메모리 캐싱 시스템
- ✅ HITL API (`/chat`, `/approve`)
- 🔄 테스트 커버리지 확대 중

**Phase 2**: 실제 매매 연동 (예정)
- 한국투자증권 API (실시간 시세)
- 실제 매매 주문 실행
- WebSocket 실시간 알림

### 2. HITL 구현

**승인이 필요한 작업:**
- 매매 실행
- 포트폴리오 구성/변경
- 리밸런싱
- 고위험 거래

📖 **상세 가이드**: [HITL 패턴 가이드](./docs/guides/langgraph-patterns.md#hitl-human-in-the-loop-구현)

### 3. 코드 작성 가이드

**디렉토리 구조:**
- **에이전트**: `src/agents/*.py`
- **API**: `src/api/routes/*.py`
- **모델**: `src/models/*.py`
- **스키마**: `src/schemas/*.py`

**핵심 규칙:**
- ✅ 에이전트는 LangGraph 서브그래프로 구현
- ✅ 순수 함수 원칙 (State-First 설계)
- ✅ Interrupt 사용 시 재실행 안전 패턴 적용
- ✅ 의존성 방향: API → Agents → Models

📖 **상세 가이드**:
- [LangGraph 패턴 가이드](./docs/guides/langgraph-patterns.md)
- [클린 아키텍처](./docs/guides/clean-architecture.md)

### 4. 데이터베이스 접근 정책 ⚠️

**HAMA는 동기식 SQLAlchemy를 사용합니다.**

```python
# ✅ 올바른 예
from fastapi import Depends
from sqlalchemy.orm import Session
from src.models.database import get_db

@router.post("/api/endpoint")
async def endpoint(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    return user

# ❌ 금지된 예
from sqlalchemy.ext.asyncio import AsyncSession  # 사용 금지
```

📖 **상세 가이드**: [데이터베이스 가이드](./docs/guides/database-guide.md)

### 5. LangGraph 필수 체크리스트 ✅

**Interrupt 사용 시 반드시:**
- [ ] 부작용 코드가 interrupt 전에 있는지 확인
- [ ] 있다면 → 노드 분리 또는 상태 플래그 적용
- [ ] 멱등성 체크 로직 추가
- [ ] 트랜잭션으로 동시성 제어

**State 설계 시:**
- [ ] `messages` 필드 포함 (LangGraph 표준)
- [ ] 진행 상태 플래그 명명: `{action}_prepared`, `{action}_approved`, `{action}_executed`
- [ ] 서브그래프는 별도 State 정의

📖 **상세 가이드**: [LangGraph 패턴 가이드 - 안전 패턴](./docs/guides/langgraph-patterns.md#interrupt-재실행-안전-패턴-필수)

---

## 🧪 테스트 가이드 (핵심만)

### 테스트 구조
```
tests/
├── test_services/       # 서비스 레이어
├── test_agents/         # Agent 레이어
└── test_integration.py  # 통합 테스트
```

### 의사결정 원칙
- ✅ **기존 파일 우선**: 같은 카테고리면 기존 파일에 추가
- ✅ **새 파일 최소화**: 독립적인 모듈만 새 파일
- ✅ **실제 API 키 사용**: Mock/Skip 금지

### 금지 사항 ❌
- API 키 없으면 skip 처리 금지
- LLM 호출 실패 시 mock fallback 금지
- 테스트 환경에서 가짜 키 사용 금지

📖 **상세 가이드**: [테스트 작성 가이드](./docs/guides/testing-guide.md)

---

## 📦 데이터 소스

**현재 연동 완료 (Phase 1):**
- ✅ **pykrx**: 주가, 거래량, 종목 리스트 (FinanceDataReader 대체)
- ✅ **DART API**: 재무제표, 공시, 기업 정보
- ✅ **인메모리 캐싱**: TTL 60초

**Phase 2 예정:**
- ⏸️ **한국투자증권 API**: 실시간 시세, 차트, 호가
- ⏸️ **네이버 금융**: 뉴스 크롤링
- ⏸️ **BOK API**: 금리, 거시경제 지표

---

## 🚫 금지 사항

### MVP에서 제외된 기능
- 실제 매매 실행 (시뮬레이션만)
- 사용자 계정/인증 (Phase 2)
- 해외 주식
- 모바일 앱
- 실시간 Push 알림

### 파일 생성 규칙
- ❌ 명시적 요청 없이 문서 파일(*.md) 생성 금지
- ✅ README는 이미 존재하므로 수정만
- ✅ 기존 파일 수정 우선

---

## 🎓 캡스톤 프로젝트 고려사항

- AWS 배포는 선택사항 (로컬 개발 우선)
- PostgreSQL은 로컬에서 구성
- 실제 매매 실행은 Phase 2 이후
- 데모/발표용 Mock 데이터 충실히 준비

### 작업 프로세스
1. **작업 전**: `docs/plan/` 참고하여 구현
2. **작업 중**: 알맞은 브랜치에서 작업 (필요시 분기)
3. **작업 후**:
   - 커밋 (한글 메시지, 컨벤션 준수)
   - 완료된 문서는 `docs/plan/completed/`로 이동
   - 테스트 파일에 `if __name__ == "__main__":` 구성

### 커밋 메시지 예시
```
✅ 좋은 예: "Feat: Research Agent 기술적 분석 강화"
❌ 나쁜 예: "feat: add feature with Claude"
```

---

## 📖 상세 가이드 문서

복잡한 주제는 별도 가이드를 참조하세요:

- 📘 **[LangGraph 패턴 가이드](./docs/guides/langgraph-patterns.md)**
  - Interrupt 안전 패턴, HITL 구현, State 관리
- 📘 **[데이터베이스 가이드](./docs/guides/database-guide.md)**
  - 동기식 SQLAlchemy 사용법, 금지 패턴
- 📘 **[테스트 작성 가이드](./docs/guides/testing-guide.md)**
  - 테스트 구조, 의사결정 프로세스, API 키 사용 원칙
- 📘 **[클린 아키텍처](./docs/guides/clean-architecture.md)**
  - 의존성 방향, 계층 분리, MVP 타협점

---

## 🤖 AI 협업 원칙

- Always use context7 when I need code generation, setup or configuration steps, or library/API documentation
- Use Context7 MCP tools to resolve library id and get library docs without explicit request
- 주석은 한글로 작성
- 테스트는 구조화된 형태로 생성

---

**완성도: 85%** | **Phase: 1 (MVP)** | **Status: Active Development**

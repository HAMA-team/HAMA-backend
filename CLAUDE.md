# HAMA 프로젝트 개발 가이드

## 프로젝트 개요

**Human-in-the-Loop(HITL) 기반 멀티 에이전트 AI 투자 시스템**

### 핵심 가설
투자자는 귀찮은 정보 분석은 하기 싫어하지만, 종목 선택과 매매 실행은 직접 하고 싶어한다.

### Vision
**"AI가 분석하고, 당신이 결정한다"**

## 문서 참조 우선순위

1. **PRD.md** (docs/PRD.md) - 제품 요구사항 정의
2. **schema.md** (docs/schema.md) - 데이터베이스 스키마
3. **phase1-overview.md** (docs/plan/) - 구현 계획

## 핵심 아키텍처

### 9개 에이전트 구조

```
사용자 (Chat Interface)
        ↕
마스터 에이전트 (Router + Orchestrator)
        ↓
┌───────┼───────┬───────┬───────┐
↓       ↓       ↓       ↓       ↓
Research Strategy Risk Portfolio Monitoring
Education Personalization DataCollection
```

### 자동화 레벨 시스템

- **Level 1 (Pilot)**: AI가 거의 모든 것을 처리, 월 1회 확인
- **Level 2 (Copilot) ⭐**: AI가 제안, 큰 결정만 승인 (기본값)
- **Level 3 (Advisor)**: AI는 정보만 제공, 사용자가 결정

## 개발 원칙

### 1. Phase별 구현 전략

**Phase 1 (MVP)**: Mock-First 접근
- 모든 에이전트는 Mock 데이터로 시작
- API 구조와 플로우 먼저 검증
- 실제 데이터 연동은 단계적으로

**Phase 2**: 실제 구현 전환
- 우선순위: Data Collection → Research → Strategy → Portfolio → Risk

**Phase 3**: 확장 기능
- 실제 매매 실행
- 해외 주식 지원
- 모바일 앱

### 2. HITL 구현 필수

모든 중요한 결정에는 사용자 승인이 필요:
- 매매 실행
- 포트폴리오 구성/변경
- 리밸런싱
- 고위험 거래

### 3. 코드 작성 가이드

- **에이전트**: src/agents/*.py 에 구현
- **API**: src/api/routes/*.py 에 REST 엔드포인트
- **모델**: src/models/*.py 에 SQLAlchemy 모델
- **스키마**: src/schemas/*.py 에 Pydantic 스키마

### 4. TODO 주석 활용

각 에이전트는 다음과 같은 TODO 주석 포함:
```python
# TODO Phase 1 실제 구현:
# - [ ] DART API 연동
# - [ ] LLM 기반 분석 로직
```

### 5. 클린 아키텍처 원칙 (실용적 접근)

캡스톤 프로젝트에 맞는 **실용적인 클린 아키텍처**를 적용합니다.

#### 핵심 원칙

1. **의존성 방향 규칙**
   - 외부 → 내부 (비즈니스 로직이 중심)
   - API → Agents → Models (한 방향)
   - ❌ Models → Agents (역방향 금지)

2. **계층 분리**
   ```
   api/routes/        # Interface Adapters (API 계층)
        ↓ 의존
   agents/            # Use Cases (비즈니스 로직)
        ↓ 의존
   models/            # Infrastructure (DB, 외부 API)
   ```

3. **추상화를 통한 의존성 역전**
   ```python
   # ✅ 좋은 예: 추상화에 의존
   class ResearchAgent:
       def __init__(self, data_repository: DataRepository):
           self.repo = data_repository  # 인터페이스에 의존

   # ❌ 나쁜 예: 구체 클래스에 의존
   class ResearchAgent:
       def __init__(self):
           from src.models.stock import Stock
           self.stock_model = Stock  # 직접 의존
   ```

#### 현재 구조 분석

**잘 된 부분:**
- ✅ API와 비즈니스 로직 분리
- ✅ Pydantic 스키마로 DTO 분리
- ✅ 설정 파일 분리

**개선 가능한 부분:**
- ⚠️ Repository 패턴 미적용 (선택적)
- ⚠️ 도메인 엔티티와 DB 모델 혼재 (허용 가능)

#### 적용 가이드라인

**필수 (MUST):**
- ✅ API 계층은 agents를 통해서만 비즈니스 로직 실행
- ✅ agents는 models를 직접 import하지 않고, 필요시 repository 사용
- ✅ 순환 의존성 절대 금지

**권장 (SHOULD):**
- 📌 복잡한 DB 로직은 repository 패턴 고려
- 📌 DTO (Pydantic)와 Domain Model 분리
- 📌 비즈니스 로직은 agents 또는 services에만

**선택 (MAY):**
- 💡 도메인 엔티티 별도 분리 (domain/entities/)
- 💡 Value Objects 사용
- 💡 완전한 DDD 적용

#### 실전 예시

**API 계층 (api/routes/chat.py):**
```python
from src.agents.master import master_agent
from src.schemas.agent import ChatRequest, ChatResponse

@router.post("/")
async def chat(request: ChatRequest):
    # ✅ 에이전트에게 위임
    result = await master_agent.execute(request)
    return ChatResponse(**result)
```

**비즈니스 로직 (agents/research.py):**
```python
from src.models.database import get_db  # DB 세션만
from src.schemas.agent import AgentInput, AgentOutput

class ResearchAgent:
    async def process(self, input_data: AgentInput):
        # ✅ Repository 또는 서비스 사용
        db = get_db()
        # 비즈니스 로직...
        return AgentOutput(...)
```

**데이터 계층 (models/):**
```python
# SQLAlchemy 모델 - 순수 데이터 구조
class Stock(Base):
    __tablename__ = "stocks"
    # ❌ 비즈니스 로직 금지
    # ✅ 데이터 정의만
```

#### MVP에서의 타협점

완벽한 클린 아키텍처보다 **실용성**을 우선:
- ✅ 계층 분리 유지
- ✅ 의존성 방향 준수
- ⚠️ Repository 패턴은 필요할 때만
- ⚠️ 도메인 엔티티 분리는 Phase 2에서

**중요:** 빠른 개발을 위해 일부 타협은 허용되지만, **의존성 방향**만은 반드시 지켜야 합니다!

## 데이터 소스

- **한국투자증권 API**: 실시간 시세, 차트, 호가
- **DART API**: 공시 문서, 재무제표
- **FinanceDataReader**: 과거 주가 데이터
- **네이버 금융**: 뉴스 크롤링

## 개발 시 주의사항

### ❌ MVP에서 제외된 기능
- 실제 매매 실행 (시뮬레이션만)
- 사용자 계정/인증 (Phase 2)
- 해외 주식
- 모바일 앱
- 실시간 Push 알림

### ✅ MVP에 포함되어야 할 기능
- Chat 인터페이스
- 9개 에이전트 (Mock 구현)
- 자동화 레벨 설정
- 종목 검색 및 기본 정보
- HITL 승인 인터페이스
- API 연동 (한국투자증권, DART)

## 파일 생성 규칙

### NEVER 생성하지 말 것
- 명시적 요청 없이는 문서 파일(*.md) 생성 금지
- README는 이미 존재하므로 수정만

### 우선순위
1. 기존 파일 수정 우선
2. 필수적인 경우에만 새 파일 생성
3. 사용자 명시적 요청이 있을 때만 문서 작성

## 캡스톤 프로젝트 고려사항

- AWS 배포는 선택사항 (로컬 개발 우선)
- PostgreSQL은 로컬에서 구성
- 실제 매매 실행은 Phase 2 이후
- 데모/발표용 Mock 데이터 충실히 준비
- Remember to ask me 3 questions before you plan the execution plans
- 테스트 파일을 작성할 때는 해당 파일에 있는 모든 테스트를 한 번에 실행가능하도록 if __name__ == "__main__": 를 구성해야 합니다
- 매 작업을 한 뒤에는 커밋을 하고 컨벤션에 맞게 메시지도 작성해야 해. 단, 메시지는 한글로, 써야 해. <example> Feat: 메시지는 한글로 작성 </example> 그리고 claude가 함께 작업했다는 내용을 포함시키지 마
- 작업이 시작되기 전, docs에서 plan 디렉터리를 참고해서 구현을 하고, 구현이 완료된 후에는 completed 디렉터리로 문서파일을 옮기도록 해야 합니다.
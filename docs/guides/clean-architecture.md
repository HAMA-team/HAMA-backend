# 클린 아키텍처 원칙 (실용적 접근)

캡스톤 프로젝트에 맞는 **실용적인 클린 아키텍처**를 적용합니다.

## 핵심 원칙

### 1. 의존성 방향 규칙
- 외부 → 내부 (비즈니스 로직이 중심)
- API → Agents → Models (한 방향)
- ❌ Models → Agents (역방향 금지)

### 2. 계층 분리
```
api/routes/        # Interface Adapters (API 계층)
     ↓ 의존
agents/            # Use Cases (비즈니스 로직)
     ↓ 의존
models/            # Infrastructure (DB, 외부 API)
```

### 3. 추상화를 통한 의존성 역전
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

## 현재 구조 분석

### 잘 된 부분:
- ✅ API와 비즈니스 로직 분리
- ✅ Pydantic 스키마로 DTO 분리
- ✅ 설정 파일 분리

### 개선 가능한 부분:
- ⚠️ Repository 패턴 미적용 (선택적)
- ⚠️ 도메인 엔티티와 DB 모델 혼재 (허용 가능)

## 적용 가이드라인

### 필수 (MUST):
- ✅ API 계층은 agents를 통해서만 비즈니스 로직 실행
- ✅ agents는 models를 직접 import하지 않고, 필요시 repository 사용
- ✅ 순환 의존성 절대 금지

### 권장 (SHOULD):
- 📌 복잡한 DB 로직은 repository 패턴 고려
- 📌 DTO (Pydantic)와 Domain Model 분리
- 📌 비즈니스 로직은 agents 또는 services에만

### 선택 (MAY):
- 💡 도메인 엔티티 별도 분리 (domain/entities/)
- 💡 Value Objects 사용
- 💡 완전한 DDD 적용

## 실전 예시

### API 계층 (api/routes/chat.py):
```python
from src.agents.master import master_agent
from src.schemas.agent import ChatRequest, ChatResponse

@router.post("/")
async def chat(request: ChatRequest):
    # ✅ 에이전트에게 위임
    result = await master_agent.execute(request)
    return ChatResponse(**result)
```

### 비즈니스 로직 (agents/research.py):
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

### 데이터 계층 (models/):
```python
# SQLAlchemy 모델 - 순수 데이터 구조
class Stock(Base):
    __tablename__ = "stocks"
    # ❌ 비즈니스 로직 금지
    # ✅ 데이터 정의만
```

## MVP에서의 타협점

완벽한 클린 아키텍처보다 **실용성**을 우선:
- ✅ 계층 분리 유지
- ✅ 의존성 방향 준수
- ⚠️ Repository 패턴은 필요할 때만
- ⚠️ 도메인 엔티티 분리는 Phase 2에서

**중요:** 빠른 개발을 위해 일부 타협은 허용되지만, **의존성 방향**만은 반드시 지켜야 합니다!

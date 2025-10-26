# Frontend PRD v3.0 vs Backend 현황 Gap Analysis

**작성일:** 2025-10-26
**목적:** Frontend PRD v3.0 요구사항과 현재 Backend 구현 상태 비교 분석

---

## 1. Executive Summary

### 현재 Backend 완성도

| 영역 | 완성도 | 비고 |
|------|--------|------|
| **Core 에이전트 아키텍처** | 80% | Week 1-4 구현 완료 |
| **HITL 시스템** | 90% | interrupt 구현됨, 일부 문서화 필요 |
| **데이터 연동** | 70% | FinanceDataReader, DART 완료 |
| **개인화 시스템** | 85% | Router, Profile, Memory 완료 |
| **Frontend 연동 준비** | 40% | ⚠️ API 문서화 부족 |

### 주요 Gap

1. **Artifact 저장 API** 없음 (US-1.3)
2. **Portfolio 차트 데이터 포맷** 미정의 (US-3.1)
3. **API 문서 통합** 부족 (Technical Spec 요구사항)
4. **에러 응답 표준화** 필요

---

## 2. User Stories 별 현황 분석

### US-1: Chat Interface

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-1.1: 기본 대화 | P0 | ✅ 완료 | - |
| US-1.2: AI 사고 과정 표시 | P0 | ⚠️ 부분 구현 | SSE 엔드포인트 문서화 필요 |
| US-1.3: Artifact 저장 | P0 | ❌ 미구현 | **API 신규 구현 필요** |
| US-1.4: Persistent Chat Input | P1 | ✅ 완료 | Frontend 구현 |

**Gap Detail:**

#### US-1.2: Thinking Trace 스트리밍

**현황:**
- Week 3에서 `astream_events` 구현 완료
- `overall-architecture.md` 3.2절에 언급

**필요 작업:**
```python
# src/api/routes/chat.py
@router.get("/stream")
async def stream_thinking(
    thread_id: str,
    request: Request
) -> EventSourceResponse:
    """
    SSE로 Thinking Trace 스트리밍

    Event Types:
    - thinking: 에이전트 단계별 진행 상황
    - message: 최종 답변
    """
    ...
```

**Frontend 연동 형식:**
```javascript
// Frontend: EventSource
const eventSource = new EventSource(`/api/v1/chat/stream?thread_id=${threadId}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'thinking') {
    // { agent: 'research', description: '데이터 수집 중...', timestamp: '...' }
    updateThinking(data);
  } else if (data.type === 'message') {
    // { content: '최종 답변...', timestamp: '...' }
    updateMessage(data);
  }
};
```

**우선순위:** P0 (시연 핵심 기능)

---

#### US-1.3: Artifact 저장

**현황:**
- ❌ API 미구현
- Frontend PRD 요구사항:
  - "Save as Artifact" 버튼
  - LocalStorage (Phase 1) → Backend (Phase 3)

**필요 작업:**

**Phase 1 (MVP):** Frontend LocalStorage로 구현 (Backend API 불필요)

**Phase 3:** Backend API 구현
```python
# src/api/routes/artifacts.py

@router.post("/")
async def save_artifact(
    artifact: ArtifactCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Artifact 저장

    Request:
    {
        "title": "삼성전자 분석 결과",
        "content": "...", // Markdown
        "type": "analysis" | "portfolio" | "strategy",
        "metadata": {
            "stock_code": "005930",
            "created_from_message_id": "uuid"
        }
    }
    """
    ...

@router.get("/")
async def list_artifacts(
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """
    Artifact 목록

    Response:
    {
        "items": [
            {
                "id": "uuid",
                "title": "삼성전자 분석 결과",
                "type": "analysis",
                "created_at": "2025-10-26T10:00:00Z",
                "preview": "첫 100자..."
            }
        ],
        "total": 42
    }
    """
    ...

@router.get("/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Artifact 상세

    Response:
    {
        "id": "uuid",
        "title": "삼성전자 분석 결과",
        "content": "...", // Full Markdown
        "type": "analysis",
        "metadata": {...},
        "created_at": "...",
        "updated_at": "..."
    }
    """
    ...
```

**우선순위:** P2 (Phase 3)

---

### US-2: HITL Approval

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-2.1: 매매 승인 필수 | P0 | ✅ 완료 | 데이터 구조 문서화 필요 |
| US-2.2: 승인 이력 추적 | P2 | ❌ 미구현 | Phase 2 |

**Gap Detail:**

#### US-2.1: 승인 패널 데이터 구조

**현황:**
- `interrupt()` 구현 완료
- `/chat/approve` API 존재 가능성 높음

**필요 작업:**

**Frontend PRD 요구 데이터 구조:**
```typescript
// Frontend: ApprovalPanelProps
interface ApprovalRequest {
  action: 'buy' | 'sell';
  stock_code: string;
  stock_name: string;
  quantity: number;
  price: number;
  total_amount: number;
  current_weight: number;      // 현재 포트폴리오 비중
  expected_weight: number;     // 매수 후 예상 비중
  risk_warning?: string;
  alternatives?: Alternative[];
}
```

**Backend 응답 예시:**
```python
# src/api/routes/chat.py
@router.post("/")
async def chat(request: ChatRequest):
    ...

    # interrupt 발생 시
    if state.next:
        return ChatResponse(
            requires_approval=True,
            approval_request={
                "action": "buy",
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 131,
                "price": 76300,
                "total_amount": 10000000,
                "current_weight": 0.25,      # ⚠️ 계산 필요
                "expected_weight": 0.43,     # ⚠️ 계산 필요
                "risk_warning": "단일 종목 40% 이상 시 평균 수익률 -6.8%",
                "alternatives": [
                    {
                        "suggestion": "매수 금액을 500만원으로 조정",
                        "adjusted_quantity": 65,
                        "adjusted_amount": 5000000
                    }
                ]
            },
            thread_id=thread_id,
            timestamp="..."
        )
```

**추가 구현 필요:**
- **현재/예상 비중 계산**: Portfolio Agent 호출
- **대안 제시**: Risk Agent가 생성

**우선순위:** P0

---

### US-3: Portfolio Visualization

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-3.1: 포트폴리오 즉시 시각화 | P0 | ⚠️ 부분 구현 | **차트 데이터 포맷 정의 필요** |
| US-3.2: 포트폴리오 기본 정보 | P1 | ✅ 완료 | 문서화 필요 |

**Gap Detail:**

#### US-3.1: 차트 데이터 포맷

**현황:**
- Portfolio Agent 존재
- 포트폴리오 데이터 조회 가능 (추정)

**필요 작업:**

**Frontend 요구 데이터 구조:**
```typescript
interface PortfolioData {
  stocks: Stock[];
  total_value: number;
  total_return: number;
  total_return_percent: number;
}

interface Stock {
  stock_code: string;
  stock_name: string;
  quantity: number;
  current_price: number;
  purchase_price: number;
  weight: number;           // 비중 (0~1)
  return_percent: number;
  sector: string;
}
```

**Backend API 구현:**
```python
# src/api/routes/portfolio.py

@router.get("/chart-data")
async def get_portfolio_chart_data(
    current_user: User = Depends(get_current_user)
):
    """
    포트폴리오 차트용 데이터

    Response:
    {
        "stocks": [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 10,
                "current_price": 76300,
                "purchase_price": 70000,
                "weight": 0.35,
                "return_percent": 9.0,
                "sector": "반도체"
            },
            ...
        ],
        "total_value": 10000000,
        "total_return": 900000,
        "total_return_percent": 9.0,
        "cash": 1000000
    }
    """
    portfolio = await portfolio_service.get_user_portfolio(current_user.id)

    # 차트 데이터 변환
    chart_data = {
        "stocks": [
            {
                "stock_code": holding.stock_code,
                "stock_name": await get_stock_name(holding.stock_code),
                "quantity": holding.quantity,
                "current_price": await get_current_price(holding.stock_code),
                "purchase_price": holding.avg_price,
                "weight": holding.quantity * current_price / total_value,
                "return_percent": ((current_price - holding.avg_price) / holding.avg_price) * 100,
                "sector": await get_stock_sector(holding.stock_code)  # ⚠️ DART API
            }
            for holding in portfolio.holdings
        ],
        "total_value": total_value,
        "total_return": total_return,
        "total_return_percent": (total_return / total_investment) * 100,
        "cash": portfolio.cash
    }

    return chart_data
```

**추가 구현 필요:**
- **섹터 정보**: DART API 또는 자체 DB
- **실시간 가격**: FinanceDataReader 캐싱 (60초)

**우선순위:** P0 (시연 하이라이트)

---

#### US-3.2: 예상 포트폴리오 미리보기

**현황:**
- ❌ 미구현

**Frontend 요구사항:**
- HITL 승인 패널 하단에 "예상 포트폴리오" 원 그래프 표시
- 승인 전/후 비중 비교

**필요 작업:**
```python
# src/api/routes/chat.py (HITL 응답 확장)

approval_request = {
    ...,
    "expected_portfolio_preview": {
        "current": [
            {"stock_name": "삼성전자", "weight": 0.25, "color": "#3B82F6"},
            {"stock_name": "SK하이닉스", "weight": 0.15, "color": "#10B981"},
            {"stock_name": "현금", "weight": 0.60, "color": "#6B7280"}
        ],
        "after_approval": [
            {"stock_name": "삼성전자", "weight": 0.43, "color": "#EF4444"},  # 빨강 강조
            {"stock_name": "SK하이닉스", "weight": 0.10, "color": "#10B981"},
            {"stock_name": "현금", "weight": 0.47, "color": "#6B7280"}
        ]
    }
}
```

**우선순위:** P1 (UX 향상)

---

### US-4: Automation Level

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-4.1: 자동화 수준 설정 | P2 | ✅ 완료 | 문서화 필요 |

**현황:**
- 자동화 레벨 1-3 시스템 구현 (PRD.md 3.1절)
- Backend에서 interrupt 지점 자동 결정

**Frontend 연동:**
```python
# src/api/routes/settings.py

@router.get("/automation-level")
async def get_automation_level(
    current_user: User = Depends(get_current_user)
):
    """
    현재 자동화 레벨 조회

    Response:
    {
        "level": 2,
        "level_name": "코파일럿",
        "description": "AI가 제안, 큰 결정만 승인",
        "interrupt_points": ["전략 생성", "포트폴리오 구성", "매매 실행", "리밸런싱"]
    }
    """
    ...

@router.put("/automation-level")
async def update_automation_level(
    level: int,  # 1, 2, 3
    current_user: User = Depends(get_current_user)
):
    """
    자동화 레벨 변경

    Request:
    {
        "level": 3,
        "confirm": true
    }

    Response:
    {
        "level": 3,
        "message": "어드바이저 모드로 변경되었습니다. 향후 모든 결정에 승인이 필요합니다."
    }
    """
    ...
```

**우선순위:** P2

---

### US-5: Personalized Investment Profile

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-5.1: AI 생성 투자 성향 프로필 | P1 | ✅ 완료 | 문서화 완료 (Week 4) |

**현황:**
- Week 4에서 구현 완료
- `/onboarding/profile/{user_id}` API 존재

**Frontend 연동:**
```javascript
// GET /api/v1/onboarding/profile/{user_id}
const response = await fetch(`/api/v1/onboarding/profile/${userId}`);
const data = await response.json();

console.log(data.llm_generated_profile);
// "이 투자자는 장기 성장을 목표로 하며,
//  반도체/배터리 섹터에 집중 투자하는 공격적 스타일입니다..."
```

**우선순위:** P1 (구현 완료)

---

### US-6: Onboarding Flow

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-6.1: 투자 성향 분석 | P3 | ✅ 완료 | 문서화 완료 (Week 4) |

**현황:**
- Week 4에서 구현 완료
- `/onboarding/screening` API 존재

**우선순위:** P3 (구현 완료)

---

### US-7: Internationalization

| 요구사항 | 우선순위 | Backend 상태 | Gap |
|---------|---------|-------------|-----|
| US-7.1: 다국어 지원 | P1 | ⚠️ 부분 구현 | Backend 응답 다국어 처리 필요 |

**현황:**
- Backend에서 다국어 고려 안 됨

**필요 작업:**

**Option 1: Frontend에서만 처리** (권장)
- Backend는 한국어만 응답
- Frontend에서 UI 텍스트만 번역
- AI 답변은 한국어 유지 (또는 별도 요청 시 영어)

**Option 2: Backend 다국어 지원**
```python
# src/api/routes/chat.py
@router.post("/")
async def chat(
    request: ChatRequest,
    accept_language: str = Header(default="ko")
):
    """
    다국어 지원

    Request Header:
    Accept-Language: ko | en

    Backend:
    - Router에 language 전달
    - LLM 프롬프트에 "한국어로 답변" 또는 "Answer in English"
    """
    ...
```

**우선순위:** P2 (Phase 2)

---

## 3. Technical Specification 요구사항 분석

### 3.1 API Integration (Technical Spec 3.1-3.2)

**Frontend 요구:**
- SSE (Server-Sent Events) for Real-time Thinking
- Chat API 표준 응답 형식
- Error Handling 표준

**현황:**
- ⚠️ API 문서가 산재 (PRD, plan 문서 등)
- ⚠️ OpenAPI/Swagger 문서 없음

**필요 작업:**

#### 3.1.1 OpenAPI 문서 생성

```python
# src/main.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="HAMA API",
    description="Human-in-the-Loop AI 투자 시스템 API",
    version="1.0.0"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="HAMA API",
        version="1.0.0",
        description="API 문서",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

**우선순위:** P1

---

#### 3.1.2 에러 응답 표준화

**Frontend 요구:**
```typescript
// Frontend: APIError
class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string
  ) {
    super(message);
  }
}
```

**Backend 표준 응답:**
```python
# src/api/error_handlers.py

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

class APIException(Exception):
    def __init__(self, status_code: int, message: str, code: str = None):
        self.status_code = status_code
        self.message = message
        self.code = code

def setup_error_handlers(app: FastAPI):
    @app.exception_handler(APIException)
    async def api_exception_handler(request, exc: APIException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "code": exc.code,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        return JSONResponse(
            status_code=404,
            content={
                "error": True,
                "message": "요청하신 리소스를 찾을 수 없습니다",
                "code": "NOT_FOUND"
            }
        )

    @app.exception_handler(429)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={
                "error": True,
                "message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요",
                "code": "RATE_LIMIT_EXCEEDED"
            }
        )

# src/main.py
setup_error_handlers(app)
```

**우선순위:** P1

---

### 3.2 State Management (Technical Spec 4.1)

**Frontend 요구:**
- Zustand 기반 Global State
- Chat messages, approval panel state

**Backend 역할:**
- ✅ 상태 관리는 Frontend 책임
- Backend는 stateless (LangGraph checkpointer만 관리)

**연동 포인트:**
```python
# Backend: thread_id 기반 대화 상태 유지
@router.post("/chat")
async def chat(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "checkpoint_ns": request.user_id
        }
    }
    ...
```

**우선순위:** ✅ Backend 추가 작업 불필요

---

## 4. 우선순위별 구현 계획

### Phase 1: MVP 시연 필수 기능 (P0)

**목표:** 2025-11-02 (1주)

| 작업 | 담당 | 예상 시간 | 우선순위 |
|------|------|---------|---------|
| **1. Thinking Trace SSE 구현** | Backend | 4시간 | P0 |
| **2. Portfolio 차트 데이터 API** | Backend | 6시간 | P0 |
| **3. HITL 응답 데이터 구조 문서화** | Backend | 2시간 | P0 |
| **4. 에러 응답 표준화** | Backend | 3시간 | P0 |
| **5. OpenAPI 문서 생성** | Backend | 2시간 | P0 |
| **6. Frontend 연동 가이드 작성** | Backend | 3시간 | P0 |

**총 예상 시간:** 20시간 (2.5일)

---

### Phase 2: UX 향상 (P1)

**목표:** 2025-11-09 (1주)

| 작업 | 담당 | 예상 시간 | 우선순위 |
|------|------|---------|---------|
| **1. 예상 포트폴리오 미리보기 API** | Backend | 4시간 | P1 |
| **2. 자동화 레벨 설정 API** | Backend | 2시간 | P1 |
| **3. 섹터 정보 DB 구축** | Backend | 4시간 | P1 |
| **4. API 성능 최적화** | Backend | 4시간 | P1 |

**총 예상 시간:** 14시간 (2일)

---

### Phase 3: 완성도 향상 (P2)

**목표:** 2025-11-16 (1주)

| 작업 | 담당 | 예상 시간 | 우선순위 |
|------|------|---------|---------|
| **1. Artifact 저장 API** | Backend | 6시간 | P2 |
| **2. 승인 이력 추적 API** | Backend | 4시간 | P2 |
| **3. 다국어 지원** | Backend | 4시간 | P2 |
| **4. E2E 테스트** | Backend | 6시간 | P2 |

**총 예상 시간:** 20시간 (2.5일)

---

## 5. 위험 요소 및 완화 방안

| 위험 | 영향도 | 완화 방안 |
|------|--------|----------|
| **섹터 정보 없음** | High | DART API 또는 자체 DB 구축 (1일) |
| **실시간 가격 지연** | Medium | FinanceDataReader 캐싱 (60초) |
| **SSE 연결 불안정** | Medium | Polling fallback 구현 |
| **Frontend-Backend 스키마 불일치** | High | OpenAPI 문서 기반 개발 |

---

## 6. 다음 단계 (Action Items)

### 즉시 착수 (이번 주)

1. **OpenAPI 문서 생성** (2시간)
   - FastAPI 자동 문서화 활용
   - `/docs` 엔드포인트 활성화

2. **에러 응답 표준화** (3시간)
   - `APIException` 클래스 구현
   - 전역 에러 핸들러 등록

3. **Thinking Trace SSE 구현** (4시간)
   - `/chat/stream` 엔드포인트
   - Frontend 연동 가이드

4. **Portfolio 차트 데이터 API** (6시간)
   - `/portfolio/chart-data` 구현
   - 섹터 정보 Mock 데이터 (임시)

5. **HITL 데이터 구조 문서화** (2시간)
   - `approval_request` 스키마 명시
   - 예시 응답 작성

### 다음 주

6. **섹터 정보 DB 구축** (4시간)
7. **예상 포트폴리오 미리보기 API** (4시간)
8. **Frontend 연동 테스트** (6시간)

---

## 7. 문서 참조

| 문서 | 위치 | 관련 내용 |
|------|------|----------|
| **Backend PRD** | `docs/PRD.md` | 에이전트 아키텍처, 자동화 레벨 |
| **Frontend PRD v3.0** | (제공받은 문서) | User Stories, Technical Spec |
| **Week 4 구현 문서** | `docs/plan/week4-implementation.md` | AI Profile, Memory |
| **Overall Architecture** | `docs/plan/overall-architecture.md` | Router, ReAct |

---

**작성자:** Claude + 팀원
**최종 검토:** 2025-10-26

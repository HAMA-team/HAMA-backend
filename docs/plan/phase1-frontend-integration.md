# Phase 1: Frontend 연동 필수 기능 구현

**기간:** 2025-10-26 ~ 2025-11-02 (1주)
**목표:** MVP 시연에 필요한 Frontend-Backend 연동 완성

---

## 📋 구현 목록

### 1. Thinking Trace SSE 스트리밍 (4시간)

**현황:**
- Week 3에서 `astream_events` 구현 완료
- SSE 엔드포인트 미구현

**구현 내용:**

```python
# src/api/routes/chat.py

from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator
import json

@router.get("/stream")
async def stream_thinking(
    thread_id: str,
    request: Request
) -> EventSourceResponse:
    """
    SSE로 Thinking Trace 실시간 스트리밍

    Query Parameters:
    - thread_id: 대화 스레드 ID

    Event Types:
    - thinking: 에이전트 단계별 진행 상황
    - message: 최종 답변
    - done: 스트리밍 종료

    Example:
    ```
    data: {"type": "thinking", "agent": "research", "description": "데이터 수집 중...", "timestamp": "2025-10-26T10:00:00Z"}

    data: {"type": "thinking", "agent": "strategy", "description": "전략 분석 중...", "timestamp": "2025-10-26T10:00:05Z"}

    data: {"type": "message", "content": "삼성전자 분석 결과...", "timestamp": "2025-10-26T10:00:10Z"}

    data: {"type": "done"}
    ```
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Master Graph 실행 (astream_events 사용)
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            async for event in master_graph.astream_events(
                {"messages": []},  # 재개 시 빈 메시지
                config=config,
                version="v2"
            ):
                # 1. Thinking 이벤트
                if event["event"] == "on_chain_stream":
                    agent_name = event.get("name", "unknown")
                    data = event.get("data", {})

                    if "thinking" in data:
                        yield {
                            "event": "message",
                            "data": json.dumps({
                                "type": "thinking",
                                "agent": agent_name,
                                "description": data["thinking"],
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        }

                # 2. 최종 메시지
                elif event["event"] == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if "final_response" in output:
                        yield {
                            "event": "message",
                            "data": json.dumps({
                                "type": "message",
                                "content": output["final_response"],
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        }

            # 3. 완료 신호
            yield {
                "event": "message",
                "data": json.dumps({"type": "done"})
            }

        except Exception as e:
            logger.error(f"SSE streaming error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "message": str(e)
                })
            }

    return EventSourceResponse(event_generator())
```

**의존성 추가:**
```bash
pip install sse-starlette
```

**테스트:**
```bash
curl -N http://localhost:8000/api/v1/chat/stream?thread_id=test-123
```

**Frontend 연동 가이드:**
```javascript
// Frontend: EventSource
const eventSource = new EventSource(`/api/v1/chat/stream?thread_id=${threadId}`);

const thinkingSteps = [];

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'thinking':
      // Thinking 섹션 업데이트
      thinkingSteps.push({
        agent: data.agent,
        description: data.description,
        timestamp: data.timestamp
      });
      updateThinkingUI(thinkingSteps);
      break;

    case 'message':
      // 최종 답변 표시
      displayMessage(data.content);
      break;

    case 'done':
      // 스트리밍 종료
      eventSource.close();
      break;

    case 'error':
      console.error('SSE Error:', data.message);
      eventSource.close();
      break;
  }
});

eventSource.onerror = (error) => {
  console.error('EventSource failed:', error);
  eventSource.close();

  // Fallback: 폴링 모드로 전환
  startPolling(threadId);
};
```

**우선순위:** P0
**예상 시간:** 4시간

---

### 2. Portfolio 차트 데이터 API (6시간)

**구현 내용:**

```python
# src/api/routes/portfolio.py

from fastapi import APIRouter, Depends
from src.services.portfolio_service import PortfolioService
from src.services.stock_data_service import StockDataService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

@router.get("/chart-data")
async def get_portfolio_chart_data(
    current_user: User = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(),
    stock_service: StockDataService = Depends()
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
            }
        ],
        "total_value": 10000000,
        "total_return": 900000,
        "total_return_percent": 9.0,
        "cash": 1000000,
        "sectors": {
            "반도체": 0.45,
            "배터리": 0.30,
            "현금": 0.25
        }
    }
    """

    # 1. 사용자 포트폴리오 조회
    portfolio = await portfolio_service.get_user_portfolio(current_user.id)

    if not portfolio:
        return {
            "stocks": [],
            "total_value": 0,
            "total_return": 0,
            "total_return_percent": 0.0,
            "cash": 0,
            "sectors": {}
        }

    # 2. 실시간 가격 조회 (캐싱 60초)
    stock_prices = {}
    for holding in portfolio.holdings:
        price_data = await stock_service.get_stock_price(
            holding.stock_code,
            days=1
        )
        stock_prices[holding.stock_code] = price_data["current_price"]

    # 3. 섹터 정보 조회 (Mock 또는 DB)
    stock_sectors = await get_stock_sectors([h.stock_code for h in portfolio.holdings])

    # 4. 총 평가금액 계산
    total_value = sum(
        holding.quantity * stock_prices[holding.stock_code]
        for holding in portfolio.holdings
    ) + portfolio.cash

    # 5. 차트 데이터 생성
    stocks_data = []
    sector_weights = {}

    for holding in portfolio.holdings:
        current_price = stock_prices[holding.stock_code]
        holding_value = holding.quantity * current_price
        weight = holding_value / total_value if total_value > 0 else 0

        stock_info = {
            "stock_code": holding.stock_code,
            "stock_name": await get_stock_name(holding.stock_code),
            "quantity": holding.quantity,
            "current_price": current_price,
            "purchase_price": holding.avg_price,
            "weight": round(weight, 4),
            "return_percent": round(
                ((current_price - holding.avg_price) / holding.avg_price) * 100,
                2
            ),
            "sector": stock_sectors.get(holding.stock_code, "기타")
        }

        stocks_data.append(stock_info)

        # 섹터별 비중 집계
        sector = stock_info["sector"]
        sector_weights[sector] = sector_weights.get(sector, 0) + weight

    # 현금 비중 추가
    cash_weight = portfolio.cash / total_value if total_value > 0 else 0
    sector_weights["현금"] = round(cash_weight, 4)

    # 6. 총 수익률 계산
    total_investment = sum(
        holding.quantity * holding.avg_price
        for holding in portfolio.holdings
    )
    total_return = (total_value - portfolio.cash) - total_investment
    total_return_percent = (
        (total_return / total_investment) * 100
        if total_investment > 0 else 0.0
    )

    return {
        "stocks": stocks_data,
        "total_value": total_value,
        "total_return": total_return,
        "total_return_percent": round(total_return_percent, 2),
        "cash": portfolio.cash,
        "sectors": sector_weights
    }


# 헬퍼 함수
async def get_stock_sectors(stock_codes: list[str]) -> dict[str, str]:
    """
    종목 코드 → 섹터 매핑

    Phase 1: Mock 데이터
    Phase 2: DART API 또는 자체 DB
    """
    # TODO: 실제 구현 (DART API 또는 DB)
    MOCK_SECTORS = {
        "005930": "반도체",
        "000660": "반도체",
        "373220": "LG에너지솔루션",  # 배터리
        "051910": "배터리",
        "035720": "제약",
        "005380": "제약",
    }

    return {
        code: MOCK_SECTORS.get(code, "기타")
        for code in stock_codes
    }


async def get_stock_name(stock_code: str) -> str:
    """
    종목 코드 → 종목명

    캐싱 (Redis, 24시간)
    """
    cache_key = f"stock_name:{stock_code}"
    cached = await redis_client.get(cache_key)

    if cached:
        return cached

    # FinanceDataReader 또는 DART API
    stock_info = await stock_data_service.get_stock_info(stock_code)
    name = stock_info.get("name", stock_code)

    await redis_client.setex(cache_key, 86400, name)  # 24시간
    return name
```

**섹터 정보 구축 (Phase 1: Mock):**
```python
# src/data/stock_sectors.py

STOCK_SECTORS = {
    # 반도체
    "005930": "반도체",  # 삼성전자
    "000660": "반도체",  # SK하이닉스

    # 배터리
    "373220": "배터리",  # LG에너지솔루션
    "051910": "배터리",  # LG화학

    # 제약/바이오
    "035720": "제약",    # 카카오
    "005380": "제약",    # 현대차

    # 자동차
    "005380": "자동차",
    "000270": "자동차",

    # 금융
    "105560": "금융",
    "055550": "금융",
}

def get_sector(stock_code: str) -> str:
    """종목 코드로 섹터 조회"""
    return STOCK_SECTORS.get(stock_code, "기타")
```

**우선순위:** P0
**예상 시간:** 6시간

---

### 3. HITL 응답 데이터 구조 문서화 (2시간)

**현황:**
- interrupt 구현 완료
- Frontend 요구 데이터 구조 명시 필요

**구현 내용:**

```python
# src/schemas/hitl.py

from pydantic import BaseModel, Field
from typing import Optional, Literal

class Alternative(BaseModel):
    """HITL 대안 제시"""
    suggestion: str = Field(..., description="대안 설명")
    adjusted_quantity: int = Field(..., description="조정된 수량")
    adjusted_amount: int = Field(..., description="조정된 금액")

class PortfolioPreview(BaseModel):
    """예상 포트폴리오 미리보기"""
    stock_name: str
    weight: float
    color: str  # Hex color code

class ApprovalRequest(BaseModel):
    """HITL 승인 요청 데이터"""
    action: Literal["buy", "sell"] = Field(..., description="매매 유형")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    quantity: int = Field(..., description="수량")
    price: int = Field(..., description="가격 (원)")
    total_amount: int = Field(..., description="총 금액 (원)")

    # 리스크 정보
    current_weight: float = Field(..., description="현재 포트폴리오 비중 (0~1)")
    expected_weight: float = Field(..., description="매수 후 예상 비중 (0~1)")
    risk_warning: Optional[str] = Field(None, description="리스크 경고 메시지")

    # 대안 제시
    alternatives: Optional[list[Alternative]] = Field(None, description="권장 대안")

    # 예상 포트폴리오 (Phase 1: Optional, Phase 2: Required)
    expected_portfolio_preview: Optional[dict] = Field(
        None,
        description="예상 포트폴리오 미리보기 (원 그래프용)"
    )

    class Config:
        schema_extra = {
            "example": {
                "action": "buy",
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 131,
                "price": 76300,
                "total_amount": 10000000,
                "current_weight": 0.25,
                "expected_weight": 0.43,
                "risk_warning": "단일 종목 40% 이상 시 평균 수익률 -6.8%",
                "alternatives": [
                    {
                        "suggestion": "매수 금액을 500만원으로 조정 (비중 34%)",
                        "adjusted_quantity": 65,
                        "adjusted_amount": 5000000
                    }
                ],
                "expected_portfolio_preview": {
                    "current": [
                        {"stock_name": "삼성전자", "weight": 0.25, "color": "#3B82F6"},
                        {"stock_name": "SK하이닉스", "weight": 0.15, "color": "#10B981"},
                        {"stock_name": "현금", "weight": 0.60, "color": "#6B7280"}
                    ],
                    "after_approval": [
                        {"stock_name": "삼성전자", "weight": 0.43, "color": "#EF4444"},
                        {"stock_name": "SK하이닉스", "weight": 0.10, "color": "#10B981"},
                        {"stock_name": "현금", "weight": 0.47, "color": "#6B7280"}
                    ]
                }
            }
        }


class ChatResponse(BaseModel):
    """Chat API 응답"""
    message: str = Field(..., description="AI 답변 (Markdown)")
    thinking: Optional[list[dict]] = Field(None, description="Thinking Trace")
    requires_approval: bool = Field(False, description="HITL 승인 필요 여부")
    approval_request: Optional[ApprovalRequest] = Field(None, description="승인 요청 데이터")
    thread_id: str = Field(..., description="대화 스레드 ID")
    timestamp: str = Field(..., description="응답 시각 (ISO 8601)")
```

**사용 예시:**
```python
# src/agents/graph_master.py

async def execute_chat(request: ChatRequest):
    ...

    # interrupt 발생 시
    state = await master_graph.aget_state(config)

    if state.next:  # HITL 필요
        # 1. 현재/예상 비중 계산
        portfolio = await portfolio_service.get_user_portfolio(user_id)
        current_weight = calculate_weight(portfolio, state["stock_code"])
        expected_weight = calculate_expected_weight(
            portfolio,
            state["stock_code"],
            state["quantity"],
            state["price"]
        )

        # 2. 대안 생성 (Risk Agent)
        alternatives = await risk_agent.generate_alternatives(
            portfolio=portfolio,
            order=state["order_data"],
            risk_level=state["risk_level"]
        )

        # 3. 예상 포트폴리오 계산
        expected_preview = await calculate_portfolio_preview(
            current_portfolio=portfolio,
            new_order=state["order_data"]
        )

        return ChatResponse(
            message=state["last_message"],
            requires_approval=True,
            approval_request=ApprovalRequest(
                action="buy",
                stock_code=state["stock_code"],
                stock_name=state["stock_name"],
                quantity=state["quantity"],
                price=state["price"],
                total_amount=state["total_amount"],
                current_weight=current_weight,
                expected_weight=expected_weight,
                risk_warning=state["risk_warning"],
                alternatives=alternatives,
                expected_portfolio_preview=expected_preview
            ),
            thread_id=thread_id,
            timestamp=datetime.utcnow().isoformat()
        )
```

**우선순위:** P0
**예상 시간:** 2시간

---

### 4. 에러 응답 표준화 (3시간)

**구현 내용:**

```python
# src/api/error_handlers.py

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class APIException(Exception):
    """커스텀 API 예외"""

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str = None,
        details: dict = None
    ):
        self.status_code = status_code
        self.message = message
        self.code = code or f"ERROR_{status_code}"
        self.details = details or {}


def setup_error_handlers(app: FastAPI):
    """전역 에러 핸들러 등록"""

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """커스텀 API 예외 처리"""
        logger.error(
            f"API Exception: {exc.message}",
            extra={
                "status_code": exc.status_code,
                "code": exc.code,
                "path": request.url.path,
                "details": exc.details
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "code": exc.code,
                "timestamp": datetime.utcnow().isoformat(),
                **exc.details
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
    ):
        """Pydantic Validation 에러"""
        logger.warning(
            f"Validation Error: {exc.errors()}",
            extra={"path": request.url.path}
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "message": "요청 데이터가 올바르지 않습니다",
                "code": "VALIDATION_ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "details": exc.errors()
            }
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        """404 Not Found"""
        return JSONResponse(
            status_code=404,
            content={
                "error": True,
                "message": "요청하신 리소스를 찾을 수 없습니다",
                "code": "NOT_FOUND",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path
            }
        )

    @app.exception_handler(429)
    async def rate_limit_handler(request: Request, exc):
        """429 Too Many Requests"""
        return JSONResponse(
            status_code=429,
            content={
                "error": True,
                "message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요",
                "code": "RATE_LIMIT_EXCEEDED",
                "timestamp": datetime.utcnow().isoformat(),
                "retry_after": 60  # seconds
            }
        )

    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc: Exception):
        """500 Internal Server Error"""
        logger.exception(
            f"Internal Server Error: {exc}",
            extra={"path": request.url.path}
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "서버 오류가 발생했습니다",
                "code": "INTERNAL_SERVER_ERROR",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc):
        """401 Unauthorized"""
        return JSONResponse(
            status_code=401,
            content={
                "error": True,
                "message": "로그인이 필요합니다",
                "code": "UNAUTHORIZED",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        """403 Forbidden"""
        return JSONResponse(
            status_code=403,
            content={
                "error": True,
                "message": "접근 권한이 없습니다",
                "code": "FORBIDDEN",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# src/main.py
from src.api.error_handlers import setup_error_handlers

app = FastAPI(...)

# 에러 핸들러 등록
setup_error_handlers(app)
```

**사용 예시:**
```python
# src/api/routes/portfolio.py

from src.api.error_handlers import APIException

@router.get("/chart-data")
async def get_portfolio_chart_data(...):
    portfolio = await portfolio_service.get_user_portfolio(user_id)

    if not portfolio:
        raise APIException(
            status_code=404,
            message="포트폴리오를 찾을 수 없습니다",
            code="PORTFOLIO_NOT_FOUND",
            details={"user_id": user_id}
        )

    ...
```

**우선순위:** P0
**예상 시간:** 3시간

---

### 5. OpenAPI 문서 생성 (2시간)

**구현 내용:**

```python
# src/main.py

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="HAMA API",
    description="Human-in-the-Loop AI 투자 시스템 API",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
)


def custom_openapi():
    """커스텀 OpenAPI 스키마"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="HAMA API",
        version="1.0.0",
        description="""
# HAMA API Documentation

Human-in-the-Loop AI 투자 시스템 Backend API

## 인증
모든 API는 JWT 토큰 인증이 필요합니다 (Phase 2).
Phase 1에서는 인증 없이 사용 가능합니다.

## 주요 엔드포인트
- `/chat`: AI 대화 인터페이스
- `/portfolio`: 포트폴리오 관리
- `/onboarding`: 온보딩 및 프로파일

## 에러 코드
| Code | Message | 설명 |
|------|---------|------|
| `VALIDATION_ERROR` | 요청 데이터가 올바르지 않습니다 | 422 |
| `NOT_FOUND` | 리소스를 찾을 수 없습니다 | 404 |
| `RATE_LIMIT_EXCEEDED` | 요청이 너무 많습니다 | 429 |
| `INTERNAL_SERVER_ERROR` | 서버 오류 | 500 |
        """,
        routes=app.routes,
        tags=[
            {
                "name": "Chat",
                "description": "AI 대화 및 HITL 승인"
            },
            {
                "name": "Portfolio",
                "description": "포트폴리오 조회 및 차트 데이터"
            },
            {
                "name": "Onboarding",
                "description": "온보딩 및 사용자 프로파일"
            }
        ]
    )

    # 공통 응답 스키마 추가
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "error": {"type": "boolean", "example": True},
            "message": {"type": "string", "example": "에러 메시지"},
            "code": {"type": "string", "example": "ERROR_CODE"},
            "timestamp": {"type": "string", "format": "date-time"},
        },
        "required": ["error", "message", "code", "timestamp"]
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# 라우터 등록
from src.api.routes import chat, portfolio, onboarding

app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
```

**접속 URL:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

**우선순위:** P0
**예상 시간:** 2시간

---

### 6. Frontend 연동 가이드 작성 (3시간)

**구현 내용:**

```markdown
# docs/frontend-integration-guide.md

# Frontend 연동 가이드

## 1. Chat API

### 1.1 기본 대화

**Request:**
```javascript
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    message: '삼성전자 분석해줘',
    thread_id: 'uuid',
    automation_level: 2,
    config: {
      language: 'ko',
      max_tokens: 1000
    }
  })
});

const data = await response.json();
```

**Response (일반):**
```json
{
  "message": "삼성전자 분석 결과...",
  "thinking": [
    {
      "agent": "research",
      "description": "데이터 수집 중...",
      "timestamp": "2025-10-26T10:00:00Z"
    }
  ],
  "requires_approval": false,
  "thread_id": "uuid",
  "timestamp": "2025-10-26T10:00:10Z"
}
```

**Response (HITL 필요):**
```json
{
  "message": "삼성전자 1000만원 매수를 제안합니다",
  "requires_approval": true,
  "approval_request": {
    "action": "buy",
    "stock_code": "005930",
    "stock_name": "삼성전자",
    ...
  },
  "thread_id": "uuid",
  "timestamp": "..."
}
```

### 1.2 Thinking Trace 스트리밍

**EventSource:**
```javascript
const eventSource = new EventSource(`/api/v1/chat/stream?thread_id=${threadId}`);

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'thinking') {
    updateThinking(data);
  } else if (data.type === 'message') {
    displayMessage(data.content);
  } else if (data.type === 'done') {
    eventSource.close();
  }
});

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
  startPolling(threadId);  // Fallback
};
```

## 2. Portfolio API

### 2.1 차트 데이터 조회

**Request:**
```javascript
const response = await fetch('/api/v1/portfolio/chart-data');
const data = await response.json();
```

**Response:**
```json
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
    }
  ],
  "total_value": 10000000,
  "total_return": 900000,
  "total_return_percent": 9.0,
  "cash": 1000000,
  "sectors": {
    "반도체": 0.45,
    "배터리": 0.30,
    "현금": 0.25
  }
}
```

**Recharts 연동:**
```javascript
// Treemap
<Treemap
  data={data.stocks.map(s => ({
    name: s.stock_name,
    size: s.weight * 100,
    color: s.return_percent > 0 ? '#10B981' : '#EF4444'
  }))}
  dataKey="size"
/>

// Pie Chart (섹터별)
<PieChart>
  <Pie
    data={Object.entries(data.sectors).map(([name, weight]) => ({
      name,
      value: weight * 100
    }))}
    dataKey="value"
  />
</PieChart>
```

## 3. 에러 핸들링

**표준 에러 응답:**
```json
{
  "error": true,
  "message": "에러 메시지",
  "code": "ERROR_CODE",
  "timestamp": "2025-10-26T10:00:00Z"
}
```

**Frontend 에러 처리:**
```javascript
try {
  const response = await fetch('/api/v1/chat', options);

  if (!response.ok) {
    const error = await response.json();

    switch (error.code) {
      case 'VALIDATION_ERROR':
        toast.error('입력값을 확인해주세요');
        break;
      case 'NOT_FOUND':
        toast.error('요청하신 리소스를 찾을 수 없습니다');
        break;
      case 'RATE_LIMIT_EXCEEDED':
        toast.error('요청이 너무 많습니다. 잠시 후 다시 시도해주세요');
        break;
      default:
        toast.error(error.message);
    }

    throw new APIError(error.status, error.message, error.code);
  }

  return await response.json();
} catch (error) {
  console.error('API Error:', error);
}
```

**APIError 클래스:**
```typescript
class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}
```

## 4. 개발 환경 설정

**.env.local:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**API Client:**
```javascript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new APIError(response.status, error.message, error.code);
  }

  return await response.json();
}
```
```

**우선순위:** P0
**예상 시간:** 3시간

---

## 📊 일정 및 체크리스트

### Day 1 (2025-10-26)
- [ ] OpenAPI 문서 생성 (2시간)
- [ ] 에러 응답 표준화 (3시간)
- [ ] Thinking Trace SSE 구현 (4시간)

### Day 2 (2025-10-27)
- [ ] Portfolio 차트 데이터 API (6시간)
- [ ] 섹터 정보 Mock 데이터 (1시간)

### Day 3 (2025-10-28)
- [ ] HITL 응답 데이터 구조 문서화 (2시간)
- [ ] Frontend 연동 가이드 작성 (3시간)
- [ ] 통합 테스트 (2시간)

### Day 4-5 (2025-10-29~30)
- [ ] Frontend 연동 테스트
- [ ] 버그 수정
- [ ] 문서 업데이트

---

## 🧪 테스트 계획

### 단위 테스트
```python
# tests/test_api/test_portfolio.py

async def test_portfolio_chart_data():
    """포트폴리오 차트 데이터 API 테스트"""
    response = await client.get("/api/v1/portfolio/chart-data")
    assert response.status_code == 200

    data = response.json()
    assert "stocks" in data
    assert "total_value" in data
    assert "sectors" in data

    # 비중 합계 검증
    total_weight = sum(s["weight"] for s in data["stocks"]) + data["cash"] / data["total_value"]
    assert abs(total_weight - 1.0) < 0.01  # 오차 1% 이내
```

### 통합 테스트
```python
# tests/test_integration/test_chat_hitl.py

async def test_chat_hitl_flow():
    """Chat → HITL → 승인 전체 플로우"""
    # 1. Chat 요청
    response = await client.post("/api/v1/chat", json={
        "message": "삼성전자 1000만원 매수해줘",
        "thread_id": "test-123",
        "automation_level": 2
    })

    assert response.status_code == 200
    data = response.json()
    assert data["requires_approval"] == True
    assert "approval_request" in data

    # 2. 승인
    approval_response = await client.post("/api/v1/chat/approve", json={
        "thread_id": "test-123",
        "decision": "approved"
    })

    assert approval_response.status_code == 200
```

---

## 🎯 완료 기준

1. **OpenAPI 문서**
   - Swagger UI 접속 가능
   - 모든 엔드포인트 문서화
   - 예시 응답 포함

2. **에러 응답**
   - 모든 HTTP 상태 코드 표준화
   - Frontend에서 code 기반 처리 가능

3. **SSE 스트리밍**
   - Thinking Trace 실시간 업데이트
   - Frontend EventSource 연동 성공

4. **Portfolio API**
   - 차트 데이터 정확성 검증
   - 비중 합계 1.0 보장

5. **HITL 데이터 구조**
   - Frontend ApprovalPanelProps와 일치
   - 예상 포트폴리오 계산 정확

6. **Frontend 연동 가이드**
   - 모든 API 사용 예시 작성
   - 에러 핸들링 가이드 포함

---

**작성자:** Claude + 팀원
**최종 검토:** 2025-10-26
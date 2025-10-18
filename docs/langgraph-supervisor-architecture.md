# HAMA LangGraph Supervisor 아키텍처

**작성일**: 2025-10-05
**최종 업데이트**: 2025-10-19 (실제 구현 반영)
**목적**: LangGraph Supervisor 패턴 기반 Multi-Agent 시스템 아키텍처

---

## 📚 LangGraph Supervisor 패턴 개요

### 공식 패턴 정의

LangGraph Supervisor 패턴은 **중앙 조율자(Supervisor)**가 여러 **전문 에이전트(Specialized Agents)**를 관리하는 계층적 멀티 에이전트 아키텍처입니다.

**핵심 원리:**
1. **LLM 기반 동적 라우팅**: 규칙 기반이 아닌, LLM이 상황에 맞는 에이전트 선택
2. **도구로서의 에이전트**: 각 에이전트는 Supervisor가 호출할 수 있는 도구(tool)
3. **병렬 실행 지원**: `parallel_tool_calls=True`로 여러 에이전트 동시 실행
4. **메시지 기반 통신**: LangChain `MessagesState` 사용
5. **순환 구조**: Agent → Supervisor → Agent (feedback loop)

### 공식 API: create_supervisor

```python
from langgraph_supervisor import create_supervisor
from langchain_openai import ChatOpenAI

supervisor = create_supervisor(
    agents=[agent1, agent2, agent3],  # Compiled StateGraph 리스트
    model=ChatOpenAI(model="gpt-4o-mini"),
    parallel_tool_calls=True,  # 병렬 실행 활성화
    prompt="You are a supervisor managing specialized agents...",
)

app = supervisor.compile(checkpointer=MemorySaver())
```

**파라미터:**
- `agents`: Compiled StateGraph 객체 리스트 (각 에이전트는 `.compile()` 필요)
- `model`: Supervisor LLM (라우팅 판단용)
- `parallel_tool_calls`: 병렬 실행 여부 (default: `False`)
- `prompt`: Supervisor 시스템 프롬프트
- `output_mode`: 메시지 히스토리 포함 방식 (`"full_history"` | `"last_message"`)

---

## 🎯 HAMA 아키텍처 적용

### 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│                  사용자 (Chat Interface)                │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│           Master Agent (LangGraph Supervisor)           │
│                                                          │
│  - LLM 기반 동적 라우팅                                │
│  - 병렬 에이전트 실행                                  │
│  - 결과 통합 및 응답 생성                              │
└──────────────────────────┬──────────────────────────────┘
                           ↓
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Research    │   │  Strategy    │   │  Risk        │
│  Agent       │   │  Agent       │   │  Agent       │
│              │   │              │   │              │
│  - 종목 분석 │   │  - 투자 전략 │   │  - VaR 계산  │
│  - 재무/기술 │   │  - 자산 배분 │   │  - 집중도    │
│  - 뉴스 감정 │   │  - Blueprint │   │  - 경고 생성 │
└──────────────┘   └──────────────┘   └──────────────┘

┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Portfolio   │   │  Trading     │   │  Monitoring  │
│  Agent       │   │  Agent       │   │  Agent       │
│              │   │              │   │              │
│  - 최적화    │   │  - 매매 실행 │   │  - 이벤트    │
│  - 리밸런싱  │   │  - HITL      │   │  - 알림 생성 │
└──────────────┘   └──────────────┘   └──────────────┘

┌──────────────┐
│  General     │
│  Agent       │
│              │
│  - 일반 질문 │
│  - 용어 설명 │
│  - 교육      │
└──────────────┘
```

### 에이전트 구성

**총 7개 전문 에이전트:**

| 에이전트 | 역할 | 서브그래프 | HITL |
|---------|------|----------|------|
| `research_agent` | 종목 심층 분석 | ✅ 구현 완료 | - |
| `strategy_agent` | 투자 전략 수립 | ✅ 구현 완료 | - |
| `risk_agent` | 리스크 평가 | ✅ 구현 완료 | 조건부 |
| `portfolio_agent` | 포트폴리오 관리 | ✅ 구현 완료 | 조건부 |
| `trading_agent` | 매매 실행 | ✅ 구현 완료 | ✅ (L2+) |
| `monitoring_agent` | 시장 모니터링 | ❌ Phase 2 | - |
| `general_agent` | 일반 질의응답 | ✅ 구현 완료 | - |

**변경 사항:**
- ❌ `education_agent` 삭제 → `general_agent`로 통합
- ❌ `personalization_agent` 삭제 → 사용자 프로필은 DB로 관리
- ❌ `data_collection_agent` 삭제 → Service Layer로 분리
- ✅ `BaseAgent` → `LegacyAgent` (shim: `src/agents/legacy`) — 남은 레거시 에이전트 단계적 전환 예정

---

## 🔧 Master Agent 구현

### 함수 시그니처

```python
def build_supervisor(automation_level: int = 2) -> StateGraph:
    """
    Supervisor 그래프 생성

    Args:
        automation_level: 자동화 레벨 (1=Pilot, 2=Copilot, 3=Advisor)

    Returns:
        StateGraph: 컴파일되지 않은 Supervisor 그래프
    """
    ...

def build_graph(automation_level: int = 2) -> CompiledStateGraph:
    """
    최종 그래프 컴파일

    Args:
        automation_level: 자동화 레벨

    Returns:
        CompiledStateGraph: 실행 가능한 그래프
    """
    ...

async def run_graph(
    query: str,
    automation_level: int = 2,
    request_id: str = None,
    thread_id: str = None
) -> Dict[str, Any]:
    """
    그래프 실행 엔트리포인트

    Args:
        query: 사용자 질의
        automation_level: 자동화 레벨
        request_id: 요청 ID
        thread_id: 대화 스레드 ID (HITL 재개용)

    Returns:
        최종 응답 딕셔너리
    """
    ...
```

### 추상화 예시 코드

```python
from langgraph_supervisor import create_supervisor
from langchain_openai import ChatOpenAI

# 1. Compiled Agents Import
from src.agents.research import research_agent
from src.agents.strategy import strategy_agent
from src.agents.risk import risk_agent
from src.agents.trading import trading_agent
from src.agents.portfolio import portfolio_agent
from src.agents.legacy.monitoring import monitoring_agent
from src.agents.general import general_agent


# 2. Supervisor 생성
def build_supervisor(automation_level: int = 2):
    """Supervisor 패턴 구성"""

    # LLM 초기화
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Supervisor 프롬프트
    prompt = f"""당신은 투자 에이전트 팀의 Supervisor입니다.

사용 가능한 에이전트:
- research_agent: 종목 분석 (재무, 기술적, 뉴스)
- strategy_agent: 투자 전략 및 자산 배분
- risk_agent: 리스크 평가 (VaR, 집중도)
- portfolio_agent: 포트폴리오 최적화 및 리밸런싱
- trading_agent: 매매 실행 (automation_level={automation_level})
- monitoring_agent: 시장 모니터링 및 이벤트 감지
- general_agent: 일반 질문 응답 및 교육

규칙:
1. 병렬 실행 가능 (예: research + strategy + risk 동시 호출)
2. 필요한 에이전트만 선택
3. HITL은 각 에이전트가 내부 처리
"""

    # Supervisor 생성 (⭐ 핵심)
    supervisor = create_supervisor(
        agents=[
            research_agent,
            strategy_agent,
            risk_agent,
            trading_agent,
            portfolio_agent,
            monitoring_agent,
            general_agent,
        ],
        model=llm,
        parallel_tool_calls=True,  # ⭐ 병렬 실행
        prompt=prompt,
    )

    return supervisor


# 3. 그래프 컴파일
def build_graph(automation_level: int = 2, backend_key: str = None):
    """최종 그래프 빌드"""
    supervisor = build_supervisor(automation_level)

    # Checkpointer 선택 (Memory, SQLite, Redis)
    checkpointer = _create_checkpointer(backend_key or "memory")

    return supervisor.compile(checkpointer=checkpointer)


# 4. 실행
async def run_graph(query: str, automation_level: int = 2):
    """그래프 실행"""
    app = build_graph(automation_level)

    result = await app.ainvoke({
        "messages": [HumanMessage(content=query)]
    })

    return result["messages"][-1].content
```

---

## 🔧 Checkpointer 설정 (상태 저장)

HAMA는 3가지 Checkpointer 백엔드를 지원하여 그래프 실행 상태를 저장하고 HITL 재개를 가능하게 합니다.

### 지원 백엔드

| 백엔드 | 용도 | 설정 방법 |
|-------|------|---------|
| **Memory** | 개발/테스트 | 기본값 (설정 불필요) |
| **SQLite** | 단일 서버 | `GRAPH_CHECKPOINT_BACKEND=sqlite` |
| **Redis** | 분산 환경 (프로덕션) | `GRAPH_CHECKPOINT_BACKEND=redis` |

### 구현 코드

```python
def _create_checkpointer(backend_key: str):
    """backend_key에 따라 적절한 체크포인터 생성"""
    key = backend_key.lower()

    if key == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        db_path = settings.GRAPH_CHECKPOINT_SQLITE_PATH or "data/checkpoints.sqlite"
        return SqliteSaver(db_path)

    if key == "redis":
        from langgraph.checkpoint.redis import RedisSaver
        return RedisSaver.from_conn_string(settings.REDIS_URL)

    # 기본값: 인메모리
    return MemorySaver()
```

### 환경 변수 설정

```bash
# .env 파일
GRAPH_CHECKPOINT_BACKEND=redis  # memory | sqlite | redis
GRAPH_CHECKPOINT_SQLITE_PATH=data/langgraph_checkpoints.sqlite
REDIS_URL=redis://localhost:6379/0
```

### 사용 예시

```python
# Memory (기본값)
app = build_graph(automation_level=2)

# SQLite
app = build_graph(automation_level=2, backend_key="sqlite")

# Redis (프로덕션)
app = build_graph(automation_level=2, backend_key="redis")
```

### 그래프 컴파일 캐싱

성능 최적화를 위해 컴파일된 그래프를 캐싱합니다:

```python
from functools import lru_cache

@lru_cache(maxsize=16)
def get_compiled_graph(automation_level: int, backend_key: str, loop_token: str):
    """automation_level, backend_key 조합으로 캐싱"""
    state_graph = build_state_graph(automation_level)
    checkpointer = _create_checkpointer(backend_key)
    return state_graph.compile(checkpointer=checkpointer)
```

**캐싱 키:**
- `automation_level`: 1, 2, 3
- `backend_key`: memory, sqlite, redis
- `loop_token`: asyncio 이벤트 루프 식별자 (비동기 안전성)

**효과:**
- 같은 설정의 그래프 재사용 → 컴파일 오버헤드 제거
- API 요청마다 재컴파일하지 않음 → 응답 속도 향상

---

## 📋 에이전트 상세 명세

### 1. Research Agent (종목 분석)

**서브그래프 플로우:**
```
collect_data → [bull_analysis, bear_analysis] → consensus
                     (병렬 실행)
```

**함수 시그니처:**
```python
async def collect_data_node(state: ResearchState) -> dict:
    """
    데이터 수집 노드

    Args:
        state: ResearchState (stock_code 포함)

    Returns:
        dict: price_data, financial_data, company_data
    """

async def bull_analyst_node(state: ResearchState) -> dict:
    """
    강세 분석 노드 (LLM)

    Returns:
        dict: bull_analysis (상승 근거, 신뢰도)
    """

async def bear_analyst_node(state: ResearchState) -> dict:
    """
    약세 분석 노드 (LLM)

    Returns:
        dict: bear_analysis (하락 근거, 신뢰도)
    """

async def consensus_node(state: ResearchState) -> dict:
    """
    합의 의견 생성 노드

    Returns:
        dict: consensus (추천, 신뢰도, HITL 플래그)
    """
```

---

### 2. Strategy Agent (투자 전략)

**서브그래프 플로우:**
```
market_analysis → sector_rotation → asset_allocation → blueprint_creation
```

**함수 시그니처:**
```python
async def market_analysis_node(state: StrategyState) -> dict:
    """
    시장 사이클 분석 (LLM)

    Returns:
        dict: market_outlook (cycle, indicators)
    """

async def sector_rotation_node(state: StrategyState) -> dict:
    """
    섹터 로테이션 전략 (LLM)

    Returns:
        dict: sector_strategy (overweight, underweight)
    """

async def asset_allocation_node(state: StrategyState) -> dict:
    """
    자산 배분 결정

    Returns:
        dict: asset_allocation (stocks, cash, bonds)
    """

async def blueprint_creation_node(state: StrategyState) -> dict:
    """
    Strategic Blueprint 생성

    Returns:
        dict: blueprint (전략 종합, HITL 플래그)
    """
```

---

### 3. Risk Agent (리스크 평가)

**서브그래프 플로우:**
```
collect_portfolio_data → concentration_check → market_risk → final_assessment
```

**함수 시그니처:**
```python
async def collect_portfolio_data_node(state: RiskState) -> dict:
    """
    포트폴리오 데이터 수집

    Returns:
        dict: portfolio_data, market_data
    """

async def concentration_check_node(state: RiskState) -> dict:
    """
    집중도 리스크 체크

    Returns:
        dict: concentration_risk (HHI, warnings)
    """

async def market_risk_node(state: RiskState) -> dict:
    """
    시장 리스크 분석

    Returns:
        dict: market_risk (VaR, volatility)
    """

async def final_assessment_node(state: RiskState) -> dict:
    """
    종합 리스크 평가

    Returns:
        dict: risk_assessment (level, score, HITL 플래그)
    """
```

---

### 4. Trading Agent (매매 실행)

**서브그래프 플로우:**
```
prepare_trade → approve_trade (HITL) → execute_trade
```

**함수 시그니처:**
```python
def prepare_trade_node(state: TradingState) -> dict:
    """
    거래 준비 (부작용: DB 주문 생성)

    Returns:
        dict: trade_order_id, trade_prepared=True
    """

def approve_trade_node(state: TradingState) -> dict:
    """
    HITL 승인 (interrupt 발생)

    Automation Level에 따라 조건부 처리:
    - Level 1 (Pilot): 자동 승인
    - Level 2+ (Copilot/Advisor): interrupt() 호출

    Returns:
        dict: trade_approved=True

    Raises:
        interrupt: 사용자 승인 대기 (Level 2+)
    """

def execute_trade_node(state: TradingState) -> dict:
    """
    거래 실행 (부작용: API 호출)

    Returns:
        dict: trade_result, trade_executed=True
    """
```

---

### 5. Portfolio Agent (포트폴리오 관리)

**서브그래프 플로우:**
```
collect_portfolio → optimize_allocation → rebalance_plan → summary
```

**함수 시그니처:**
```python
async def collect_portfolio_node(state: PortfolioState) -> PortfolioState:
    """
    현재 포트폴리오 스냅샷 수집 (보유 종목/비중)

    Returns:
        dict: current_holdings, total_value, risk_profile
    """

async def optimize_allocation_node(state: PortfolioState) -> PortfolioState:
    """
    위험 성향 기반 목표 비중 및 기대 수익/변동성 산출

    Returns:
        dict: proposed_allocation, expected_return, sharpe_ratio
    """

async def rebalance_plan_node(state: PortfolioState) -> PortfolioState:
    """
    현재/목표 비중 차이를 계산해 리밸런싱 지시 생성

    Returns:
        dict: trades_required, rebalancing_needed, hitl_required
    """

async def summary_node(state: PortfolioState) -> PortfolioState:
    """
    최종 요약 및 포트폴리오 리포트 구성

    Returns:
        dict: summary, portfolio_report
    """
```

---

### 6. Monitoring Agent (시장 모니터링)

**TODO: 서브그래프로 전환 필요**

**함수 시그니처:**
```python
async def detect_price_events_node(state: MonitoringState) -> dict:
    """
    가격 이벤트 감지 (급등/급락)

    Returns:
        dict: price_events, alerts
    """

async def monitor_news_node(state: MonitoringState) -> dict:
    """
    뉴스 모니터링

    Returns:
        dict: important_news, sentiment
    """
```

---

### 7. General Agent (일반 질의응답)

**✅ 구현 완료**

**역할:**
- 투자 용어 설명
- 일반 시장 질문 응답
- 투자 전략 교육
- PER, PBR 등 기본 개념 설명

**서브그래프 플로우:**
```
answer_question → END
```

**함수 시그니처:**
```python
async def answer_question_node(state: GeneralState) -> dict:
    """
    일반 질문 응답 (LLM 기반)

    Args:
        state: GeneralState (query 포함)

    Returns:
        dict: answer, sources (optional)
    """
```

---

## 🔄 HITL (Human-in-the-Loop) 패턴

### Interrupt 메커니즘

**LangGraph의 `interrupt()` 함수:**
```python
from langgraph.types import interrupt

def approve_trade_node(state):
    """HITL 승인 노드"""

    # Automation Level 조건부 처리
    automation_level = state.get("automation_level", 2)

    if automation_level == 1:  # Pilot - 자동 승인
        return {"trade_approved": True}

    # Level 2+ - Interrupt 발생 (사용자 승인 대기)
    approval = interrupt({
        "type": "trade_approval",
        "order_id": state["trade_order_id"],
        "stock_code": state["stock_code"],
        "quantity": state["quantity"],
        "order_type": state["order_type"],
        "automation_level": automation_level,
        "message": "매매를 승인하시겠습니까?"
    })

    # 재개 후 승인 결과 처리
    if approval and approval.get("approved"):
        return {"trade_approved": True}
    else:
        return {"trade_approved": False, "error": "User rejected"}
```

### 승인 결정 유형

HAMA는 3가지 승인 결정을 지원합니다:

| 결정 | 설명 | API 사용 |
|------|------|---------|
| **approved** | 제안 그대로 승인 | `{"decision": "approved"}` |
| **modified** | 조건 수정 후 승인 | `{"decision": "modified", "modifications": {...}}` |
| **rejected** | 거부 (취소) | `{"decision": "rejected"}` |

**Modified 승인 예시:**

```python
# API 요청
POST /chat/approve
{
  "thread_id": "conversation_uuid",
  "decision": "modified",
  "modifications": {
    "quantity": 5,      # 10주 → 5주로 변경
    "order_price": 65000  # 시장가 → 지정가로 변경
  },
  "user_notes": "수량을 줄이고 지정가로 변경"
}

# 그래프 재개
resume_value = {
    "approved": True,
    "user_id": user_id,
    "modifications": approval.modifications,
    "notes": approval.user_notes
}

result = await app.ainvoke(Command(resume=resume_value), config)
```

**Modified 승인 처리 플로우:**

```
1. Trading Agent → interrupt() 발생
2. API → requires_approval: true 반환
3. 사용자 → 조건 수정 (quantity: 10 → 5)
4. API → Command(resume={...modifications...}) 전달
5. Trading Agent → 수정된 조건으로 execute_trade_node 실행
```

### 안전 패턴

**노드 분리 패턴:**
```python
# 1단계: 부작용 (DB 업데이트)
def prepare_node(state):
    order_id = db.create_order(...)
    return {"order_id": order_id}

# 2단계: Interrupt (순수 함수)
def approval_node(state):
    approval = interrupt(...)
    return {"approved": True}

# 3단계: 실행 (부작용)
def execute_node(state):
    result = api.execute_trade(...)
    return {"result": result}
```

**멱등성 보장:**
```python
def execute_node(state):
    # 멱등성 체크
    existing = db.get_order(state["order_id"])
    if existing and existing["status"] == "executed":
        return {"result": existing["result"]}

    # 트랜잭션으로 실행
    with db.transaction():
        result = api.execute_trade(...)
        db.update(state["order_id"], {"status": "executed"})

    return {"result": result}
```

---

## 📊 State 관리

### GraphState (Master)

Master Graph에서 사용하는 전체 공유 상태입니다. API 레이어에서 초기화됩니다.

```python
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class GraphState(TypedDict, total=False):
    """Master Graph 공유 State (API 초기화)"""

    # LangGraph 표준
    messages: Annotated[List[BaseMessage], add_messages]

    # 사용자 컨텍스트
    user_id: str
    conversation_id: str
    automation_level: int

    # 의도 및 라우팅
    intent: Optional[str]
    query: str
    agents_to_call: List[str]
    agents_called: List[str]

    # 에이전트 결과
    agent_results: Dict[str, Any]

    # 리스크 정보
    risk_level: Optional[str]
    hitl_required: bool

    # Trading Agent 실행 플래그 (안전 패턴)
    trade_prepared: bool
    trade_approved: bool
    trade_executed: bool
    trade_order_id: Optional[str]
    trade_result: Optional[Dict[str, Any]]

    # 최종 응답
    summary: Optional[str]
    final_response: Optional[Dict[str, Any]]
```

**주요 필드 설명:**

- `messages`: LangGraph 표준 메시지 스택 (add_messages reducer 적용)
- `agents_called`: 실행된 에이전트 추적 (모니터링용)
- `trade_*` 플래그: Interrupt 재실행 안전성 보장
- `final_response`: API 응답 구성용 최종 데이터

**total=False 이유:**
- 부분 업데이트 허용 (노드마다 필요한 필드만 업데이트)
- Optional 필드 명시적 표현

### 서브그래프 State 예시

```python
class ResearchState(TypedDict):
    """Research Agent State"""
    stock_code: str
    request_id: str

    # 데이터
    price_data: Optional[dict]
    financial_data: Optional[dict]

    # 분석 결과
    bull_analysis: Optional[dict]
    bear_analysis: Optional[dict]
    consensus: Optional[dict]
```

---

## 🧪 테스트 모드

API 키가 없거나 테스트 환경에서는 Mock 응답을 반환합니다.

### 활성화 조건

```python
def _is_test_mode() -> bool:
    env_value = os.getenv("ENV", settings.ENV or "").lower()
    return env_value == "test" or not settings.ANTHROPIC_API_KEY
```

**테스트 모드 활성화:**
- `ENV=test` 환경 변수 설정
- `ANTHROPIC_API_KEY` 미설정

### Mock 응답 예시

```python
# 일반 질문
request: "삼성전자 분석해줘"
response: {
    "message": "📋 테스트 응답입니다.\n요청하신 메시지: 삼성전자 분석해줘",
    "requires_approval": false,
    "metadata": {
        "intent": "general_inquiry",
        "agents_called": ["mock_general_agent"]
    }
}

# 매매 요청 (HITL 시뮬레이션)
request: "삼성전자 10주 매수"
response: {
    "message": "🔔 현재 환경은 테스트 모드입니다.\n모의 매매 요청이 접수되었으며 승인이 필요합니다.",
    "requires_approval": true,
    "approval_request": {
        "type": "trade_approval",
        "thread_id": "conversation_id",
        "message": "모의 매매 주문을 승인하시겠습니까?"
    }
}
```

**장점:**
- API 키 없이 프론트엔드 개발 가능
- CI/CD 파이프라인에서 통합 테스트 실행
- HITL 플로우 시뮬레이션

---

## 🌐 API 엔드포인트

### POST /chat

메인 채팅 엔드포인트입니다.

**Request:**
```json
{
  "message": "삼성전자 분석해줘",
  "conversation_id": "optional-uuid",
  "automation_level": 2
}
```

**Response (정상 완료):**
```json
{
  "message": "📊 분석 결과\n\n삼성전자는 반도체 업황 회복과...",
  "conversation_id": "uuid",
  "requires_approval": false,
  "metadata": {
    "intent": "stock_analysis",
    "agents_called": ["research_agent", "strategy_agent"],
    "automation_level": 2
  }
}
```

**Response (HITL 중단):**
```json
{
  "message": "🔔 사용자 승인이 필요합니다.",
  "conversation_id": "uuid",
  "requires_approval": true,
  "approval_request": {
    "type": "trade_approval",
    "thread_id": "uuid",
    "pending_node": "approve_trade",
    "interrupt_data": {
      "stock_code": "005930",
      "quantity": 10,
      "order_type": "BUY"
    },
    "message": "매매 주문을 승인하시겠습니까?"
  }
}
```

### POST /chat/approve

승인/거부 처리 엔드포인트입니다.

**Request (승인):**
```json
{
  "thread_id": "conversation-uuid",
  "decision": "approved",
  "automation_level": 2
}
```

**Request (수정 후 승인):**
```json
{
  "thread_id": "conversation-uuid",
  "decision": "modified",
  "automation_level": 2,
  "modifications": {
    "quantity": 5,
    "order_price": 65000
  },
  "user_notes": "수량 절반으로 변경"
}
```

**Request (거부):**
```json
{
  "thread_id": "conversation-uuid",
  "decision": "rejected",
  "automation_level": 2,
  "user_notes": "지금은 매수 타이밍이 아닌 것 같음"
}
```

**Response:**
```json
{
  "status": "approved",  // approved | rejected | modified
  "message": "승인 완료 - 매매가 실행되었습니다.",
  "conversation_id": "uuid",
  "result": {
    "summary": "삼성전자 10주 매수 완료",
    "trade_result": {
      "order_id": "ORD123",
      "status": "filled",
      "price": 70000,
      "quantity": 10
    }
  }
}
```

### GET /chat/history/{conversation_id}

대화 히스토리 조회

**Response:**
```json
{
  "conversation_id": "uuid",
  "user_id": "user-uuid",
  "automation_level": 2,
  "summary": "삼성전자 분석 및 매매",
  "created_at": "2025-10-19T12:00:00",
  "messages": [
    {
      "message_id": "msg-uuid",
      "role": "user",
      "content": "삼성전자 분석해줘",
      "created_at": "2025-10-19T12:00:00"
    },
    {
      "message_id": "msg-uuid2",
      "role": "assistant",
      "content": "📊 분석 결과\n\n...",
      "metadata": {
        "agents_called": ["research_agent"]
      },
      "created_at": "2025-10-19T12:00:15"
    }
  ]
}
```

### GET /chat/sessions

최근 대화 목록 조회

**Response:**
```json
[
  {
    "conversation_id": "uuid",
    "title": "삼성전자 분석 및 매매",
    "last_message": "승인 완료 - 매매가 실행되었습니다.",
    "last_message_at": "2025-10-19T12:05:00",
    "automation_level": 2,
    "message_count": 8,
    "created_at": "2025-10-19T12:00:00"
  }
]
```

---

## 🚀 실행 예시

### 사용 방법

```python
from src.agents.graph_master import run_graph

# 1. 종목 분석 (research + strategy + risk 병렬 실행)
result = await run_graph(
    query="삼성전자 분석해줘",
    automation_level=2
)

# 2. 매매 실행 (trading_agent, HITL 발생)
result = await run_graph(
    query="삼성전자 10주 매수",
    automation_level=2,
    thread_id="user123_session1"  # HITL 재개용
)

# 3. 일반 질문 (general_agent만 호출)
result = await run_graph(
    query="PER이 뭐야?",
    automation_level=2
)
```

---

## 📦 구현 현황 및 다음 단계

### Phase 1: 서브그래프 전환 ✅ **85% 완료**

- [x] Research Agent → 서브그래프 (✅ 완료)
- [x] Strategy Agent → 서브그래프 (✅ 완료)
- [x] Risk Agent → 서브그래프 (✅ 완료)
- [x] Trading Agent → 서브그래프 + HITL (✅ 완료)
- [x] Portfolio Agent → 서브그래프 (✅ 완료)
- [x] General Agent → 서브그래프 (✅ 완료)
- [ ] Monitoring Agent → 서브그래프 (⏸️ Phase 2로 연기)

**추가 구현 완료:**
- [x] 3가지 Checkpointer 지원 (Memory, SQLite, Redis)
- [x] 그래프 컴파일 캐싱 (@lru_cache)
- [x] Modified 승인 패턴
- [x] 테스트 모드 (Mock 응답)
- [x] 세션 히스토리 관리 (DB)
- [x] E2E 테스트 (6개 통과)

### Phase 2: 고도화 (예정)

- [ ] Monitoring Agent 구현
- [ ] LLM 기반 Stock Code 추출 (NER)
- [ ] 실제 한국투자증권 API 연동 (실시간 시세, 매매)
- [ ] 뉴스 크롤링 및 감정 분석
- [ ] WebSocket 실시간 알림
- [ ] 성능 최적화 (추가 캐싱, 병렬화)

### Phase 3: 프로덕션 (예정)

- [ ] 구조화된 로깅 및 모니터링
- [ ] 에러 핸들링 강화 (재시도, fallback)
- [ ] 통합 테스트 확장
- [ ] API 문서 자동화 (OpenAPI/Swagger)
- [ ] 프로덕션 배포 (AWS, Kubernetes)

---

## 📚 참고 자료

- [LangGraph Supervisor 공식 문서](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)
- [LangGraph HITL 가이드](https://langchain-ai.github.io/langgraph/how-tos/human-in-the-loop/)
- [LangGraph Checkpointer](https://langchain-ai.github.io/langgraph/reference/checkpoints/)
- [LangGraph Command API](https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.Command)

---

**작성자**: HAMA 개발팀
**최초 작성일**: 2025-10-05
**최종 업데이트**: 2025-10-19 (실제 구현 반영)
**문서 버전**: 2.0

# LangGraph 기반 개발 가이드

HAMA 시스템은 **LangGraph 네이티브 아키텍처**를 사용합니다. 모든 에이전트는 LangGraph의 노드 또는 서브그래프로 구현됩니다.

## 핵심 원칙

### State-First 설계
- 모든 상태는 `GraphState` (TypedDict)로 정의
- 노드 함수는 state를 받아 업데이트를 반환
- 순수 함수 원칙: 입력이 같으면 출력도 같아야 함

### Interrupt 재실행 메커니즘
- ⚠️ **중요:** `interrupt()` 호출 후 재개 시, 해당 노드가 **처음부터 다시 실행**됨
- DB 업데이트, API 호출 등 부작용(side effect)이 중복 실행될 위험
- 반드시 아래 안전 패턴 중 하나를 적용

### 부작용 격리
- 노드는 가능한 한 순수 함수로 작성
- DB 업데이트, API 호출은 특별히 관리

## Interrupt 재실행 안전 패턴 (필수)

### 패턴 1: 상태 플래그 패턴 (권장 ⭐)

```python
def safe_trade_node(state: GraphState) -> GraphState:
    """상태 플래그로 재실행 방지"""

    # 1단계: DB 업데이트 (재실행 시 스킵)
    if not state.get("trade_prepared"):
        db.create_order(state["order_data"])
        state["trade_prepared"] = True

    # 2단계: HITL 승인
    if not state.get("trade_approved"):
        approval = interrupt({
            "type": "trade_approval",
            "data": state["order_data"]
        })
        state["trade_approved"] = True
        state["approval_result"] = approval

    # 3단계: 실행 (1회만)
    if not state.get("trade_executed"):
        result = api.execute_trade(state["approval_result"])
        state["trade_executed"] = True
        state["result"] = result

    return state
```

### 패턴 2: 노드 분리 패턴 (가장 안전 🔒)

```python
# 노드 1: 준비 (부작용)
def prepare_order_node(state):
    order_id = db.create_order(state["order_data"])
    return {**state, "order_id": order_id}

# 노드 2: 승인 (interrupt만)
def approval_node(state):
    approval = interrupt({
        "type": "trade_approval",
        "order_id": state["order_id"]
    })
    return {**state, "approved": True}

# 노드 3: 실행 (부작용)
def execute_order_node(state):
    result = api.execute_trade(state["order_id"])
    return {**state, "result": result}

# 그래프 구성
workflow.add_edge("prepare_order", "approval")
workflow.add_edge("approval", "execute_order")
```

### 패턴 3: 멱등성 설계 (권장 ⭐⭐)

```python
def idempotent_trade_node(state):
    """여러 번 실행해도 안전"""
    order_id = state["order_id"]

    # 멱등성 체크
    existing = db.get_order(order_id)
    if existing and existing["status"] == "executed":
        return {**state, "result": existing["result"]}

    # DB 업데이트 (upsert)
    db.upsert(order_id, {"status": "preparing"})

    # HITL
    approval = interrupt({"order_id": order_id})

    # 재확인 (다른 프로세스가 실행했을 수도)
    existing = db.get_order(order_id)
    if existing["status"] == "executed":
        return {**state, "result": existing["result"]}

    # 트랜잭션으로 실행
    with db.transaction():
        result = api.execute_trade(approval)
        db.update(order_id, {"status": "executed", "result": result})

    return {**state, "result": result}
```

### 패턴 선택 기준

| 상황 | 권장 패턴 | 이유 |
|------|----------|------|
| 매매 실행 | 노드 분리 | 부작용 완전 격리 |
| 리밸런싱 | 상태 플래그 | 진행도 추적 필요 |
| 데이터 수집 | 멱등성 설계 | 중복 허용 가능 |
| 리스크 체크 | 순수 함수 | 부작용 없음 |

## HITL (Human-in-the-Loop) 구현

### 자동화 레벨별 Interrupt 설정

```python
from langgraph.checkpoint.memory import MemorySaver

def build_graph(automation_level: int):
    workflow = StateGraph(GraphState)

    # 노드 추가
    workflow.add_node("create_strategy", create_strategy_node)
    workflow.add_node("build_portfolio", build_portfolio_node)
    workflow.add_node("execute_trade", execute_trade_node)
    workflow.add_node("rebalance", rebalance_node)

    # 레벨별 interrupt 설정
    interrupt_nodes = []

    if automation_level >= 2:  # Copilot
        interrupt_nodes.extend([
            "execute_trade",
            "rebalance"
        ])

    if automation_level == 3:  # Advisor
        interrupt_nodes.extend([
            "create_strategy",
            "build_portfolio"
        ])

    # Checkpointer 설정 (MVP: MemorySaver)
    checkpointer = MemorySaver()

    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes
    )

    return app
```

### API 엔드포인트 패턴

```python
# chat.py
@router.post("/chat")
async def chat(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.conversation_id,
            "checkpoint_ns": request.user_id
        }
    }

    # 그래프 실행
    result = await app.ainvoke(
        {"messages": [HumanMessage(content=request.message)]},
        config=config
    )

    # Interrupt 확인
    state = await app.aget_state(config)
    if state.next:  # 중단됨
        return ChatResponse(
            requires_approval=True,
            approval_request={
                "type": "approval_needed",
                "thread_id": request.conversation_id,
                "pending_action": state.next[0]
            }
        )

    return ChatResponse(message=result["final_response"])

# 승인 처리
@router.post("/approve")
async def approve(approval: ApprovalRequest):
    config = {"configurable": {"thread_id": approval.thread_id}}

    if approval.decision == "approved":
        # 재개
        result = await app.ainvoke(None, config=config)
        return {"status": "executed", "result": result}
    else:
        # 취소
        await app.aupdate_state(
            config,
            {"final_response": "사용자가 거부"}
        )
        return {"status": "cancelled"}
```

### 동적 Interrupt (리스크 기반)

```python
from langgraph.types import interrupt

def risk_check_node(state: GraphState) -> GraphState:
    """리스크 수준에 따라 동적으로 중단"""
    risk_level = calculate_risk(state["portfolio"])

    # 고위험 감지 → 동적 interrupt
    if risk_level in ["high", "critical"]:
        approval = interrupt({
            "type": "high_risk_warning",
            "risk_level": risk_level,
            "warnings": state["risk_warnings"],
            "alternatives": state["alternatives"]
        })

        if not approval["proceed"]:
            return {**state, "cancelled": True}

    return state
```

## State 관리 패턴

### 전체 GraphState

```python
from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class GraphState(TypedDict):
    """전체 그래프 공유 상태"""
    # Langgraph 표준 패턴
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 사용자 컨텍스트
    user_id: str
    conversation_id: str
    automation_level: int

    # 의도 및 라우팅
    intent: str
    agents_to_call: list[str]

    # 에이전트 결과
    research_result: dict | None
    strategy_result: dict | None
    portfolio_result: dict | None
    risk_result: dict | None

    # HITL 상태
    requires_approval: bool
    approval_type: str | None

    # 실행 진행 플래그 (패턴 1용)
    trade_prepared: bool
    trade_approved: bool
    trade_executed: bool

    # 최종 응답
    final_response: dict | None
```

### 서브그래프 State (Research Agent 예시)

```python
class ResearchState(TypedDict):
    """Research Agent 서브그래프 상태"""
    stock_code: str

    # 데이터
    price_data: dict | None
    financial_data: dict | None

    # 분석 결과
    bull_analysis: dict | None
    bear_analysis: dict | None
    consensus: dict | None
```

## 서브그래프 활용 패턴

### 복잡한 에이전트는 서브그래프로

```python
# research/graph.py
def build_research_subgraph():
    """Research Agent 서브그래프"""
    workflow = StateGraph(ResearchState)

    workflow.add_node("collect_data", collect_data_node)
    workflow.add_node("bull_analysis", bull_analyst_node)
    workflow.add_node("bear_analysis", bear_analyst_node)
    workflow.add_node("consensus", consensus_node)

    # 병렬 실행
    workflow.add_edge("collect_data", "bull_analysis")
    workflow.add_edge("collect_data", "bear_analysis")
    workflow.add_edge(["bull_analysis", "bear_analysis"], "consensus")

    return workflow.compile()

# Master Graph에 통합
def research_subgraph_wrapper(state: GraphState) -> GraphState:
    """서브그래프를 Master Graph 노드로 래핑"""
    research_graph = build_research_subgraph()

    # State 변환
    research_input = {
        "stock_code": state["stock_code"],
        "price_data": None,
        "financial_data": None,
    }

    # 서브그래프 실행
    result = research_graph.invoke(research_input)

    # 결과를 Master State에 저장
    return {
        **state,
        "research_result": result["consensus"]
    }

master_workflow.add_node("research", research_subgraph_wrapper)
```

## Agent 세분화 패턴

### 패턴 1: Specialist Worker 패턴 (Research Agent)

**개요**: 복잡한 분석을 전문가 Worker로 분리하여 각 영역의 전문성 강화

**적용 예시: Research Agent**

```python
# research/nodes.py

async def technical_analyst_worker_node(state: ResearchState) -> dict:
    """기술적 분석 전문가"""
    technical_indicators = state.get("technical_indicators", {})

    # 기술적 분석: 이평선, RSI/MACD, 지지/저항선
    analysis = {
        "trend": technical_indicators.get("overall_trend", "중립"),
        "trend_strength": calculate_trend_strength(technical_indicators),
        "technical_signals": {
            "rsi_signal": technical_indicators.get("rsi", {}).get("signal", "중립"),
            "macd_signal": technical_indicators.get("macd", {}).get("signal", "중립"),
        },
        "moving_average_analysis": analyze_moving_averages(state),
        "support_resistance": calculate_support_resistance(state),
    }

    return {"technical_analysis": analysis}

async def trading_flow_analyst_worker_node(state: ResearchState) -> dict:
    """거래 동향 분석 전문가"""
    investor_data = state.get("investor_trading_data", {})

    # 외국인/기관/개인 수급 분석
    analysis = {
        "foreign_investor": {
            "trend": investor_data.get("foreign_trend", "중립"),
            "net_amount": investor_data.get("foreign_net", 0),
        },
        "institutional_investor": {
            "trend": investor_data.get("institution_trend", "중립"),
            "net_amount": investor_data.get("institution_net", 0),
        },
        "supply_demand_analysis": {
            "outlook": determine_supply_outlook(investor_data),
            "leading_investor": find_leading_investor(investor_data),
        },
    }

    return {"trading_flow_analysis": analysis}

async def information_analyst_worker_node(state: ResearchState) -> dict:
    """정보 분석 전문가"""
    # 뉴스, 호재/악재, 시장 센티먼트 분석
    analysis = {
        "market_sentiment": "긍정적",  # LLM 기반 분석
        "risk_level": "낮음",
        "positive_factors": ["실적 개선", "신제품 출시"],
        "negative_factors": [],
    }

    return {"information_analysis": analysis}

# Synthesis 노드에서 통합
async def synthesis_node(state: ResearchState) -> dict:
    """모든 전문가 분석 통합"""
    # Technical, Trading Flow, Information 분석 결과 통합
    technical = state.get("technical_analysis", {})
    trading_flow = state.get("trading_flow_analysis", {})
    information = state.get("information_analysis", {})

    # 신뢰도 조정
    confidence = adjust_confidence_with_specialists(
        base_confidence=3,
        technical=technical,
        trading_flow=trading_flow,
        information=information
    )

    consensus = {
        "recommendation": "BUY",
        "confidence": confidence,
        "technical_summary": technical,
        "trading_flow_summary": trading_flow,
        "information_summary": information,
    }

    return {"consensus": consensus}
```

**장점**:
- 각 전문가가 독립적으로 심층 분석 수행
- 분석 로직 모듈화 및 재사용성 증가
- 전문가별 가중치 조정 가능

### 패턴 2: 단순 선형 플로우 패턴 (Trading Agent) ⭐ 신규

**개요**: 복잡한 ReAct 패턴 대신 단순한 3-노드 선형 플로우로 매매 실행

**변경 이력 (2025-11-09)**:
- ❌ 기존 9-노드 ReAct 패턴 제거 (query_intent_classifier, planner, task_router, buy/sell specialists, risk_reward_calculator)
- ✅ 3-노드 선형 플로우로 단순화 (prepare → approve → execute)
- **결과**: 58% 코드 감소, 80% LLM 호출 감소, ~5배 속도 향상

**적용 예시: Trading Agent (단순화 버전)**

```python
# trading/graph.py

def build_trading_subgraph():
    """Trading Agent 서브그래프 (단순화된 구조)"""
    workflow = StateGraph(TradingState)

    # 3개 노드만 추가
    workflow.add_node("prepare_trade", prepare_trade_node)
    workflow.add_node("approval_trade", approval_trade_node)
    workflow.add_node("execute_trade", execute_trade_node)

    # 단순 선형 플로우
    workflow.set_entry_point("prepare_trade")
    workflow.add_edge("prepare_trade", "approval_trade")

    # Approval 이후 조건부 분기
    workflow.add_conditional_edges(
        "approval_trade",
        should_execute_trade,
        {
            "execute": "execute_trade",
            "end": END,
        },
    )

    workflow.add_edge("execute_trade", END)
    return workflow.compile()


def should_execute_trade(state: TradingState) -> str:
    """승인 여부에 따라 실행 결정"""
    if state.get("skip_hitl"):  # Automation Level 1
        return "execute"
    if state.get("trade_approved"):
        return "execute"
    return "end"
```

```python
# trading/nodes.py

async def prepare_trade_node(state: TradingState) -> dict:
    """1단계: LLM으로 주문 준비"""
    # 멱등성 체크
    if state.get("trade_prepared"):
        return {}

    query = state.get("query")

    # LLM으로 주문 정보 추출
    llm = get_llm()
    order_info = await llm.ainvoke(f"주문 정보 추출: {query}")

    # DB에 주문 생성
    order_id = trading_service.create_pending_order(
        stock_code=order_info["stock_code"],
        quantity=order_info["quantity"],
        order_type=order_info["order_type"],
    )

    return {
        "trade_prepared": True,
        "stock_code": order_info["stock_code"],
        "quantity": order_info["quantity"],
        "order_type": order_info["order_type"],
        "trade_order_id": order_id,
    }


async def approval_trade_node(state: TradingState) -> dict:
    """2단계: HITL 승인"""
    # Automation Level 1: 자동 승인
    automation_level = state.get("automation_level", 2)
    if automation_level == 1:
        return {"skip_hitl": True, "trade_approved": True}

    # HITL Interrupt
    approval = interrupt({
        "type": "trade_approval",
        "order_id": state["trade_order_id"],
        "summary": {
            "stock_code": state["stock_code"],
            "quantity": state["quantity"],
            "order_type": state["order_type"],
        }
    })

    if approval.get("decision") == "approved":
        return {"trade_approved": True}
    else:
        return {
            "trade_approved": False,
            "rejection_reason": approval.get("reason"),
        }


async def execute_trade_node(state: TradingState) -> dict:
    """3단계: 주문 실행"""
    # 멱등성 체크
    if state.get("trade_executed"):
        return {}

    order_id = state["trade_order_id"]

    # 실제 주문 실행
    result = trading_service.execute_order(order_id)

    return {
        "trade_executed": True,
        "trade_result": result,
    }
```

**장점**:
- **단순성**: 9 노드 → 3 노드로 복잡도 대폭 감소
- **비용 절감**: LLM 호출 5회 → 1회 (80% 감소)
- **속도**: 평균 60-90초 → 10-20초 (~5배 향상)
- **유지보수**: 선형 플로우로 디버깅 용이
- **멱등성**: 각 노드에서 플래그 체크로 재실행 안전

**제거된 노드 및 이동 계획**:
- ❌ `buy_specialist`, `sell_specialist`: Strategy Agent로 이동 예정
- ❌ `risk_reward_calculator`: Strategy Agent로 이동 예정
- ❌ `query_intent_classifier`: prepare_trade에서 LLM이 직접 처리
- ❌ `planner`, `task_router`: 선형 플로우에 불필요

### 패턴 3: Constraint Validation 패턴 (Portfolio Agent)

**개요**: 포트폴리오 제약 조건을 체계적으로 검증하고 위반 시 경고

**적용 예시: Portfolio Agent**

```python
# portfolio/nodes.py

async def market_condition_node(state: PortfolioState) -> dict:
    """시장 상황 분석 및 최대 슬롯 동적 조정"""
    market_data = state.get("portfolio_snapshot", {}).get("market_data", {})
    kospi_change = market_data.get("kospi_change_rate", 0)

    # KOSPI 변화율 기반 시장 상황 판단
    if kospi_change >= 0.05:
        market_condition = "강세장"
        max_slots = 10
    elif kospi_change <= -0.05:
        market_condition = "약세장"
        max_slots = 5  # 리스크 관리
    else:
        market_condition = "중립장"
        max_slots = 7

    return {
        "market_condition": market_condition,
        "max_slots": max_slots,
    }

async def validate_constraints_node(state: PortfolioState) -> dict:
    """포트폴리오 제약 조건 검증"""
    proposed = state.get("proposed_allocation", [])
    max_slots = state.get("max_slots", 10)
    max_sector_concentration = state.get("max_sector_concentration", 0.30)
    max_same_industry = state.get("max_same_industry_count", 3)

    violations = []

    # 1. 최대 슬롯 수 검증
    non_cash_holdings = [h for h in proposed if h.get("stock_code") != "CASH"]
    if len(non_cash_holdings) > max_slots:
        violations.append({
            "type": "max_slots",
            "message": f"최대 보유 종목 수({max_slots}개) 초과: {len(non_cash_holdings)}개",
            "severity": "high",
            "current": len(non_cash_holdings),
            "limit": max_slots,
        })

    # 2. 섹터 집중도 검증
    sector_concentration = calculate_sector_concentration(proposed)
    for sector, weight in sector_concentration.items():
        if weight > max_sector_concentration:
            violations.append({
                "type": "sector_concentration",
                "message": f"{sector} 섹터 비중 초과: {weight*100:.1f}%",
                "severity": "medium",
                "sector": sector,
                "current": weight,
                "limit": max_sector_concentration,
            })

    # 3. 동일 산업군 종목 수 검증
    industry_counts = calculate_industry_counts(proposed)
    for industry, count in industry_counts.items():
        if count > max_same_industry:
            violations.append({
                "type": "industry_count",
                "message": f"{industry} 산업군 종목 수 초과: {count}개",
                "severity": "low",
                "industry": industry,
                "current": count,
                "limit": max_same_industry,
            })

    return {"constraint_violations": violations}

# 그래프 구성
workflow.add_edge("collect_portfolio", "market_condition")
workflow.add_edge("market_condition", "optimize_allocation")
workflow.add_edge("optimize_allocation", "validate_constraints")
```

**장점**:
- 제약 조건 위반을 사전에 감지
- Severity 기반 우선순위 관리 (high/medium/low)
- 시장 상황에 따른 동적 제약 조정

### 패턴 4: 3-Tier 라우팅 패턴 (Router Agent) ⭐ 신규

**개요**: 단일 진입점에서 쿼리 복잡도에 따라 3단계 우선순위로 라우팅하여 비용/속도 최적화

**변경 이력 (2025-11-09)**:
- ❌ Supervisor 패턴 제거 (langgraph-supervisor 라이브러리)
- ✅ Router Agent로 단일화 (Claude Sonnet 4.5 + Pydantic Structured Output)
- ✅ 3-Tier 라우팅 우선순위 시스템 도입

**적용 예시: Router Agent**

```python
# router/router_agent.py

from pydantic import BaseModel, Field
from typing import Optional, List

class WorkerParams(BaseModel):
    """Worker 직접 호출 파라미터"""
    stock_code: Optional[str] = None
    index_code: Optional[str] = None

class PersonalizationSettings(BaseModel):
    """사용자 맞춤 설정"""
    expertise_level: str = "intermediate"
    preferred_depth: str = "detailed"
    focus_areas: List[str] = []

class RoutingDecision(BaseModel):
    """라우팅 결정 스키마 (Pydantic Structured Output)"""
    query_complexity: str = Field(
        ...,
        description="simple | moderate | expert"
    )
    user_intent: str = Field(
        ...,
        description="quick_info | stock_analysis | trading | portfolio_management | etc"
    )
    stock_names: Optional[List[str]] = Field(
        None,
        description="추출된 종목명"
    )
    agents_to_call: List[str] = Field(
        default_factory=list,
        description="호출할 에이전트: research, strategy, risk, trading, portfolio"
    )
    depth_level: str = Field(
        ...,
        description="brief | detailed | comprehensive"
    )
    personalization: PersonalizationSettings = Field(
        default_factory=PersonalizationSettings
    )
    reasoning: str = Field(
        ...,
        description="라우팅 결정 이유"
    )

    # Tier 1: Worker 직접 호출 (초고속)
    worker_action: Optional[str] = Field(
        None,
        description="stock_price, index_price 등"
    )
    worker_params: Optional[WorkerParams] = None

    # Tier 2: 직접 답변
    direct_answer: Optional[str] = Field(
        None,
        description="간단한 질문은 LLM이 즉시 답변"
    )


async def route_query(
    query: str,
    user_profile: dict,
    conversation_history: List[dict]
) -> RoutingDecision:
    """Router Agent: 3-Tier 라우팅 결정"""

    # Claude Sonnet 4.5 with Structured Output
    llm = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0
    ).with_structured_output(RoutingDecision)

    prompt = f"""
    당신은 HAMA 시스템의 Router Agent입니다.

    다음 우선순위로 쿼리를 처리하세요:

    **우선순위 1 (최고): Worker 직접 호출**
    - 간단한 조회성 쿼리는 worker_action 사용
    - 예: "삼성전자 현재가?" → worker_action="stock_price", worker_params={{"stock_code": "005930"}}
    - 예: "코스피 지수?" → worker_action="index_price", worker_params={{"index_code": "KOSPI"}}

    **우선순위 2: 직접 답변**
    - 일반적인 질문은 direct_answer에 즉시 답변
    - 예: "HAMA가 뭐야?" → direct_answer="..."
    - 예: "포트폴리오 조회 방법?" → direct_answer="..."

    **우선순위 3 (최하): 에이전트 호출**
    - 복잡한 분석/매매는 agents_to_call 사용
    - 예: "삼성전자 분석해줘" → agents_to_call=["research"]
    - 예: "리밸런싱해줘" → agents_to_call=["portfolio"]

    사용자 쿼리: {query}
    사용자 프로파일: {user_profile}
    대화 이력: {conversation_history[-5:]}  # 최근 5개만
    """

    decision = await llm.ainvoke(prompt)
    return decision
```

```python
# api/routes/multi_agent_stream.py

@router.post("/multi-stream")
async def multi_agent_stream(request: ChatRequest):
    """3-Tier 라우팅 기반 SSE 스트리밍"""

    # 1. Router 판단
    routing_decision = await route_query(
        query=request.message,
        user_profile=user_profile,
        conversation_history=conversation_history
    )

    # 2. Tier 1: Worker 직접 호출 (초고속)
    if routing_decision.worker_action:
        if routing_decision.worker_action == "stock_price":
            stock_code = routing_decision.worker_params.stock_code
            price_data = await stock_data_service.get_current_price(stock_code)

            yield {
                "type": "worker_result",
                "data": price_data,
                "elapsed": "0.5초"  # 매우 빠름
            }
            return

    # 3. Tier 2: 직접 답변
    if routing_decision.direct_answer:
        yield {
            "type": "direct_answer",
            "content": routing_decision.direct_answer,
            "elapsed": "1초"
        }
        return

    # 4. Tier 3: 에이전트 호출 (복잡한 분석)
    agents_to_call = routing_decision.agents_to_call

    for agent_name in agents_to_call:
        agent = load_agent(agent_name)

        async for event in agent.astream_events(...):
            yield {
                "type": "agent_event",
                "agent": agent_name,
                "data": event
            }
```

**장점**:
- **속도 최적화**: Tier 1 (0.5초) < Tier 2 (1초) < Tier 3 (10-90초)
- **비용 절감**: 간단한 쿼리는 Worker 직접 호출로 LLM 비용 절감
- **단일 진입점**: Supervisor 제거로 아키텍처 단순화
- **Pydantic 검증**: Structured Output으로 잘못된 라우팅 방지
- **사용자 맞춤**: UserProfile 기반 depth_level 자동 조정

**성능 비교**:

| 쿼리 유형 | 기존 (Supervisor) | Router Agent | 개선 |
|----------|------------------|--------------|------|
| "삼성전자 현재가?" | 60초 (에이전트 호출) | 0.5초 (Worker 직접) | **99% 단축** |
| "HAMA가 뭐야?" | 10초 (LLM 호출) | 1초 (직접 답변) | **90% 단축** |
| "삼성전자 분석해줘" | 60초 | 60초 | 변화 없음 (필요시) |

### 패턴 5: Dynamic Worker Selection (Smart Planner) 패턴 (v1.2 신규)

**개요**: 사용자 쿼리와 프로파일에 따라 필요한 Worker만 동적으로 선택하여 비용과 시간 최적화

**문제**:
- 모든 쿼리에 대해 8개 worker를 실행하면 비용과 시간 낭비
- 간단한 질문("현재가?")에도 복잡한 분석 수행
- 사용자 전문성 수준을 고려하지 않음

**해결 방안: 3-Tier 분석 깊이 시스템**

| 레벨 | Worker 수 | 소요 시간 | 비용 절감 | 적용 사례 |
| --- | --- | --- | --- | --- |
| **Quick** | 1-3개 | 10-20초 | 75-87% | "현재가?", "가격만 확인" |
| **Standard** | 4-5개 | 30-45초 | 38-44% | "분석해줘", "기술적으로 어때?" |
| **Comprehensive** | 7-8개 | 60-90초 | 0% | "매수해도 될까?", "상세 분석" |

**구현 예시:**

```python
# constants/analysis_depth.py

ANALYSIS_DEPTH_LEVELS = {
    "quick": {
        "name": "빠른 분석",
        "required_workers": ["data"],
        "optional_workers": ["technical"],
        "max_workers": 3,
        "estimated_time": "10-20초",
    },
    "standard": {
        "name": "표준 분석",
        "required_workers": ["data", "technical"],
        "optional_workers": ["trading_flow", "information", "bull", "bear"],
        "max_workers": 5,
        "estimated_time": "30-45초",
    },
    "comprehensive": {
        "name": "종합 분석",
        "required_workers": ["data", "technical", "trading_flow", "information"],
        "optional_workers": ["macro", "bull", "bear", "insight"],
        "max_workers": 8,
        "estimated_time": "60-90초",
    }
}

def get_recommended_workers(depth: str, focus_areas: List[str] = None) -> List[str]:
    """분석 깊이와 집중 영역에 따른 추천 worker 리스트"""
    config = ANALYSIS_DEPTH_LEVELS[depth]
    workers = config["required_workers"].copy()

    # Focus areas 우선 추가
    if focus_areas:
        for worker in focus_areas:
            if worker not in workers and len(workers) < config["max_workers"]:
                workers.append(worker)

    # Optional workers 추가 (max_workers까지)
    for worker in config["optional_workers"]:
        if worker not in workers and len(workers) < config["max_workers"]:
            workers.append(worker)

    return workers
```

```python
# research/nodes.py

async def query_intent_classifier_node(state: ResearchState) -> ResearchState:
    """쿼리 의도 분석 및 분석 깊이 결정"""
    query = state.get("query", "")
    user_profile = state.get("user_profile") or {}

    # 1. 키워드 기반 분류
    keyword_depth = classify_depth_by_keywords(query)  # "빠르게" → quick

    # 2. Focus area 추출
    focus_workers = extract_focus_areas(query)  # "기술적" → ["technical"]

    # 3. UserProfile 고려
    preferred_depth = user_profile.get("preferred_depth", "detailed")
    profile_depth_map = {
        "brief": "quick",
        "detailed": "standard",
        "comprehensive": "comprehensive",
    }
    profile_depth = profile_depth_map.get(preferred_depth, "standard")

    # 4. LLM 기반 최종 판단 (복잡한 케이스)
    should_use_llm = (
        keyword_depth == "standard"  # 명확한 키워드 없음
        and any(keyword in query.lower() for keyword in ["할까", "해도 될까", "판단", "결정"])
    )

    if should_use_llm:
        llm = get_llm(temperature=0)
        intent = await llm.ainvoke(f"다음 쿼리의 분석 깊이를 결정하세요: {query}")
        final_depth = intent.get("depth", "standard")
        depth_reason = intent.get("reason", "LLM 판단")
    else:
        final_depth = keyword_depth if keyword_depth != "standard" else profile_depth
        depth_reason = f"키워드: {keyword_depth}, 프로파일: {profile_depth}"

    return {
        "analysis_depth": final_depth,
        "focus_areas": focus_workers,
        "depth_reason": depth_reason,
    }

async def planner_node(state: ResearchState) -> ResearchState:
    """Smart Planner - 분석 깊이에 따라 동적으로 worker 선택"""
    analysis_depth = state.get("analysis_depth", "standard")
    focus_areas = state.get("focus_areas") or []

    # 추천 worker 리스트 생성
    recommended_workers = get_recommended_workers(analysis_depth, focus_areas)
    depth_config = get_depth_config(analysis_depth)

    # LLM에게 제한된 worker 목록 제공
    llm = get_llm(temperature=0)
    prompt = f"""
    사용 가능한 Worker (최대 {depth_config["max_workers"]}개):
    {", ".join(recommended_workers)}

    위 목록에서만 선택하여 작업 계획을 수립하세요.
    """

    plan = await llm.ainvoke(prompt)

    # Worker 검증 및 필터링
    validated_tasks = []
    for task in plan.get("tasks", []):
        if task["worker"] in recommended_workers:
            validated_tasks.append(task)

    return {
        "pending_tasks": validated_tasks,
        "plan": plan,
    }
```

**그래프 구성:**

```python
# research/graph.py

workflow = StateGraph(ResearchState)

# 노드 추가
workflow.add_node("query_intent_classifier", query_intent_classifier_node)
workflow.add_node("planner", planner_node)
workflow.add_node("task_router", task_router_node)
# ... worker nodes

# 플로우
workflow.set_entry_point("query_intent_classifier")
workflow.add_edge("query_intent_classifier", "planner")
workflow.add_edge("planner", "task_router")
# ... worker edges
```

**장점**:
- 비용 절감: Quick 모드에서 최대 87% 절감
- 속도 향상: Quick 모드에서 78% 시간 단축
- 사용자 맞춤: 전문성 수준에 따른 분석 깊이 자동 조절
- LLM 정확도 향상: 제한된 선택지 제공으로 잘못된 worker 선택 방지

**State 스키마:**

```python
class ResearchState(TypedDict, total=False):
    # 동적 Worker 선택 필드
    analysis_depth: Optional[str]  # "quick" | "standard" | "comprehensive"
    focus_areas: Optional[List[str]]  # ["technical", "trading_flow"]
    depth_reason: Optional[str]  # 선택 이유
    user_profile: Optional[dict]  # UserProfile 정보
```

**UserProfile 연동:**

```python
# api/routes/chat.py

@router.post("/")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # UserProfile 조회
    user_profile_service = UserProfileService()
    user_profile = user_profile_service.get_user_profile(user_id, db)

    # GraphState에 포함
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_profile": user_profile,  # Research Agent로 자동 전달
        # ... other fields
    }

    result = await app.ainvoke(initial_state)
```

**기대 효과:**

| 쿼리 유형 | 기존 (8 workers) | 최적화 후 | 절감율 |
| --- | --- | --- | --- |
| "삼성전자 현재가?" | 60-90초, 8 LLM calls | 10-20초, 2 LLM calls | -75% 비용, -78% 시간 |
| "삼성전자 분석해줘" | 60-90초, 8 LLM calls | 30-45초, 5 LLM calls | -38% 비용, -44% 시간 |
| "삼성전자 매수해도 될까?" | 60-90초, 8 LLM calls | 60-90초, 8 LLM calls | 변화 없음 (필요시) |

## 실전 예시

### 매매 실행 워크플로우 (노드 분리 + 멱등성)

```python
def prepare_trade_node(state: GraphState) -> GraphState:
    """1단계: 거래 준비"""
    order_id = db.create_order({
        "stock": state["stock_code"],
        "quantity": state["quantity"],
        "status": "pending"
    })
    return {**state, "order_id": order_id}

def approval_node(state: GraphState) -> GraphState:
    """2단계: HITL 승인"""
    order = db.get_order(state["order_id"])

    approval = interrupt({
        "type": "trade_approval",
        "order": order
    })

    db.update(state["order_id"], {
        "approved": True,
        "approved_by": approval["user_id"]
    })

    return {**state, "approved": True}

def execute_trade_node(state: GraphState) -> GraphState:
    """3단계: 거래 실행 (멱등성)"""
    order = db.get_order(state["order_id"])

    # 멱등성 체크
    if order["status"] == "executed":
        return {**state, "result": order["result"]}

    # 한국투자증권 API 호출
    with db.transaction():
        result = kis_api.execute_trade(
            stock=state["stock_code"],
            quantity=state["quantity"]
        )

        db.update(state["order_id"], {
            "status": "executed",
            "result": result
        })

    return {**state, "result": result}

# 그래프 구성
workflow.add_edge("prepare_trade", "approval")
workflow.add_edge("approval", "execute_trade")
```

### 리밸런싱 노드 (상태 플래그 패턴)

```python
def rebalancing_node(state: GraphState) -> GraphState:
    """리밸런싱 - 상태 플래그 패턴"""

    # 1단계: 목표 포트폴리오 계산
    if not state.get("rebalance_calculated"):
        target = calculate_rebalance(
            current=state["current_portfolio"],
            target=state["target_allocation"]
        )
        state["target_portfolio"] = target
        state["rebalance_calculated"] = True

    # 2단계: 승인 요청
    if not state.get("rebalance_approved"):
        approval = interrupt({
            "type": "rebalancing",
            "changes": state["target_portfolio"]["changes"]
        })

        if approval["decision"] == "modify":
            state["target_portfolio"] = approval["modified"]

        state["rebalance_approved"] = True

    # 3단계: 실행
    if not state.get("rebalance_executed"):
        trades = []
        for change in state["target_portfolio"]["changes"]:
            # 멱등성 보장
            trade_id = f"{state['portfolio_id']}_{change['stock']}"
            if not db.get_trade(trade_id):
                result = execute_trade(change)
                trades.append(result)

        state["rebalance_executed"] = True
        state["trades"] = trades

    return state
```

## 디버깅 및 모니터링

### 정적 Interrupt (디버깅용)

```python
# 특정 노드 전/후에 중단
app = workflow.compile(
    interrupt_before=["risky_node"],  # 이 노드 실행 전 중단
    interrupt_after=["data_collection"]  # 이 노드 실행 후 중단
)
```

### 상태 추적

```python
# 실행 히스토리 조회
history = await app.aget_state_history(config)
for state in history:
    print(f"Step: {state.values}, Next: {state.next}")
```

### 스트리밍 응답

```python
async for event in app.astream_events(initial_state, config):
    if event["event"] == "on_chain_stream":
        yield event["data"]  # 실시간 진행 상황
```

## 주의사항 체크리스트

### ✅ Interrupt 사용 시 반드시:
- [ ] 부작용 코드가 interrupt 전에 있는지 확인
- [ ] 있다면 → 노드 분리 또는 상태 플래그 적용
- [ ] 멱등성 체크 로직 추가 (DB 조회)
- [ ] 트랜잭션으로 동시성 제어

### ✅ State 설계 시:
- [ ] `messages` 필드 포함 (LangGraph 표준)
- [ ] 진행 상태 플래그 명명: `{action}_prepared`, `{action}_approved`, `{action}_executed`
- [ ] 서브그래프는 별도 State 정의

### ✅ 노드 작성 시:
- [ ] 순수 함수 원칙 (같은 입력 → 같은 출력)
- [ ] 부작용 최소화
- [ ] 재실행 안전성 검증

### ✅ 테스트 시:
- [ ] Interrupt 전후 상태 확인
- [ ] 재개 후 중복 실행 테스트
- [ ] 동시성 테스트 (같은 order_id 처리)

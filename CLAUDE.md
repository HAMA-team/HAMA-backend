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

### LangGraph Supervisor 패턴 기반 멀티 에이전트 시스템

**현재 구현 상태 (2025-10-06):**

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

[Legacy - 마이그레이션 중]
Monitoring (⏸️ Phase 2)
Personalization (🔍 검토 중)
DataCollection (❌ 제거 완료 - Research로 통합)
```

**에이전트 실행 방식:**
- **에이전트 간**: 의존성에 따라 **순차 실행** (Research → Strategy → Risk)
- **에이전트 내부 노드**: LangGraph로 **병렬 실행 가능** (예: Bull/Bear 분석)
- **Supervisor**: LLM이 의도를 분석하여 필요한 에이전트만 선택

### 자동화 레벨 시스템

- **Level 1 (Pilot)**: AI가 거의 모든 것을 처리, 월 1회 확인
- **Level 2 (Copilot) ⭐**: AI가 제안, 큰 결정만 승인 (기본값)
- **Level 3 (Advisor)**: AI는 정보만 제공, 사용자가 결정

## 개발 원칙

### 1. Phase별 구현 전략

**Phase 1 (MVP)**: 실제 데이터 연동 완료 ✅ (80% 완성)
- ✅ LangGraph Supervisor 패턴 아키텍처
- ✅ 6개 서브그래프 에이전트 구현
- ✅ 실제 데이터 연동 (FinanceDataReader, DART API)
- ✅ Redis 캐싱 시스템
- ✅ HITL API (`/chat`, `/approve`)
- ✅ E2E 테스트 (6개 통과)
- 🔄 Legacy Agent 마이그레이션 (1/3 완료)

**Phase 2**: 실제 매매 연동 (예정)
- 한국투자증권 API (실시간 시세)
- 실제 매매 주문 실행
- WebSocket 실시간 알림
- 뉴스 크롤링

**Phase 3**: 확장 기능
- 해외 주식 지원
- 모바일 앱
- 자동 리밸런싱 스케줄러

### 2. HITL 구현 필수

**구현 완료 (2025-10-06):**
- ✅ Trading Agent: `interrupt()` 기반 HITL
- ✅ API 엔드포인트: `POST /chat/approve`
- ✅ 자동화 레벨별 Interrupt 조건

**승인이 필요한 작업:**
- 매매 실행
- 포트폴리오 구성/변경
- 리밸런싱
- 고위험 거래

**플로우:**
```
1. 사용자 매매 요청 → Trading Agent
2. approval_trade 노드에서 interrupt() 호출
3. API가 requires_approval: true 반환
4. 사용자 승인 → Command(resume) 전달
5. 거래 실행
```

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

### 6. LangGraph 기반 개발 가이드

HAMA 시스템은 **LangGraph 네이티브 아키텍처**를 사용합니다. 모든 에이전트는 LangGraph의 노드 또는 서브그래프로 구현됩니다.

#### 6.1 핵심 원칙

**State-First 설계:**
- 모든 상태는 `GraphState` (TypedDict)로 정의
- 노드 함수는 state를 받아 업데이트를 반환
- 순수 함수 원칙: 입력이 같으면 출력도 같아야 함

**Interrupt 재실행 메커니즘:**
- ⚠️ **중요:** `interrupt()` 호출 후 재개 시, 해당 노드가 **처음부터 다시 실행**됨
- DB 업데이트, API 호출 등 부작용(side effect)이 중복 실행될 위험
- 반드시 아래 안전 패턴 중 하나를 적용

**부작용 격리:**
- 노드는 가능한 한 순수 함수로 작성
- DB 업데이트, API 호출은 특별히 관리

#### 6.2 Interrupt 재실행 안전 패턴 (필수)

**패턴 1: 상태 플래그 패턴** (권장 ⭐)

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

**패턴 2: 노드 분리 패턴** (가장 안전 🔒)

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

**패턴 3: 멱등성 설계** (권장 ⭐⭐)

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

**패턴 선택 기준:**

| 상황 | 권장 패턴 | 이유 |
|------|----------|------|
| 매매 실행 | 노드 분리 | 부작용 완전 격리 |
| 리밸런싱 | 상태 플래그 | 진행도 추적 필요 |
| 데이터 수집 | 멱등성 설계 | 중복 허용 가능 |
| 리스크 체크 | 순수 함수 | 부작용 없음 |

#### 6.3 HITL (Human-in-the-Loop) 구현

**자동화 레벨별 Interrupt 설정:**

```python
from langgraph.checkpoint.sqlite import SqliteSaver

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

    # Checkpointer 설정
    checkpointer = SqliteSaver.from_conn_string("data/checkpoints.db")

    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes
    )

    return app
```

**API 엔드포인트 패턴:**

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

**동적 Interrupt (리스크 기반):**

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

#### 6.4 State 관리 패턴

**전체 GraphState:**

```python
from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class GraphState(TypedDict):
    """전체 그래프 공유 상태"""
    # LangGraph 표준 패턴
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

**서브그래프 State (Research Agent 예시):**

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

#### 6.5 서브그래프 활용 패턴

**복잡한 에이전트는 서브그래프로:**

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

#### 6.6 실전 예시

**매매 실행 워크플로우 (노드 분리 + 멱등성):**

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

**리밸런싱 노드 (상태 플래그 패턴):**

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

#### 6.7 디버깅 및 모니터링

**정적 Interrupt (디버깅용):**

```python
# 특정 노드 전/후에 중단
app = workflow.compile(
    interrupt_before=["risky_node"],  # 이 노드 실행 전 중단
    interrupt_after=["data_collection"]  # 이 노드 실행 후 중단
)
```

**상태 추적:**

```python
# 실행 히스토리 조회
history = await app.aget_state_history(config)
for state in history:
    print(f"Step: {state.values}, Next: {state.next}")
```

**스트리밍 응답:**

```python
async for event in app.astream_events(initial_state, config):
    if event["event"] == "on_chain_stream":
        yield event["data"]  # 실시간 진행 상황
```

#### 6.8 주의사항 체크리스트

**✅ Interrupt 사용 시 반드시:**
- [ ] 부작용 코드가 interrupt 전에 있는지 확인
- [ ] 있다면 → 노드 분리 또는 상태 플래그 적용
- [ ] 멱등성 체크 로직 추가 (DB 조회)
- [ ] 트랜잭션으로 동시성 제어

**✅ State 설계 시:**
- [ ] `messages` 필드 포함 (LangGraph 표준)
- [ ] 진행 상태 플래그 명명: `{action}_prepared`, `{action}_approved`, `{action}_executed`
- [ ] 서브그래프는 별도 State 정의

**✅ 노드 작성 시:**
- [ ] 순수 함수 원칙 (같은 입력 → 같은 출력)
- [ ] 부작용 최소화
- [ ] 재실행 안전성 검증

**✅ 테스트 시:**
- [ ] Interrupt 전후 상태 확인
- [ ] 재개 후 중복 실행 테스트
- [ ] 동시성 테스트 (같은 order_id 처리)

## 데이터 소스

**현재 연동 완료 (2025-10-06):**
- ✅ **FinanceDataReader**: 주가, 거래량, 종목 리스트
- ✅ **DART API**: 재무제표, 공시, 기업 정보
- ✅ **Redis**: 캐싱 (TTL 60초)

**Phase 2 예정:**
- ⏸️ **한국투자증권 API**: 실시간 시세, 차트, 호가
- ⏸️ **네이버 금융**: 뉴스 크롤링
- ⏸️ **BOK API**: 금리, 거시경제 지표

**데이터 플로우:**
```
사용자 요청 → Research Agent
              ↓
    stock_data_service.get_stock_price()  (FinanceDataReader)
              ↓
    dart_service.search_corp_code()  (종목코드 → 고유번호)
              ↓
    dart_service.get_financial_statement()  (재무제표)
              ↓
    dart_service.get_company_info()  (기업 정보)
              ↓
    Redis 캐싱 (중복 요청 방지)
```

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
- 각 작업을 시작할 때에는 알맞은 브랜치에서 작업중인지 확인하고, 만약 그렇지 않다면 기존 작업 상황을 커밋한 뒤에 알맞은 브랜치로 분기하여 작업을 진행해야 합니다

## 테스트 및 API 키 사용 원칙

### ❌ 절대 하지 말 것

1. **테스트에서 API 키가 없다고 skip 처리하지 말 것**
   - `@pytest.mark.skipif(no api key)` 같은 패턴 절대 금지
   - API 키가 필요한 테스트는 실패하도록 두어야 함

2. **LLM 호출 실패 시 mock 데이터로 대체하지 말 것**
   - "API 키 없으면 mock 응답" 같은 fallback 로직 금지
   - 실패는 실패로 명확히 드러나야 함

3. **테스트 환경에서 가짜 API 키 사용 금지**
   - `os.environ["OPENAI_API_KEY"] = "test-key-not-used"` 같은 코드 금지
   - 실제 키가 없으면 테스트가 실패해야 정상

### ✅ 올바른 방법

1. **모든 환경에서 실제 API 키 사용**
   - 테스트 환경에서도 `.env` 파일의 실제 키 사용
   - `src.config.settings.settings.OPENAI_API_KEY` 사용

2. **실패는 명확하게**
   - API 키가 없으면 → 테스트 실패
   - LLM 호출 실패하면 → 에러 발생
   - 네트워크 문제 있으면 → 테스트 실패

3. **환경 변수 의존성 명시**
   - README나 문서에 필수 환경 변수 명시
   - 개발자가 직접 `.env` 파일 설정하도록 안내

### 예시

**❌ 잘못된 예:**
```python
# 테스트 skip
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No API key")
def test_llm():
    ...

# Mock fallback
try:
    response = llm.invoke(query)
except:
    return {"answer": "mock response"}  # ❌ 절대 안 됨
```

**✅ 올바른 예:**
```python
# API 키는 settings에서 가져오기
from src.config.settings import settings

def call_llm(query: str):
    llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY)  # 실제 키
    response = llm.invoke(query)  # 실패하면 에러 발생
    return response

# 테스트도 실제 키 사용
def test_llm():
    result = call_llm("test")
    assert result is not None  # 키 없으면 여기서 실패
```

Always use context7 when I need code generation, setup or configuration steps, or
library/API documentation. This means you should automatically use the Context7 MCP
tools to resolve library id and get library docs without me having to explicitly ask.

## 테스트 작성 가이드라인

### 테스트 파일 구조 원칙

```
tests/
├── test_services/       # 서비스 레이어 단위 테스트
├── test_agents/         # Agent 레이어 테스트
├── test_api/            # API 엔드포인트 테스트 (선택)
└── test_*.py            # 통합/특수 테스트 (최소화)
```

### 새 테스트 작성 시 의사결정 프로세스

**1단계: 테스트 대상 파악**
- 서비스 로직 → `tests/test_services/`
- Agent 로직 → `tests/test_agents/`
- API 엔드포인트 → `tests/test_api/` 또는 루트
- 통합/E2E → 루트 (`test_integration.py` 등)

**2단계: 기존 파일 vs 새 파일 결정**

**기존 파일에 추가하는 경우 (우선):**
- ✅ 같은 클래스/모듈의 다른 메서드 테스트
- ✅ 기존 테스트와 관련된 엣지 케이스
- ✅ 같은 카테고리의 테스트 (예: DART service의 다른 API)

**새 파일을 만드는 경우:**
- ✅ 완전히 새로운 서비스/모듈
- ✅ 독립적인 기능 영역 (예: KIS vs DART)
- ✅ 기존 파일이 너무 커짐 (200줄 초과 시 고려)

**3단계: 파일명 규칙**

```python
# 서비스 테스트
test_services/test_{service_name}_service.py

# Agent 테스트
test_agents/test_{agent_name}_agent.py

# 통합 테스트
test_{feature}_integration.py
```

### 의사결정 예시

**예시 1: DART 서비스에 새 API 메서드 추가**
```
상황: dart_service.py에 get_disclosure() 메서드 추가
결정: ✅ test_services/test_dart_service.py에 test_get_disclosure() 추가
이유: 같은 서비스의 다른 메서드, 기존 파일에 통합
```

**예시 2: 완전히 새로운 뉴스 서비스**
```
상황: news_service.py 신규 생성
결정: ✅ test_services/test_news_service.py 신규 생성
이유: 독립적인 새 서비스, 별도 파일 필요
```

**예시 3: Research Agent에 새 노드 추가**
```
상황: research/nodes.py에 sentiment_analysis_node 추가
결정: ✅ test_agents/test_research_agent.py에 test_sentiment_analysis_node() 추가
이유: 같은 Agent 내 노드, 기존 파일에 통합
```

**예시 4: 새로운 Agent 추가**
```
상황: monitoring_agent/ 디렉토리 신규 생성
결정: ✅ test_agents/test_monitoring_agent.py 신규 생성
이유: 완전히 새로운 Agent, 별도 파일 필요
```

### 테스트 작성 체크리스트

**테스트 작성 전:**
- [ ] 테스트 대상이 services인지 agents인지 API인지 확인
- [ ] 해당 카테고리에 기존 테스트 파일이 있는지 검색
- [ ] 기존 파일에 추가할 수 있는지 검토 (라인 수, 관련성)
- [ ] 새 파일이 필요하다면 명확한 이유가 있는지 확인

**테스트 작성 후:**
- [ ] `if __name__ == "__main__":` 블록 추가 (독립 실행 가능)
- [ ] pytest와 직접 실행 모두 테스트
- [ ] 테스트 문서화 (docstring)
- [ ] tests/README.md 업데이트 (필요시)

### 안티패턴 (피해야 할 것)

**❌ 임시 테스트 파일 남발**
```
test_feature_temp.py        # 작업 후 정리 안 함
test_feature_v2.py          # 버전별로 파일 생성
test_feature_backup.py      # 백업 파일 생성
```

**❌ 과도한 파일 분리**
```
test_dart_service_search.py       # 메서드 하나당 파일
test_dart_service_financial.py    # → 하나로 통합해야 함
test_dart_service_company.py
```

**❌ 애매한 파일명**
```
test_improvements.py        # 무엇을 개선했는지 불명확
test_temp.py                # 임시 파일 명시
test_new_feature.py         # 기능명이 구체적이지 않음
```

### 베스트 프랙티스

**✅ 명확한 구조**
```
tests/
├── test_services/
│   ├── test_dart_service.py      # DART 관련 모든 테스트
│   ├── test_kis_service.py       # KIS 관련 모든 테스트
│   └── test_stock_data_service.py
├── test_agents/
│   ├── test_research_agent.py    # Research Agent 모든 노드
│   └── test_strategy_agent.py    # Strategy Agent 모든 노드
└── test_integration.py            # 전체 통합 테스트
```

**✅ 테스트 클래스로 그룹화**
```python
# test_services/test_dart_service.py
class TestDARTService:
    """DART Service 전체 테스트"""

    async def test_search_corp_code(self):
        """종목코드 검색"""
        pass

    async def test_get_financial_statement(self):
        """재무제표 조회"""
        pass

    async def test_cache_mechanism(self):
        """캐싱 검증"""
        pass
```

**✅ 독립 실행 가능**
```python
if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        tester = TestDARTService()
        await tester.test_search_corp_code()
        await tester.test_get_financial_statement()

    asyncio.run(main())
```

### 요약

1. **기존 파일 우선**: 같은 카테고리면 기존 파일에 추가
2. **새 파일 최소화**: 독립적인 모듈/서비스만 새 파일
3. **임시 파일 금지**: 작업 완료 후 반드시 정리
4. **명확한 구조**: services/agents/api로 분류
5. **문서화 필수**: 변경 시 README 업데이트
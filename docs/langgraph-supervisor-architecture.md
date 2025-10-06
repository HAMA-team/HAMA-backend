# HAMA LangGraph Supervisor 아키텍처

**작성일**: 2025-10-05
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
| `research_agent` | 종목 심층 분석 | ✅ | - |
| `strategy_agent` | 투자 전략 수립 | ✅ | - |
| `risk_agent` | 리스크 평가 | ✅ | 조건부 |
| `portfolio_agent` | 포트폴리오 관리 | ✅ | 조건부 |
| `trading_agent` | 매매 실행 | ✅ | ✅ (L2+) |
| `monitoring_agent` | 시장 모니터링 | 🚧 TODO | - |
| `general_agent` | 일반 질의응답 | 🚧 TODO | - |

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
def build_graph(automation_level: int = 2):
    """최종 그래프 빌드"""
    supervisor = build_supervisor(automation_level)

    return supervisor.compile(
        checkpointer=MemorySaver()
    )


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
market_outlook → sector_strategy → asset_allocation → blueprint
```

**함수 시그니처:**
```python
async def market_outlook_node(state: StrategyState) -> dict:
    """
    시장 사이클 분석 (LLM)

    Returns:
        dict: market_outlook (cycle, indicators)
    """

async def sector_strategy_node(state: StrategyState) -> dict:
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
collect_portfolio → concentration_check → market_risk → assess_risk
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

async def assess_risk_node(state: RiskState) -> dict:
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
prepare_trade → approval_trade (HITL) → execute_trade
```

**함수 시그니처:**
```python
def prepare_trade_node(state: TradingState) -> dict:
    """
    거래 준비 (부작용: DB 주문 생성)

    Returns:
        dict: trade_order_id, trade_prepared=True
    """

def approval_trade_node(state: TradingState) -> dict:
    """
    HITL 승인 (interrupt 발생)

    Returns:
        dict: trade_approved=True

    Raises:
        interrupt: 사용자 승인 대기
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

**TODO: 신규 생성 필요**

**역할:**
- 투자 용어 설명
- 일반 시장 질문 응답
- 투자 전략 교육
- PER, PBR 등 기본 개념 설명

**함수 시그니처:**
```python
async def answer_general_question_node(state: GeneralState) -> dict:
    """
    일반 질문 응답 (LLM + RAG)

    Args:
        state: GeneralState (query 포함)

    Returns:
        dict: answer, sources
    """
```

---

## 🔄 HITL (Human-in-the-Loop) 패턴

### Interrupt 메커니즘

**LangGraph의 `interrupt()` 함수:**
```python
from langgraph.types import interrupt

def approval_node(state):
    # Interrupt 발생 - 사용자 승인 대기
    approval = interrupt({
        "type": "trade_approval",
        "order_id": state["order_id"],
        "message": "매매를 승인하시겠습니까?"
    })

    # 재개 후 승인 결과 처리
    return {"approved": True}
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

```python
class GraphState(TypedDict):
    """Master Graph 공유 State"""

    # LangGraph 표준
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 사용자 컨텍스트
    user_id: str
    conversation_id: str
    automation_level: int  # 전역으로 전달

    # 에이전트 결과
    agent_results: Annotated[Dict[str, Any], operator.or_]
```

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

## 📦 다음 단계

### Phase 1: 서브그래프 전환
- [ ] Portfolio Agent → 서브그래프
- [ ] Monitoring Agent → 서브그래프
- [ ] General Agent → 서브그래프 (신규)

### Phase 2: 고도화
- [ ] LLM 기반 Stock Code 추출 (NER)
- [ ] AsyncSqliteSaver로 Checkpointer 전환
- [ ] 실제 API 연동 (한국투자증권)
- [ ] 성능 최적화 (캐싱, 병렬화)

### Phase 3: 프로덕션
- [ ] 로깅 및 모니터링
- [ ] 에러 핸들링 강화
- [ ] 통합 테스트 작성
- [ ] API 문서화

---

**작성자**: HAMA 개발팀
**최종 업데이트**: 2025-10-05
**참고**: [LangGraph Supervisor 공식 문서](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)

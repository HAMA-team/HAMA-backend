"""
Langgraph Supervisor 패턴 기반 마스터 에이전트

Master Agent의 역할 (순수 조율자):
1. 사용자 질의를 LLM으로 분석
2. 적절한 에이전트들 선택 (LLM 기반 동적 라우팅)
3. 에이전트 실행 (병렬 가능)
4. 결과 통합

중요: Master는 비즈니스 로직을 수행하지 않음!
      모든 실제 작업은 서브그래프(에이전트)가 수행
      HITL도 각 서브그래프 내부에서 처리
"""
import asyncio
import logging
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
try:
    from langgraph.checkpoints.memory import MemorySaver
except ImportError:  # pragma: no cover - 호환성 유지
    from langgraph.checkpoint.memory import MemorySaver  # type: ignore
from langgraph_supervisor import create_supervisor

from src.config.settings import settings
from src.schemas.graph_state import GraphState
from src.agents.master.routing_nodes import (
    routing_node,
    worker_dispatch_node,
    direct_answer_node,
    clarification_node,
    determine_routing_path,
)

logger = logging.getLogger(__name__)


# ==================== Supervisor 구성 ====================

@lru_cache
def _load_agent(module_path: str, attribute: str):
    """
    에이전트 모듈을 지연 로딩하여 초기 import 순환/경로 문제를 회피한다.
    """
    module = import_module(module_path)
    return getattr(module, attribute)


def build_supervisor(automation_level: int = 2, llm: Optional[BaseChatModel] = None):
    """
    Langgraph Supervisor 패턴 기반 Master Agent 정의를 생성합니다.
    """
    if llm is None:
        # 라우팅에는 ROUTER_MODEL 설정 사용 (종목명 인식 개선을 위해 강력한 모델)
        from src.utils.llm_factory import _build_llm, _loop_token

        provider = settings.ROUTER_MODEL_PROVIDER
        model_name = settings.ROUTER_MODEL
        loop_token = _loop_token()

        logger.info(
            "🤖 [Supervisor] 라우팅 모델 초기화: provider=%s, model=%s",
            provider,
            model_name,
        )

        llm = _build_llm(
            provider=provider,
            model_name=model_name,
            temperature=0.0,
            max_tokens=settings.MAX_TOKENS,
            loop_token=loop_token,
        )

    supervisor_prompt = f"""<context>
## 역할
당신은 투자 에이전트 팀을 조율하는 Supervisor입니다. 사용자 요청을 분석하여 적절한 에이전트를 선택하고 실행을 조율합니다.

## 에이전트 구조 (서브에이전트 포함)

**research_agent** (분석 깊이: Quick/Standard/Comprehensive)
- 7 Workers: Data, Bull/Bear Analyst, Technical Analyst, Trading Flow, Information, Macro, Insight
- 역할: 종목 데이터 수집, 기술적/재무 분석, 뉴스 수집, 시장 전망

**strategy_agent**
- 3 Specialists: Buy Specialist (1-10점 평가), Sell Specialist (매도 판단), Risk/Reward Calculator (손절/목표가)
- 역할: 투자 의사결정, 매수/매도 평가, 손익 계산

**portfolio_agent**
- 3 Nodes: Market Condition, Optimize Allocation, Validate Constraints
- 역할: 포트폴리오 구성/최적화, 리밸런싱, 제약 검증

**risk_agent** (단일 노드)
- 역할: VaR, 변동성, 집중도 리스크, 섹터 노출도 측정

**trading_agent** (단일 노드 + HITL)
- 역할: 매매 주문 생성 및 실행
- ⚠️ automation_level {automation_level} - 모든 매매는 승인 필요

**monitoring_agent** (배경 전용 - 챗봇 호출 불가)
- 역할: 포트폴리오 종목 뉴스 수집/분석 (정기/트리거 기반, 사용자 직접 호출 불가)
</context>

<instructions>
## 라우팅 원칙

1. **직접 답변 우선**: 투자 용어 설명, 시스템 사용법 → 에이전트 호출 없이 직접 답변
2. **최소 에이전트**: 필요한 에이전트만 호출 (불필요한 호출 금지)
3. **서브에이전트 인식**: 질문 의도에 맞는 Worker/Specialist 조합 고려
4. **병렬 vs 순차**:
   - 병렬: 독립적인 에이전트 (예: 복수 종목 비교)
   - 순차: 의존성 있음 (예: 분석 → 매매)
5. **분석 깊이 선택**:
   - Quick (1-3 workers): 단순 조회 (현재가, PER)
   - Standard (4-5 workers): 세부 분석 (기술적, 재무)
   - Comprehensive (7 workers): 종합 분석 + 투자 의사결정

## 핵심 시나리오 (10가지)

### 1. 투자 용어/상식 → 직접 답변
예: "PER이 뭐야?", "증시 몇 시에 열어?"
→ 에이전트 호출 없음

### 2. 단순 조회 → research_agent (Quick)
예: "삼성전자 현재가?", "SK하이닉스 PER?"
→ transfer_to_research_agent (Data Worker만)

### 3. 기술적 분석 → research_agent (Standard)
예: "삼성전자 차트 분석", "RSI 지표 어때?"
→ transfer_to_research_agent (Data + Technical Analyst)

### 4. 재무 분석 → research + strategy (Standard)
예: "삼성전자 재무제표 분석", "수익성 평가"
→ transfer_to_research_agent (Data), transfer_to_strategy_agent (Buy Specialist 밸류에이션)

### 5. 종합 분석 + 투자 판단 → research + strategy + risk (Comprehensive)
예: "삼성전자 분석해줘", "투자 어때?"
→ transfer_to_research_agent (7 workers), transfer_to_strategy_agent (Buy + Risk/Reward), transfer_to_risk_agent

### 6. 2종목 비교 → research + strategy (병렬)
예: "삼성전자 vs SK하이닉스"
→ transfer_to_research_agent (각 종목 병렬), transfer_to_strategy_agent (비교 평가)

### 7. 시장 전망 → research + strategy
예: "코스피 전망?", "어떤 섹터가 유망해?"
→ transfer_to_research_agent (Macro + Bull/Bear), transfer_to_strategy_agent

### 8. 포트폴리오 진단 → portfolio + risk
예: "내 포트폴리오 평가", "리스크 체크"
→ transfer_to_portfolio_agent (Market Condition + Optimize), transfer_to_risk_agent

### 9. 리밸런싱 → research + strategy + portfolio + risk + HITL
예: "포트폴리오 리밸런싱", "비중 조정"
→ transfer_to_research_agent (Macro), transfer_to_strategy_agent (종목 재평가), transfer_to_portfolio_agent (최적화), transfer_to_risk_agent
→ HITL 승인 필요 (automation_level {automation_level})

### 10. 매매 실행 → trading + HITL
예: "삼성전자 10주 매수", "SK하이닉스 매도"
→ transfer_to_trading_agent
→ HITL 승인 필수

## 주의사항
- monitoring_agent는 배경 작업 전용 (사용자 직접 호출 금지)
- 복합 명령 (예: "분석 후 매수")은 순차 실행 (분석 → HITL → 매매)
- 애매한 요청은 명확화 질문 생성
</instructions>

<examples>
### 예시 1: 직접 답변
사용자: "PER이 뭐야?"
→ 에이전트 호출 없이 직접 답변: "PER(주가수익비율)은 주가를 주당순이익(EPS)로 나눈 값으로..."

### 예시 2: 종합 분석 (Comprehensive)
사용자: "삼성전자 분석해줘"
→ transfer_to_research_agent (Comprehensive, 7 workers)
→ transfer_to_strategy_agent (Buy Specialist + Risk/Reward Calculator)
→ transfer_to_risk_agent (포트폴리오 영향)

### 예시 3: 리밸런싱 (순차 + HITL)
사용자: "포트폴리오 리밸런싱해줘"
→ transfer_to_research_agent (Macro Worker)
→ transfer_to_strategy_agent (종목 재평가)
→ transfer_to_portfolio_agent (3 nodes 순차: Market Condition → Optimize → Validate)
→ transfer_to_risk_agent (리밸런싱 전후 비교)
→ HITL 승인 대기
</examples>

사용자 요청을 분석하여 위 원칙에 따라 라우팅하세요.
"""

    supervisor_graph = create_supervisor(
        agents=[
            _load_agent("src.agents.research", "research_agent"),
            _load_agent("src.agents.strategy", "strategy_agent"),
            _load_agent("src.agents.risk", "risk_agent"),
            _load_agent("src.agents.trading", "trading_agent"),
            _load_agent("src.agents.portfolio", "portfolio_agent"),
            _load_agent("src.agents.monitoring", "monitoring_subgraph"),
        ],
        model=llm,
        parallel_tool_calls=True,
        prompt=supervisor_prompt,
        state_schema=GraphState,  # MasterState로 에이전트 간 데이터 공유
    )

    supervisor_app = supervisor_graph.compile(name="supervisor_agent")

    logger.info("✅ [Supervisor] 생성 완료 (automation_level=%s)", automation_level)

    return supervisor_app


def build_state_graph(automation_level: int = 2):
    """
    Routing → Worker/Direct 처리 → Supervisor 실행을 포함한 Langgraph 정의를 생성합니다.
    """
    supervisor_graph = build_supervisor(automation_level=automation_level, llm=None)

    workflow = StateGraph(GraphState)
    workflow.add_node("routing", routing_node)
    workflow.add_node("worker_dispatch", worker_dispatch_node)
    workflow.add_node("direct_answer", direct_answer_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("supervisor", supervisor_graph)

    workflow.set_entry_point("routing")
    workflow.add_conditional_edges(
        "routing",
        determine_routing_path,
        {
            "worker_dispatch": "worker_dispatch",
            "direct_answer": "direct_answer",
            "clarification": "clarification",
            "supervisor": "supervisor",
        },
    )

    workflow.add_edge("worker_dispatch", END)
    workflow.add_edge("direct_answer", END)
    workflow.add_edge("clarification", END)
    workflow.add_edge("supervisor", END)

    return workflow


def _resolve_backend_key(backend: Optional[str] = None) -> str:
    if backend:
        return backend.lower()
    return getattr(settings, "GRAPH_CHECKPOINT_BACKEND", "memory").lower()


def _create_checkpointer(backend_key: str):
    """
    현재 환경에서는 Redis/Postgres 체크포인터를 사용하지 않고
    항상 인메모리 Saver를 반환한다.
    """
    key = backend_key.lower()

    if key != "memory":
        logger.warning(
            "Graph checkpoint backend '%s'는 지원되지 않아 MemorySaver로 대체합니다.",
            backend_key,
        )

    return MemorySaver()


def _loop_token() -> str:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return "sync"
    return f"loop-{id(loop)}"


@lru_cache(maxsize=16)
def get_compiled_graph(automation_level: int, backend_key: str, loop_token: str):
    """
    automation_level, backend_key 조합으로 컴파일된 그래프를 캐싱합니다.
    """
    state_graph = build_state_graph(automation_level=automation_level)
    checkpointer = _create_checkpointer(backend_key)
    app = state_graph.compile(checkpointer=checkpointer)

    logger.info(
        "🔧 [Graph] 컴파일 완료 (automation_level=%s, backend=%s, loop=%s)",
        automation_level,
        backend_key,
        loop_token,
    )

    return app


# ==================== Main Interface ====================

def build_graph(
    automation_level: int = 2,
    *,
    backend_key: Optional[str] = None,
):
    """
    Backwards compatible helper that mirrors the legacy API expected by
    existing routes. Returns a compiled Langgraph application.
    """
    resolved_backend = _resolve_backend_key(backend_key)
    loop_token = _loop_token()
    return get_compiled_graph(
        automation_level=automation_level,
        backend_key=resolved_backend,
        loop_token=loop_token,
    )


async def run_graph(
    query: str,
    automation_level: int = 2,
    request_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    backend_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Langgraph Supervisor 그래프 실행 함수
    """
    import uuid

    if not request_id:
        request_id = str(uuid.uuid4())

    if not thread_id:
        thread_id = request_id

    resolved_backend = _resolve_backend_key(backend_key)
    loop_token = _loop_token()
    app = get_compiled_graph(
        automation_level=automation_level,
        backend_key=resolved_backend,
        loop_token=loop_token,
    )

    config = {
        "configurable": {
            "thread_id": thread_id,
            "request_id": request_id,
        },
        "recursion_limit": 50,  # Supervisor 패턴을 위한 recursion_limit 증가
    }

    configured_app = app.with_config(config)

    initial_state = {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "request_id": request_id,
        "agents_to_call": [],
        "agents_called": [],
        "agent_results": {},
        "routing_decision": None,
        "personalization": None,
        "worker_action": None,
        "worker_params": None,
        "direct_answer": None,
        "clarification_needed": False,
        "clarification_message": None,
        "conversation_history": [],
    }

    logger.info("🚀 [Graph] 실행 시작: %s...", query[:50])

    result = await configured_app.ainvoke(initial_state)

    logger.info("✅ [Graph] 실행 완료 (request_id=%s)", request_id)

    final_message = result["messages"][-1]

    return {
        "message": final_message.content
        if hasattr(final_message, "content")
        else str(final_message),
        "messages": result.get("messages", []),
    }

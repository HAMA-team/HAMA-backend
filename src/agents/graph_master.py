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
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph_supervisor import create_supervisor

from src.agents.general import general_agent
from src.agents.portfolio import portfolio_agent
from src.agents.research import research_agent
from src.agents.risk import risk_agent
from src.agents.strategy import strategy_agent
from src.agents.trading import trading_agent
from src.config.settings import settings
from src.utils.llm_factory import get_llm

logger = logging.getLogger(__name__)


# ==================== Supervisor 구성 ====================

def build_supervisor(automation_level: int = 2, llm: Optional[BaseChatModel] = None):
    """
    Langgraph Supervisor 패턴 기반 Master Agent 정의를 생성합니다.
    """
    if llm is None:
        llm = get_llm(
            temperature=0,
            max_tokens=settings.MAX_TOKENS,
        )

    supervisor_prompt = f"""당신은 투자 에이전트 팀을 관리하는 Supervisor입니다.

**사용 가능한 에이전트:**

1. **research_agent** (종목 분석)
   - 기업 재무 분석 (재무제표, 비율)
   - 기술적 분석 (차트, 지표)
   - 뉴스 감정 분석
   - 종합 평가 및 등급 산출

2. **strategy_agent** (투자 전략)
   - 시장 사이클 분석
   - 섹터 로테이션 전략
   - 자산 배분 결정
   - Strategic Blueprint 생성

3. **risk_agent** (리스크 평가)
   - 포트폴리오 리스크 측정 (VaR, 변동성)
   - 집중도 리스크 분석
   - 리스크 경고 및 권고사항 생성

4. **trading_agent** (매매 실행)
   - 매매 주문 생성 및 실행
   - ⚠️ automation_level {automation_level}에서는 승인 필요

5. **portfolio_agent** (포트폴리오 관리)
   - 포트폴리오 구성 및 최적화
   - 리밸런싱 제안

6. **monitoring_agent** (시장 모니터링)
   - 가격 변동 추적
   - 이벤트 감지 (거래량 급증, VI 발동)
   - 정기 리포트 생성

7. **general_agent** (일반 질의응답)
   - 투자 용어 설명 (PER, PBR 등)
   - 일반 시장 질문 응답
   - 투자 전략 교육

**중요 규칙:**

1. **병렬 실행 가능**: 여러 에이전트를 동시에 호출할 수 있습니다.
   예: 종목 분석 시 research + strategy + risk 동시 호출

2. **에이전트 조합 예시:**
   - "삼성전자 분석해줘" → research_agent + strategy_agent + risk_agent
   - "내 포트폴리오 리밸런싱" → portfolio_agent + risk_agent
   - "PER이 뭐야?" → general_agent
   - "삼성전자 10주 매수" → trading_agent

3. **HITL (Human-in-the-Loop):**
   - 각 에이전트가 내부적으로 HITL을 처리합니다.
   - 현재 automation_level: {automation_level}
   - trading_agent는 레벨 2+ 에서 자동 승인 요청

4. **필요한 에이전트만 선택:**
   - 불필요한 에이전트는 호출하지 마세요.
   - 사용자 요청을 정확히 분석하세요.

사용자 요청을 분석하고, 적절한 에이전트들을 선택하세요.
"""

    supervisor = create_supervisor(
        agents=[
            research_agent,
            strategy_agent,
            risk_agent,
            trading_agent,
            general_agent,
            portfolio_agent,
            # monitoring_agent,
        ],
        model=llm,
        parallel_tool_calls=True,
        prompt=supervisor_prompt,
    )

    logger.info("✅ [Supervisor] 생성 완료 (automation_level=%s)", automation_level)

    return supervisor


def build_state_graph(automation_level: int = 2):
    """
    Supervisor 기반 Langgraph 정의를 반환합니다.

    그래프 정의 단계에서는 순수하게 구조만 생성하고 부수효과를 최소화합니다.
    """
    llm = get_llm(
        temperature=0,
        max_tokens=settings.MAX_TOKENS,
    )
    return build_supervisor(automation_level=automation_level, llm=llm)


def _resolve_backend_key(backend: Optional[str] = None) -> str:
    if backend:
        return backend.lower()
    return getattr(settings, "GRAPH_CHECKPOINT_BACKEND", "memory").lower()


def _create_checkpointer(backend_key: str):
    """
    backend_key에 따라 적절한 체크포인터 인스턴스를 생성합니다.

    Note: PostgresSaver는 context manager이므로 __enter__()를 호출하여
    실제 인스턴스를 얻습니다. 연결은 프로세스 종료 시까지 유지됩니다.
    """
    key = backend_key.lower()

    # PostgreSQL checkpointer는 비동기 context manager로 구현되어
    # 현재 동기 캐싱 구조에서는 사용이 복잡함
    # 프로덕션에서는 Redis checkpointer 사용 권장
    if key == "postgres":
        logger.warning(
            "PostgreSQL checkpointer는 비동기 초기화가 필요하여 지원하지 않습니다. "
            "Redis checkpointer 사용을 권장합니다."
        )
        return MemorySaver()

    if key == "redis":
        try:
            from langgraph.checkpoint.redis import RedisSaver
        except ImportError as exc:  # pragma: no cover - 환경에 따라 optional dependency
            raise ImportError(
                "langgraph-checkpoint-redis 패키지가 필요합니다."
            ) from exc

        # Context manager를 열어서 실제 RedisSaver 인스턴스 반환
        # 연결은 애플리케이션 생명주기 동안 유지됨
        conn_manager = RedisSaver.from_conn_string(settings.REDIS_URL)
        return conn_manager.__enter__()

    # 기본값: 인메모리 Saver
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

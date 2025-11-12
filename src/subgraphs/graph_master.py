"""
Supervisor 패턴 기반 멀티 에이전트 시스템

Supervisor의 역할:
1. 간단한 조회는 직접 처리 (사용가능한 Tool을 통해)
2. 투자 용어 설명은 자연스럽게 답변 (tool 없이)
3. 복잡한 심층 분석만 전문가(SubGraph)에게 위임
4. 매매 전 리스크 분석 및 HITL 승인 관리
"""
import logging
from functools import lru_cache
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

from langgraph_supervisor import create_supervisor

from src.subgraphs.research_subgraph import research_agent
from src.subgraphs.quantitative_subgraph import quantitative_agent
from src.subgraphs.tools import get_all_tools
from src.config.settings import settings
from src.schemas.graph_state import GraphState

logger = logging.getLogger(__name__)


# ==================== Supervisor Prompt ====================

def build_supervisor_prompt(automation_level: int) -> str:
    """
    Supervisor 시스템 프롬프트 생성 (간결하게 유지)

    Args:
        automation_level: 자동화 레벨 (1=Pilot, 2=Copilot, 3=Advisor)

    Returns:
        str: Supervisor 시스템 프롬프트
    """
    return f"""<context>
## 역할
당신은 사용자 계정을 관리하는 수석 투자 매니저입니다.

## 원칙
1. **간단한 조회** → 직접 tools 사용 (get_current_price, get_account_balance 등)
2. **투자 용어 설명** → tool 없이 자연스럽게 답변
3. **심층 분석** → 전문가에게 위임 (transfer_to_research_agent)
4. **매매 실행** → 반드시 리스크 분석 후 승인 대기

## 매매 HITL 플로우 (필수)
⚠️ automation_level {automation_level} - 모든 매매는 승인 필요

execute_trade 호출 전 반드시:
1. get_portfolio_positions() 호출
2. calculate_portfolio_risk() 호출
3. 리스크 변화를 사용자에게 명시적 보고:
   - 현재 리스크: 집중도, 변동성, VaR
   - 매매 후 예상 리스크
   - 경고 사항
4. 사용자의 **"승인" 또는 "실행"** 명시적 응답 대기
5. 승인 후에만 execute_trade() 호출
</context>

<instructions>
1. 사용자 질의 분석
2. 종목명이 있으면 resolve_ticker로 코드 변환
3. 적절한 tool 선택 (각 tool의 description 참고)
4. 작업 완료 후 결과 기반 다음 action 자동 결정
</instructions>

<examples>
## 예시 1: 단순 조회
사용자: "삼성전자 현재가?"
→ resolve_ticker("삼성전자") → get_current_price("005930")

## 예시 2: 투자 용어 설명 (tool 없이)
사용자: "PER이 뭐야?"
→ [tool 호출 없이 직접 답변] "PER(주가수익비율)은..."

## 예시 3: 정성적 분석 위임
사용자: "삼성전자 최근 뉴스 분석해줘"
→ resolve_ticker("삼성전자")
→ transfer_to_research_agent(query="삼성전자 뉴스 분석", ticker="005930")

## 예시 4: 정량적 분석 위임
사용자: "삼성전자 재무제표 분석해줘"
→ resolve_ticker("삼성전자")
→ transfer_to_quantitative_agent(query="삼성전자 재무제표 분석", ticker="005930")

## 예시 5: 매매 실행 (HITL)
사용자: "삼성전자 10주 매수해줘"
→ resolve_ticker("삼성전자")
→ get_portfolio_positions()
→ calculate_portfolio_risk(portfolio, {{"ticker": "005930", "action": "buy", "quantity": 10}})
→ [사용자에게 리스크 보고]
   "현재 포트폴리오 집중도는 30%이며, 이 매매 후 45%로 증가합니다.
    변동성은 15%에서 18%로 증가합니다.
    진행하시겠습니까?"
→ 사용자: "승인"
→ execute_trade(ticker="005930", action="buy", quantity=10)
</examples>
"""


# ==================== Supervisor 생성 ====================

def build_supervisor(automation_level: int = 2, llm: Optional[BaseChatModel] = None):
    """
    Supervisor 생성

    Args:
        automation_level: 자동화 레벨 (1=Pilot, 2=Copilot, 3=Advisor)
        llm: 사용할 LLM (None이면 설정에서 가져옴)

    Returns:
        StateGraph: Supervisor workflow (컴파일되지 않은 상태)
    """
    if llm is None:
        from src.utils.llm_factory import _build_llm, _loop_token

        provider = settings.ROUTER_MODEL_PROVIDER
        model_name = settings.ROUTER_MODEL

        logger.info(
            "🤖 [Supervisor] LLM 초기화: provider=%s, model=%s",
            provider,
            model_name,
        )

        llm = _build_llm(
            provider=provider,
            model_name=model_name,
            temperature=0.0,
            max_tokens=settings.MAX_TOKENS,
            loop_token=_loop_token(),
        )

    # Tools 수집
    tools = get_all_tools()
    logger.info(f"🔧 [Supervisor] Tools 로드 완료: {len(tools)}개")

    # Supervisor Prompt
    prompt = build_supervisor_prompt(automation_level)

    # SubGraphs 등록 (이미 compile된 상태)
    agents = [
        research_agent,      # Research SubGraph (정성적 분석)
        quantitative_agent,  # Quantitative SubGraph (정량적 분석)
    ]

    logger.info(f"👥 [Supervisor] SubGraphs 로드 완료: {len(agents)}개")
    for agent in agents:
        logger.info(f"  - {agent.name}")

    # Supervisor 생성 (langgraph_supervisor 패턴)
    # create_supervisor가 자동으로 transfer_to_Research_Agent 등의 handoff tools 생성
    supervisor_workflow = create_supervisor(
        agents=agents,
        model=llm,
        tools=tools,
        prompt=prompt,
        parallel_tool_calls=True,  # 병렬 실행 허용
        state_schema=GraphState,
        output_mode="last_message",  # SubGraph 결과 중 마지막 메시지만 반환
    )

    logger.info("✅ [Supervisor] 생성 완료 (automation_level=%s, agents=%d, tools=%d)",
                automation_level, len(agents), len(tools))

    return supervisor_workflow


# ==================== Graph 컴파일 ====================


@lru_cache(maxsize=16)
def get_compiled_graph(automation_level: int):
    """
    컴파일된 Supervisor graph 반환 (캐싱)

    Args:
        automation_level: 자동화 레벨

    Returns:
        CompiledStateGraph: 컴파일된 graph
    """
    supervisor_workflow = build_supervisor(automation_level=automation_level)

    # Checkpointer 추가 (상태 관리 및 HITL 승인 처리를 위해 필수)
    compiled_graph = supervisor_workflow.compile(
        checkpointer=MemorySaver()
    )

    logger.info(
        "🔧 [Graph] 컴파일 완료 (automation_level=%s, checkpointer=MemorySaver)",
        automation_level,
    )

    return compiled_graph


# ==================== Main Interface ====================

def build_graph(automation_level: int = 2, **kwargs):
    """
    Supervisor graph 생성 (기존 API 호환)

    Args:
        automation_level: 자동화 레벨
        **kwargs: 기타 인자 (무시됨 - 하위 호환성 유지)

    Returns:
        CompiledStateGraph: 컴파일된 Supervisor graph
    """
    return get_compiled_graph(automation_level=automation_level)

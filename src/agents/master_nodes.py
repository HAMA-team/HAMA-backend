"""
마스터 에이전트 노드 함수들 (LLM 기반)

GPT-5 nano를 활용한 Intent 분석 및 Supervisor 노드
"""
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import logging

from src.config.settings import settings
from src.schemas.graph_state import GraphState

logger = logging.getLogger(__name__)


# ==================== Pydantic 모델 ====================

class IntentAnalysis(BaseModel):
    """Intent 분석 결과"""
    intent: str = Field(description="분석된 사용자 의도 (stock_analysis, trade_execution, portfolio_evaluation, rebalancing, performance_check, market_status, general_question 중 하나)")
    stock_code: str | None = Field(default=None, description="종목 코드 (있는 경우)")
    stock_name: str | None = Field(default=None, description="종목 이름 (있는 경우)")
    confidence: float = Field(description="분석 신뢰도 (0.0-1.0)")


class AgentSelection(BaseModel):
    """에이전트 선택 결과"""
    agents: List[str] = Field(description="호출할 에이전트 ID 리스트 (research_agent, strategy_agent, risk_agent, portfolio_agent, monitoring_agent, education_agent 중 선택)")
    reasoning: str = Field(description="에이전트 선택 이유")


# ==================== LLM 기반 Intent 분석 노드 ====================

async def llm_intent_analysis_node(state: GraphState) -> GraphState:
    """
    GPT-5 nano 기반 의도 분석 노드

    LangGraph 표준: messages에서 마지막 사용자 메시지 추출
    Structured Output으로 intent, 종목 정보, 신뢰도 추출
    """
    # messages에서 마지막 메시지 추출
    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Claude LLM 초기화
    from langchain_anthropic import ChatAnthropic
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error(f"❌ [LLM Intent] ANTHROPIC_API_KEY not found, fallback to keyword analysis")
        # Fallback: 키워드 기반 의도 분석
        query_lower = query.lower()
        if any(word in query_lower for word in ["리밸런싱", "재구성", "재배분", "조정", "비중"]):
            intent = "rebalancing"
        elif any(word in query_lower for word in ["매수", "매도", "사", "팔"]):
            intent = "trade_execution"
        elif any(word in query_lower for word in ["수익률", "현황"]):
            intent = "performance_check"
        elif any(word in query_lower for word in ["포트폴리오", "자산배분"]):
            intent = "portfolio_evaluation"
        elif any(word in query_lower for word in ["분석", "어때", "평가", "투자", "전략"]):
            intent = "stock_analysis"
        elif "시장" in query_lower:
            intent = "market_status"
        else:
            intent = "general_question"

        logger.info(f"🔍 [Keyword Intent] 의도: {intent}")
        return {
            "intent": intent,
            "intent_confidence": 0.6,  # 키워드 기반은 낮은 신뢰도
        }

    llm = ChatAnthropic(
        model="claude-3-5-haiku-20241022",
        api_key=api_key,
        temperature=0
    )

    # Structured Output 설정
    structured_llm = llm.with_structured_output(IntentAnalysis)

    # Intent 분석 프롬프트
    prompt = f"""사용자 쿼리를 분석하여 의도를 파악하세요.

사용자 쿼리: "{query}"

의도 카테고리:
- stock_analysis: 종목 분석 및 평가
- trade_execution: 매수/매도 실행
- portfolio_evaluation: 포트폴리오 평가
- rebalancing: 리밸런싱 및 재구성
- performance_check: 수익률 및 현황 조회
- market_status: 시장 상황 분석
- general_question: 일반 질문

종목 정보가 있다면 추출하세요 (종목명 또는 종목코드).
분석 신뢰도도 함께 제공하세요."""

    try:
        # LLM 호출
        analysis: IntentAnalysis = await structured_llm.ainvoke([HumanMessage(content=prompt)])

        logger.info(f"🔍 [LLM Intent] 의도: {analysis.intent}, 종목: {analysis.stock_name or analysis.stock_code}, 신뢰도: {analysis.confidence:.2f}")

        return {
            "intent": analysis.intent,
            "stock_code": analysis.stock_code,
            "stock_name": analysis.stock_name,
            "intent_confidence": analysis.confidence,
        }

    except Exception as e:
        logger.error(f"❌ [LLM Intent] 분석 실패: {e}")
        # Fallback: 일반 질문으로 처리
        return {
            "intent": "general_question",
            "intent_confidence": 0.0,
        }


# ==================== LLM 기반 Supervisor 노드 ====================

async def llm_supervisor_node(state: GraphState) -> GraphState:
    """
    GPT-5 nano 기반 Supervisor 노드

    Intent와 컨텍스트를 바탕으로 호출할 에이전트를 자율적으로 선택
    """
    intent = state.get("intent", "general_question")
    query = state["messages"][-1].content if hasattr(state["messages"][-1], 'content') else str(state["messages"][-1])
    stock_info = state.get("stock_name") or state.get("stock_code") or ""

    # Claude LLM 초기화
    from langchain_anthropic import ChatAnthropic
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error(f"❌ [LLM Supervisor] ANTHROPIC_API_KEY not found")
        # Fallback: 의도 기반 기본 라우팅
        fallback_routing = {
            "stock_analysis": ["research_agent", "strategy_agent", "risk_agent"],
            "trade_execution": ["strategy_agent", "risk_agent"],
            "portfolio_evaluation": ["portfolio_agent", "risk_agent"],
            "rebalancing": ["portfolio_agent", "strategy_agent", "risk_agent"],
            "performance_check": ["portfolio_agent"],
            "market_status": ["research_agent", "monitoring_agent"],
            "general_question": ["education_agent"],
        }
        agents = fallback_routing.get(intent, ["education_agent"])
        return {
            "agents_to_call": agents,
            "supervisor_reasoning": "Fallback routing (no API key)",
        }

    llm = ChatAnthropic(
        model="claude-3-5-haiku-20241022",
        api_key=api_key,
        temperature=0
    )

    # Structured Output 설정
    structured_llm = llm.with_structured_output(AgentSelection)

    # Supervisor 프롬프트
    prompt = f"""다음 사용자 요청을 처리하기 위해 필요한 에이전트를 선택하세요.

사용자 쿼리: "{query}"
파악된 의도: {intent}
종목 정보: {stock_info or '없음'}

사용 가능한 에이전트:
- research_agent: 종목 분석, 재무제표, 뉴스 분석
- strategy_agent: 투자 전략 수립, 시장 분석, 자산 배분
- risk_agent: 리스크 평가 및 관리
- portfolio_agent: 포트폴리오 구성 및 평가, 리밸런싱
- monitoring_agent: 시장 모니터링, 실시간 데이터
- education_agent: 투자 교육 및 일반 질문 답변

필요한 에이전트를 선택하고 이유를 설명하세요."""

    try:
        # LLM 호출
        selection: AgentSelection = await structured_llm.ainvoke([HumanMessage(content=prompt)])

        logger.info(f"🎯 [LLM Supervisor] 선택된 에이전트: {selection.agents}")
        logger.info(f"💡 [LLM Supervisor] 선택 이유: {selection.reasoning}")

        return {
            "agents_to_call": selection.agents,
            "supervisor_reasoning": selection.reasoning,
        }

    except Exception as e:
        logger.error(f"❌ [LLM Supervisor] 선택 실패: {e}")
        # Fallback: 의도 기반 기본 라우팅
        fallback_routing = {
            "stock_analysis": ["research_agent", "strategy_agent", "risk_agent"],
            "trade_execution": ["strategy_agent", "risk_agent"],
            "portfolio_evaluation": ["portfolio_agent", "risk_agent"],
            "rebalancing": ["portfolio_agent", "strategy_agent", "risk_agent"],
            "performance_check": ["portfolio_agent"],
            "market_status": ["research_agent", "monitoring_agent"],
            "general_question": ["education_agent"],
        }

        agents = fallback_routing.get(intent, ["education_agent"])
        return {
            "agents_to_call": agents,
            "supervisor_reasoning": "Fallback routing based on intent",
        }

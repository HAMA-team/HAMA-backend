"""
리포트 생성 도구

Research와 Strategy 결과를 통합하여 Investment Dashboard를 생성합니다.
"""
import logging
from datetime import datetime
from typing import Dict, Any

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== Input Schema ====================

class GenerateReportInput(BaseModel):
    """리포트 생성 입력"""
    research_result: dict = Field(
        default_factory=dict,
        description="Research Agent의 분석 결과"
    )
    strategy_result: dict = Field(
        default_factory=dict,
        description="Strategy Agent의 전략 결과"
    )
    query: str = Field(
        description="사용자 질의"
    )


# ==================== Tool ====================

@tool(args_schema=GenerateReportInput)
async def generate_investment_report(
    research_result: dict,
    strategy_result: dict,
    query: str
) -> Dict[str, Any]:
    """
    [언제] Research와 Strategy 분석이 완료된 후, 통합 리포트가 필요할 때 사용합니다.
    [무엇] Research와 Strategy 결과를 종합하여 Investment Dashboard를 생성합니다.
    [주의] 최소한 research_result 또는 strategy_result 중 하나는 있어야 합니다.

    생성되는 리포트 구성:
    - 핵심 요약 (Executive Summary)
    - 투자 의견 (Investment Opinion)
    - 리스크 경고 (Risk Warnings)
    - 액션 플랜 (Action Plan)

    Args:
        research_result: Research Agent 분석 결과
        strategy_result: Strategy Agent 전략 결과
        query: 사용자 질의

    Returns:
        dict: {
            "dashboard": "통합 Dashboard 내용 (Markdown)",
            "summary": "핵심 요약",
            "investment_opinion": "투자 의견",
            "risk_warnings": ["경고1", "경고2"],
            "action_plan": ["액션1", "액션2"],
            "generated_at": "2024-01-01T12:00:00"
        }

    예시:
    사용자: "삼성전자 종합 분석해줘"
    → transfer_to_research_agent(...)
    → research_result 획득
    → transfer_to_strategy_agent(...)  # TODO: Strategy Agent 구현 필요
    → strategy_result 획득
    → generate_investment_report(research_result, strategy_result, query)
    """
    try:
        logger.info(f"📊 [Report Tool] 통합 리포트 생성 시작")
        logger.info(f"  - Research 포함: {bool(research_result)}")
        logger.info(f"  - Strategy 포함: {bool(strategy_result)}")

        # 최소한 하나의 결과는 있어야 함
        if not research_result and not strategy_result:
            return {
                "success": False,
                "message": "Research 또는 Strategy 결과가 필요합니다."
            }

        # LLM으로 통합 Dashboard 생성
        from src.prompts.templates.integrated_dashboard import build_integrated_dashboard_prompt
        from src.utils.llm_factory import get_default_agent_llm as get_llm

        llm = get_llm(temperature=0.3, max_tokens=4000)

        dashboard_prompt = build_integrated_dashboard_prompt(
            research_result=research_result,
            strategy_result=strategy_result,
            query=query,
        )

        # LLM 호출
        logger.info("🤖 [Report Tool] LLM 호출 중...")
        dashboard_response = await llm.ainvoke(dashboard_prompt)
        dashboard_content = dashboard_response.content

        logger.info("✅ [Report Tool] 통합 리포트 생성 완료 (길이: %d자)", len(dashboard_content))

        # 최종 리포트 구성
        return {
            "success": True,
            "dashboard": dashboard_content,
            "query": query,
            "generated_at": datetime.now().isoformat(),
            "research_included": bool(research_result),
            "strategy_included": bool(strategy_result),
            "research_consensus": research_result.get("consensus") if research_result else None,
            "strategy_cycle": strategy_result.get("market_cycle") if strategy_result else None,
        }

    except Exception as e:
        logger.error(f"❌ [Report Tool] 리포트 생성 실패: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"리포트 생성 중 오류가 발생했습니다: {e}"
        }


# ==================== Tool 목록 ====================

def get_report_tools():
    """리포트 도구 목록 반환"""
    return [
        generate_investment_report,
    ]

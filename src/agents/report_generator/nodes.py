"""Report Generator Agent 노드 함수들."""
import logging
from datetime import datetime

from langchain_core.messages import AIMessage

from .state import ReportGeneratorState

logger = logging.getLogger(__name__)


async def generate_report_node(state: ReportGeneratorState) -> ReportGeneratorState:
    """
    Research + Strategy 결과를 통합하여 최종 Investment Dashboard 생성

    단일 노드로 통합 리포트를 생성합니다.
    """
    logger.info("📊 [ReportGenerator] 통합 리포트 생성 시작")

    research_result = state.get("research_result") or {}
    strategy_result = state.get("strategy_result") or {}
    query = state.get("query", "")
    request_id = state.get("request_id", "")

    # Research 또는 Strategy 결과가 없으면 에러
    if not research_result and not strategy_result:
        error_msg = "Research 또는 Strategy 결과가 필요합니다."
        logger.error("❌ [ReportGenerator] %s", error_msg)
        return {
            "error": error_msg,
            "messages": [AIMessage(content=error_msg)],
        }

    try:
        # Integrated Dashboard 프롬프트 생성
        from src.prompts.templates.integrated_dashboard import build_integrated_dashboard_prompt
        from src.utils.llm_factory import get_default_agent_llm as get_llm

        llm = get_llm(temperature=0.3, max_tokens=4000)

        dashboard_prompt = build_integrated_dashboard_prompt(
            research_result=research_result,
            strategy_result=strategy_result,
            query=query,
        )

        # LLM 호출하여 Dashboard 생성
        logger.info("🤖 [ReportGenerator] LLM 호출 중...")
        dashboard_response = await llm.ainvoke(dashboard_prompt)
        dashboard_content = dashboard_response.content

        logger.info("✅ [ReportGenerator] 통합 리포트 생성 완료 (길이: %d자)", len(dashboard_content))

        # 최종 리포트 구성
        final_report = {
            "request_id": request_id,
            "query": query,
            "generated_at": datetime.now().isoformat(),
            "dashboard": dashboard_content,
            "research_included": bool(research_result),
            "strategy_included": bool(strategy_result),
            "research_consensus": research_result.get("consensus") if research_result else None,
            "strategy_cycle": strategy_result.get("market_cycle") if strategy_result else None,
        }

        # Supervisor 호환성을 위해 messages 포함
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=dashboard_content))

        # MasterState로 결과 전달
        return {
            "final_report": final_report,
            "dashboard_content": dashboard_content,
            "agent_results": {
                "report_generator": {
                    "summary": f"통합 리포트 생성 완료 (Research: {bool(research_result)}, Strategy: {bool(strategy_result)})",
                    "dashboard": dashboard_content,
                }
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error("❌ [ReportGenerator] 에러: %s", e, exc_info=True)

        # 에러 시에도 messages 포함
        messages = list(state.get("messages", []))
        error_msg = f"리포트 생성 실패: {str(e)}"
        messages.append(AIMessage(content=error_msg))

        return {
            "error": error_msg,
            "agent_results": {
                "report_generator": {"error": error_msg}
            },
            "messages": messages,
        }

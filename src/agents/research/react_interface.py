"""
Research Agent - ReAct 인터페이스

기존 서브그래프와 호환되는 인터페이스 제공
"""
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage

from .react_agent import create_research_agent

logger = logging.getLogger(__name__)


async def run_research_react(
    query: str,
    stock_code: Optional[str] = None,
    depth_level: str = "detailed",
    user_profile: Optional[dict] = None,
) -> dict:
    """
    ReAct 기반 Research Agent 실행

    Args:
        query: 사용자 질문
        stock_code: 종목 코드 (옵션, query에서 추출 가능)
        depth_level: "brief" | "detailed" | "comprehensive"
        user_profile: 사용자 프로파일

    Returns:
        분석 결과 딕셔너리
    """
    logger.info(f"🚀 [Research/ReAct] 실행: query={query[:50]}..., depth={depth_level}")

    # 1. ReAct Agent 생성
    agent = create_research_agent(
        depth_level=depth_level,
        user_profile=user_profile or {}
    )

    # 2. 입력 구성
    if stock_code:
        full_query = f"{query} (종목코드: {stock_code})"
    else:
        full_query = query

    input_state = {
        "messages": [HumanMessage(content=full_query)]
    }

    # 3. Agent 실행
    try:
        result = await agent.ainvoke(input_state)

        # 4. 결과 파싱
        messages = result.get("messages", [])
        final_message = messages[-1] if messages else None

        if not final_message:
            raise RuntimeError("ReAct Agent가 응답을 생성하지 않았습니다")

        response = {
            "success": True,
            "query": query,
            "stock_code": stock_code,
            "depth_level": depth_level,
            "analysis": final_message.content if hasattr(final_message, "content") else str(final_message),
            "messages": [
                {"role": m.type if hasattr(m, "type") else "unknown", "content": m.content if hasattr(m, "content") else str(m)}
                for m in messages
            ]
        }

        logger.info(f"✅ [Research/ReAct] 완료")
        return response

    except Exception as e:
        logger.error(f"❌ [Research/ReAct] 에러: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }


async def run_research_with_router(
    query: str,
    routing_decision: dict,
    user_profile: dict,
) -> dict:
    """
    Router 판단 결과를 반영한 Research Agent 실행

    Args:
        query: 사용자 질문
        routing_decision: Router의 판단 결과
        user_profile: 사용자 프로파일

    Returns:
        분석 결과
    """
    depth_level = routing_decision.get("depth_level", "detailed")
    stock_code = routing_decision.get("stock_code")  # Router가 추출한 종목 코드

    return await run_research_react(
        query=query,
        stock_code=stock_code,
        depth_level=depth_level,
        user_profile=user_profile
    )

"""
종목 코드 변환 도구

사용자가 종목명을 언급한 경우 6자리 종목 코드로 변환합니다.
"""
import logging
from typing import Dict, Any, Optional

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

from src.services.stock_data_service import stock_data_service
from src.utils.stock_name_extractor import extract_stock_names_from_query

logger = logging.getLogger(__name__)


# ==================== Input Schema ====================

class ResolveTickerInput(BaseModel):
    """종목 코드 변환 입력"""
    stock_name: str = Field(
        description="종목명 (예: '삼성전자', 'SK하이닉스') 또는 사용자 쿼리"
    )


# ==================== Tool ====================

@tool(args_schema=ResolveTickerInput)
async def resolve_ticker(stock_name: str) -> Dict[str, Any]:
    """
    [언제] 사용자가 종목명을 언급했지만 6자리 종목코드가 필요한 경우 사용합니다.
    [무엇] 종목명을 6자리 종목코드로 변환합니다. 정확히 일치하지 않으면 유사 종목을 추천합니다.
    [주의] 이미 6자리 종목코드(예: "005930")를 가지고 있다면 이 tool을 사용할 필요 없습니다.

    Args:
        stock_name: 종목명 또는 사용자 쿼리
            - "삼성전자" → 정확한 종목명
            - "sk 하이닉스 분석해줘" → 쿼리에서 종목명 추출
            - "삼전" → 유사 종목 추천

    Returns:
        dict: {
            "success": True,
            "ticker": "005930",
            "name": "삼성전자",
            "market": "KOSPI"
        }

        또는 (종목을 찾지 못한 경우):
        dict: {
            "success": False,
            "query": "삼전",
            "alternatives": [
                {"ticker": "005930", "name": "삼성전자", "similarity": 0.85},
                {"ticker": "005380", "name": "현대차", "similarity": 0.30}
            ],
            "message": "'삼전'를 찾을 수 없어요. 혹시 다음 종목 중 하나를 찾으시는 건가요?\n\n- 삼성전자(005930)\n\n정확한 종목명이나 6자리 티커를 입력해주세요."
        }

    예시:
    - 입력: "삼성전자" → {"success": True, "ticker": "005930", "name": "삼성전자"}
    - 입력: "sk 하이닉스 분석해줘" → {"success": True, "ticker": "000660", "name": "SK하이닉스"}
    - 입력: "삼전" → {"success": False, "alternatives": [...]}
    """
    try:
        logger.info(f"🔍 [Ticker Tool] 종목 코드 변환 시도: {stock_name}")

        # 1. 쿼리에서 종목명 추출 (LLM 또는 6자리 코드 직접 감지)
        stock_names = await extract_stock_names_from_query(stock_name)

        if not stock_names:
            logger.warning(f"⚠️ [Ticker Tool] 종목명을 추출할 수 없음: {stock_name}")
            return {
                "success": False,
                "query": stock_name,
                "message": f"'{stock_name}'에서 종목명을 찾을 수 없어요. 종목명이나 6자리 티커(예: 005930)를 입력해주세요."
            }

        # 2. 각 종목명을 종목 코드로 변환
        for name in stock_names:
            # 이미 6자리 코드인 경우
            if len(name) == 6 and name.isdigit():
                logger.info(f"✅ [Ticker Tool] 6자리 코드 직접 사용: {name}")
                # TODO: 종목명 역조회 (선택적)
                return {
                    "success": True,
                    "ticker": name,
                    "name": None,  # 역조회 미구현
                    "market": None
                }

            # 종목명으로 코드 조회 (KOSPI, KOSDAQ, KONEX 순서로 시도)
            for market in ("KOSPI", "KOSDAQ", "KONEX"):
                ticker = await stock_data_service.get_stock_by_name(name, market=market)
                if ticker:
                    logger.info(f"✅ [Ticker Tool] 종목 코드 변환 성공: {name} → {ticker} ({market})")
                    return {
                        "success": True,
                        "ticker": ticker,
                        "name": name,
                        "market": market
                    }

        # 3. 종목을 찾지 못한 경우 → 유사 종목 추천
        logger.warning(f"❌ [Ticker Tool] 종목을 찾지 못함: {stock_names}")

        # TODO: LLM 기반 유사 종목 추천 (routing_nodes.py의 clarification_node 로직 참고)
        # 현재는 간단한 메시지만 반환
        alternatives = []  # TODO: 유사 종목 리스트 생성

        return {
            "success": False,
            "query": stock_names[0] if stock_names else stock_name,
            "alternatives": alternatives,
            "message": (
                f"'{stock_names[0] if stock_names else stock_name}'를 찾을 수 없어요. "
                f"정확한 종목명이나 6자리 티커(예: 005930)를 입력해주세요."
            )
        }

    except Exception as e:
        logger.error(f"❌ [Ticker Tool] 종목 코드 변환 실패: {stock_name}, 에러: {e}")
        return {
            "success": False,
            "query": stock_name,
            "error": str(e),
            "message": f"종목 코드 변환 중 오류가 발생했습니다: {e}"
        }


# ==================== Tool 목록 ====================

def get_ticker_tools():
    """종목 코드 변환 도구 목록 반환"""
    return [
        resolve_ticker,
    ]

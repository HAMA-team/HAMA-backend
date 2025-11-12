"""
Quantitative Agent 노드 함수들

정량적 분석 및 전략 수립
"""
import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage

from src.subgraphs.quantitative_subgraph.state import QuantitativeState
from src.utils.llm_factory import get_default_agent_llm as get_llm

logger = logging.getLogger(__name__)


# ==================== 데이터 수집 ====================

async def data_collector_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    재무제표 및 시장 데이터 수집

    DART API: 재무제표
    pykrx: 시장 데이터, 기술적 지표
    """
    stock_code = state.get("stock_code")

    if not stock_code:
        return {
            "error": "종목 코드가 필요합니다",
            "messages": [AIMessage(content="종목 코드가 제공되지 않았습니다")]
        }

    logger.info(f"📊 [Quantitative/DataCollector] 데이터 수집 시작: {stock_code}")

    try:
        # 1. 재무제표 수집 (DART API)
        from src.services.dart_service import dart_service

        financial_statements = await dart_service.get_financial_statements(stock_code)

        # 2. 시장 데이터 수집 (pykrx)
        from src.services.stock_data_service import stock_data_service

        # 주가 데이터
        price_data = await stock_data_service.get_stock_price(stock_code, period_days=180)

        # 펀더멘털 지표
        valuation_metrics = await stock_data_service.get_fundamental_data(stock_code)

        # 기술적 지표 계산
        from src.utils.indicators import calculate_all_indicators
        technical_indicators = calculate_all_indicators(price_data) if price_data else {}

        logger.info(f"✅ [Quantitative/DataCollector] 데이터 수집 완료")

        return {
            "financial_statements": financial_statements,
            "valuation_metrics": valuation_metrics,
            "technical_indicators": technical_indicators,
            "messages": [AIMessage(content=f"{stock_code} 데이터 수집 완료")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/DataCollector] 데이터 수집 실패: {e}", exc_info=True)
        return {
            "error": str(e),
            "messages": [AIMessage(content=f"데이터 수집 실패: {e}")]
        }


# ==================== 분석 노드 ====================

async def fundamental_analyst_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    펀더멘털 분석

    재무제표 기반 기업 가치 평가
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    financial_statements = state.get("financial_statements", {})
    valuation_metrics = state.get("valuation_metrics", {})

    logger.info(f"💼 [Quantitative/Fundamental] 펀더멘털 분석 시작: {stock_code}")

    try:
        llm = get_llm(temperature=0.3, max_tokens=2000)

        # LLM 프롬프트 생성
        from src.prompts.quantitative.fundamental import build_fundamental_analysis_prompt

        prompt = build_fundamental_analysis_prompt(
            stock_code=stock_code,
            financial_statements=financial_statements,
            valuation_metrics=valuation_metrics
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        fundamental_analysis = parse_llm_json(response.content)

        logger.info(f"✅ [Quantitative/Fundamental] 분석 완료")

        return {
            "fundamental_analysis": fundamental_analysis,
            "messages": [AIMessage(content="펀더멘털 분석 완료")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/Fundamental] 분석 실패: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"펀더멘털 분석 실패: {e}")]
        }


async def technical_analyst_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    기술적 분석

    기술적 지표 기반 매매 시그널 분석
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    technical_indicators = state.get("technical_indicators", {})

    logger.info(f"📈 [Quantitative/Technical] 기술적 분석 시작: {stock_code}")

    try:
        llm = get_llm(temperature=0.3, max_tokens=2000)

        # LLM 프롬프트 생성
        from src.prompts.quantitative.technical import build_technical_analysis_prompt

        prompt = build_technical_analysis_prompt(
            stock_code=stock_code,
            technical_indicators=technical_indicators
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        technical_analysis = parse_llm_json(response.content)

        logger.info(f"✅ [Quantitative/Technical] 분석 완료")

        return {
            "technical_analysis": technical_analysis,
            "messages": [AIMessage(content="기술적 분석 완료")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/Technical] 분석 실패: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"기술적 분석 실패: {e}")]
        }


async def strategy_synthesis_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    최종 전략 통합

    펀더멘털 + 기술적 분석을 종합하여 투자 전략 제안
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    fundamental_analysis = state.get("fundamental_analysis", {})
    technical_analysis = state.get("technical_analysis", {})

    logger.info(f"🎯 [Quantitative/Strategy] 전략 통합 시작: {stock_code}")

    try:
        llm = get_llm(temperature=0.5, max_tokens=3000)

        # LLM 프롬프트 생성
        from src.prompts.quantitative.strategy import build_strategy_synthesis_prompt

        prompt = build_strategy_synthesis_prompt(
            stock_code=stock_code,
            fundamental_analysis=fundamental_analysis,
            technical_analysis=technical_analysis,
            query=state.get("query", "")
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        strategy = parse_llm_json(response.content)

        # 요약 메시지 생성
        action = strategy.get("action", "hold")
        confidence = strategy.get("confidence", 50)
        reasoning = strategy.get("reasoning", "")

        summary = (
            f"📊 {stock_code} 정량 분석 완료\n"
            f"전략: {action.upper()} (신뢰도: {confidence}%)\n"
            f"근거: {reasoning[:100]}..."
        )

        logger.info(f"✅ [Quantitative/Strategy] 전략 수립 완료: {action} ({confidence}%)")

        return {
            "strategy": strategy,
            "messages": [AIMessage(content=summary)]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/Strategy] 전략 수립 실패: {e}", exc_info=True)

        # Fallback 전략
        fallback_strategy = {
            "action": "hold",
            "confidence": 50,
            "reasoning": f"분석 중 오류 발생: {str(e)}",
            "target_price": None,
            "stop_loss": None,
            "time_horizon": "중기"
        }

        return {
            "strategy": fallback_strategy,
            "messages": [AIMessage(content=f"전략 수립 실패 (Fallback: HOLD): {e}")]
        }

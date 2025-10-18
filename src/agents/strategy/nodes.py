"""
Strategy Agent 노드 함수들

Langgraph 서브그래프 노드 구현
"""
from .state import StrategyState
from src.schemas.strategy import InvestmentStyle
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)


# ==================== Market Analysis Node ====================

async def market_analysis_node(state: StrategyState) -> StrategyState:
    """
    1단계: 시장 사이클 분석

    LLM 기반 거시경제 분석
    """
    logger.info(f"📈 [Strategy/Market] 시장 분석 시작")

    try:
        # market_analyzer 사용
        from src.agents.strategy.market_analyzer import market_analyzer

        market_outlook = await market_analyzer.analyze()

        logger.info(f"✅ [Strategy/Market] 시장 분석 완료: {market_outlook.cycle}")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "market_outlook": {
                "cycle": market_outlook.cycle,
                "confidence": market_outlook.confidence,
                "summary": market_outlook.summary,
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Market] 에러: {e}")

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))

        return {
            "error": f"시장 분석 실패: {str(e)}",
            "messages": messages,
        }


# ==================== Sector Rotation Node ====================

async def sector_rotation_node(state: StrategyState) -> StrategyState:
    """
    2단계: 섹터 전략 수립

    시장 사이클에 따른 섹터 로테이션
    """
    if state.get("error"):
        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        return {**state, "messages": messages}

    logger.info(f"🔄 [Strategy/Sector] 섹터 전략 수립 시작")

    try:
        from src.agents.strategy.sector_rotator import sector_rotator

        market_outlook = state.get("market_outlook", {})
        market_cycle = market_outlook.get("cycle", "expansion")
        user_preferences = state.get("user_preferences", {})

        sector_strategy = await sector_rotator.create_strategy(
            market_cycle=market_cycle,
            user_preferences=user_preferences
        )

        logger.info(f"✅ [Strategy/Sector] 섹터 전략 완료: {', '.join(sector_strategy.overweight[:2])}")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "sector_strategy": {
                "overweight": sector_strategy.overweight,
                "underweight": sector_strategy.underweight,
                "rationale": sector_strategy.rationale,
                "sectors": [w.model_dump() for w in sector_strategy.sectors],
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Sector] 에러: {e}")

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))

        return {
            "error": f"섹터 전략 수립 실패: {str(e)}",
            "messages": messages,
        }


# ==================== Asset Allocation Node ====================

async def asset_allocation_node(state: StrategyState) -> StrategyState:
    """
    3단계: 자산 배분 결정

    리스크 허용도에 따른 자산 배분
    """
    if state.get("error"):
        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        return {**state, "messages": messages}

    logger.info(f"💰 [Strategy/Asset] 자산 배분 결정 시작")

    try:
        from src.agents.strategy.risk_stance import risk_stance_analyzer

        market_outlook = state.get("market_outlook", {})
        market_cycle = market_outlook.get("cycle", "expansion")
        risk_tolerance = state.get("risk_tolerance", "moderate")

        asset_allocation = await risk_stance_analyzer.determine_allocation(
            market_cycle=market_cycle,
            risk_tolerance=risk_tolerance
        )

        logger.info(f"✅ [Strategy/Asset] 자산 배분 완료: 주식 {asset_allocation.stocks:.0%}")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "asset_allocation": {
                "stocks": float(asset_allocation.stocks),
                "cash": float(asset_allocation.cash),
                "rationale": asset_allocation.rationale,
            },
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Asset] 에러: {e}")

        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))

        return {
            "error": f"자산 배분 실패: {str(e)}",
            "messages": messages,
        }


# ==================== Blueprint Creation Node ====================

async def blueprint_creation_node(state: StrategyState) -> StrategyState:
    """
    4단계: Strategic Blueprint 생성

    모든 분석을 통합하여 최종 Blueprint 생성
    """
    if state.get("error"):
        # 에러 시에도 messages 전파
        messages = list(state.get("messages", []))
        return {**state, "messages": messages}

    logger.info(f"📋 [Strategy/Blueprint] Blueprint 생성 시작")

    try:
        market_outlook = state.get("market_outlook", {})
        sector_strategy = state.get("sector_strategy", {})
        asset_allocation = state.get("asset_allocation", {})
        user_preferences = state.get("user_preferences", {})
        risk_tolerance = state.get("risk_tolerance", "moderate")

        # 투자 스타일 결정
        investment_style = {
            "type": user_preferences.get("style", "growth"),
            "horizon": user_preferences.get("horizon", "mid_term"),
            "approach": user_preferences.get("approach", "dollar_cost_averaging"),
            "size_preference": user_preferences.get("size", "large")
        }

        # Blueprint 구성
        blueprint = {
            "market_outlook": market_outlook,
            "sector_strategy": sector_strategy,
            "asset_allocation": asset_allocation,
            "investment_style": investment_style,
            "risk_tolerance": risk_tolerance,
            "constraints": {
                "max_stocks": 10,
                "max_per_stock": 0.20,
                "min_stocks": 5
            },
            "confidence_score": market_outlook.get("confidence", 0.75),
            "key_assumptions": [
                f"{market_outlook.get('cycle', 'expansion')} 국면 지속",
                f"핵심 섹터: {', '.join(sector_strategy.get('overweight', [])[:2])}",
                f"주식 비중 {asset_allocation.get('stocks', 0.7):.0%}"
            ]
        }

        # 요약 생성
        summary = (
            f"{market_outlook.get('cycle', '확장')} 국면, "
            f"주식 {asset_allocation.get('stocks', 0):.0%}/현금 {asset_allocation.get('cash', 0):.0%}, "
            f"핵심 섹터: {', '.join(sector_strategy.get('overweight', [])[:2])}"
        )

        logger.info(f"✅ [Strategy/Blueprint] Blueprint 생성 완료")
        logger.info(f"   {summary}")

        # Supervisor 호환성을 위해 messages 포함
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=summary))

        return {
            "blueprint": blueprint,
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"❌ [Strategy/Blueprint] 에러: {e}")

        # 에러 시에도 messages 포함
        messages = list(state.get("messages", []))
        error_msg = f"Blueprint 생성 실패: {str(e)}"
        messages.append(AIMessage(content=error_msg))

        return {
            "error": error_msg,
            "messages": messages,
        }

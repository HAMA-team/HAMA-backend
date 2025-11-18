"""
Quantitative Agent 노드 함수들

정량적 분석 및 전략 수립
"""
import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage

from src.subgraphs.quantitative_subgraph.state import QuantitativeState
from src.utils.llm_factory import get_default_agent_llm as get_llm
from src.subgraphs.research_subgraph.tools import (
    get_stock_price_tool,
    get_fundamental_data_tool,
    search_corp_code_tool,
    get_financial_statement_tool,
)

logger = logging.getLogger(__name__)


# ==================== 데이터 수집 ====================

async def data_collector_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    재무제표 및 시장 데이터 수집 (Tool 사용)

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
        # 1. Tool을 사용하여 DART 기업 코드 검색
        corp_code = await search_corp_code_tool.ainvoke({"stock_code": stock_code})

        financial_statements = {}
        if corp_code:
            # 재무제표 연도 설정
            from datetime import datetime
            current_year = datetime.now().year
            current_month = datetime.now().month
            bsns_year = str(current_year - 1 if current_month < 7 else current_year)

            # Tool을 사용하여 재무제표 조회
            financial_statements = await get_financial_statement_tool.ainvoke({
                "corp_code": corp_code,
                "bsns_year": bsns_year
            })
        else:
            logger.warning(f"⚠️ [Quantitative/DataCollector] DART 기업 코드 없음: {stock_code}")

        # 2. Tool을 사용하여 시장 데이터 수집
        # 주가 데이터
        price_result = await get_stock_price_tool.ainvoke({"stock_code": stock_code, "days": 180})

        if "error" in price_result:
            raise RuntimeError(f"주가 데이터 조회 실패: {stock_code}")

        # Tool 결과에서 price_df 재구성 (기술적 지표 계산용)
        import pandas as pd
        price_df = pd.DataFrame(price_result["prices"])
        if "날짜" in price_df.columns:
            price_df = price_df.set_index("날짜")
        elif "Date" in price_df.columns:
            price_df = price_df.set_index("Date")

        # Tool을 사용하여 펀더멘털 지표 조회
        valuation_metrics = await get_fundamental_data_tool.ainvoke({"stock_code": stock_code})

        # 기술적 지표 계산
        from src.utils.indicators import calculate_all_indicators
        technical_indicators = calculate_all_indicators(price_df) if price_df is not None and len(price_df) > 0 else {}

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


# ==================== 거시 분석 노드 (Strategy Agent에서 이식) ====================

async def market_cycle_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    시장 사이클 분석 (market_analyzer.py 로직 이식)

    거시경제 지표와 섹터 성과를 분석하여 시장 사이클 판단
    - early_bull_market / mid_bull_market / late_bull_market
    - bear_market / consolidation
    """
    logger.info("🌍 [Quantitative/MarketCycle] 시장 사이클 분석 시작")

    try:
        # 1. 거시경제 데이터 수집
        from src.services.macro_data_service import macro_data_service
        from src.services.sector_data_service import sector_data_service

        macro_data = macro_data_service.macro_summary()
        if not macro_data.get("base_rate"):
            await macro_data_service.refresh_all()
            macro_data = macro_data_service.macro_summary()

        # 2. 섹터 성과 데이터 수집
        sector_ranking = await sector_data_service.get_sector_ranking(days=30)

        # 3. LLM 기반 시장 사이클 분석
        llm = get_llm(max_tokens=2000, temperature=0.1)

        # 섹터 성과 요약
        sector_summary = []
        for i, sector in enumerate(sector_ranking[:5], 1):
            sector_summary.append(
                f"{i}. {sector['sector']}: {sector['return']:+.1f}%"
            )

        prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다. 다음 거시경제 지표와 섹터 성과를 분석하여 현재 시장 사이클을 판단하세요.

## 거시경제 지표
- 기준금리: {macro_data.get('base_rate', 'N/A')}% (추세: {macro_data.get('base_rate_trend', 'N/A')})
- CPI (소비자물가): {macro_data.get('cpi', 'N/A')} (전년대비: {macro_data.get('cpi_yoy', 'N/A'):.1f}%)
- 환율 (원/달러): {macro_data.get('exchange_rate', 'N/A'):,.0f}원

## 섹터 성과 (최근 30일)
{chr(10).join(sector_summary)}

## 시장 사이클 분류 기준

1. **early_bull_market (초기 강세장)**
   - 금리 인하 시작 또는 안정화
   - 주요 섹터 상승 전환
   - 시장 심리 회복 초기

2. **mid_bull_market (중기 강세장)**
   - 금리 안정 또는 완만한 인하
   - 대다수 섹터 강세
   - 성장주 주도 상승

3. **late_bull_market (후기 강세장)**
   - 금리 상승 우려
   - 업종별 차별화
   - 가치주 선호

4. **bear_market (약세장)**
   - 금리 급등
   - 대다수 섹터 하락
   - 방어주 선호

5. **consolidation (횡보장)**
   - 방향성 불명확
   - 섹터별 엇갈린 성과
   - 변동성 확대

다음 JSON 형식으로 답변하세요:
{{
  "cycle": "시장 사이클 (위 5가지 중 1개)",
  "confidence": 0.0-1.0 (신뢰도),
  "summary": "한 줄 요약 (40자 이내)",
  "key_factors": ["주요 근거1", "주요 근거2", "주요 근거3"]
}}"""

        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        analysis = parse_llm_json(response.content)

        logger.info(f"✅ [Quantitative/MarketCycle] 시장 사이클: {analysis['cycle']} (신뢰도: {analysis['confidence']:.0%})")

        return {
            "market_outlook": analysis,
            "messages": [AIMessage(content=f"시장 사이클 분석 완료: {analysis['cycle']}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/MarketCycle] 분석 실패: {e}", exc_info=True)

        # Fallback: 섹터 성과 기반 간단 판단
        try:
            from src.services.sector_data_service import sector_data_service
            sector_ranking = await sector_data_service.get_sector_ranking(days=30)
            top_sectors_positive = sum(1 for s in sector_ranking[:5] if s['return'] > 0)

            if top_sectors_positive >= 4:
                cycle = "mid_bull_market"
            elif top_sectors_positive >= 3:
                cycle = "early_bull_market"
            elif top_sectors_positive <= 1:
                cycle = "bear_market"
            else:
                cycle = "consolidation"

            fallback_analysis = {
                "cycle": cycle,
                "confidence": 0.6,
                "summary": f"상위 5개 섹터 중 {top_sectors_positive}개 상승",
                "key_factors": ["섹터 성과 기반 판단"]
            }

            return {
                "market_outlook": fallback_analysis,
                "messages": [AIMessage(content=f"시장 사이클 분석 (Fallback): {cycle}")]
            }
        except Exception as fallback_error:
            logger.error(f"❌ [Quantitative/MarketCycle] Fallback 실패: {fallback_error}")
            return {
                "messages": [AIMessage(content=f"시장 사이클 분석 실패: {e}")]
            }


async def sector_allocation_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    섹터 로테이션 전략 (sector_rotator.py 로직 이식)

    시장 사이클별 유망 섹터 선정 및 비중 배분
    """
    market_outlook = state.get("market_outlook", {})
    market_cycle = market_outlook.get("cycle", "consolidation")

    logger.info(f"🎯 [Quantitative/SectorAllocation] 섹터 전략 수립 시작 (시장: {market_cycle})")

    try:
        from src.services.sector_data_service import sector_data_service

        # 1. 섹터 성과 데이터 수집
        sector_performance = await sector_data_service.get_sector_performance(days=30)

        # 2. LLM 기반 섹터 비중 결정
        llm = get_llm(max_tokens=2000, temperature=0.1)

        # 섹터 성과 요약
        perf_summary = []
        for sector, data in sector_performance.items():
            perf_summary.append(f"- {sector}: {data['return']:+.1f}%")

        # 사용자 선호 섹터 (user_profile에서 추출 가능)
        user_profile = state.get("user_profile", {})
        preferred_sectors = user_profile.get("preferred_sectors", [])
        pref_str = f"사용자 선호 섹터: {', '.join(preferred_sectors)}" if preferred_sectors else "없음"

        prompt = f"""당신은 자산 배분 전문가입니다. 다음 정보를 바탕으로 섹터별 투자 비중을 결정하세요.

## 시장 상황
- 시장 사이클: {market_cycle}
- {pref_str}

## 섹터 성과 (최근 30일)
{chr(10).join(perf_summary)}

## 요구사항
1. 10개 섹터에 총 100% 비중 배분
2. 단일 섹터 최대 40% 제한
3. 모멘텀 강한 섹터 overweight
4. 약한 섹터 underweight
5. 사용자 선호 섹터 우대 (있는 경우)

다음 JSON 형식으로 답변:
{{
  "allocations": [
    {{"sector": "IT/전기전자", "weight": 0.35, "stance": "overweight"}},
    ...
  ],
  "overweight": ["섹터1", "섹터2"],
  "underweight": ["섹터3", "섹터4"],
  "rationale": "전략 근거 (50자 이내)"
}}

**중요**: weight 합계는 정확히 1.0이어야 합니다."""

        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        result = parse_llm_json(response.content)

        logger.info(f"✅ [Quantitative/SectorAllocation] Overweight: {', '.join(result['overweight'])}")

        return {
            "sector_strategy": {
                "sectors": result["allocations"],
                "overweight": result["overweight"],
                "underweight": result["underweight"],
                "rationale": result["rationale"]
            },
            "messages": [AIMessage(content=f"섹터 전략 수립 완료: {result['rationale']}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/SectorAllocation] 전략 수립 실패: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"섹터 전략 수립 실패: {e}")]
        }


async def asset_allocation_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    자산 배분 결정 (risk_stance.py 로직 이식)

    시장 상황 × 리스크 허용도 기반 주식/현금 비율 결정
    """
    market_outlook = state.get("market_outlook", {})
    market_cycle = market_outlook.get("cycle", "consolidation")

    # 사용자 프로파일에서 리스크 허용도 추출
    user_profile = state.get("user_profile", {})
    risk_tolerance = user_profile.get("risk_tolerance", "moderate")

    logger.info(f"💰 [Quantitative/AssetAllocation] 자산 배분 시작 (시장: {market_cycle}, 리스크: {risk_tolerance})")

    try:
        # 1. KOSPI 변동성 계산
        from src.services.stock_data_service import stock_data_service

        # 서비스 계층은 지수명을 KOSPI/KOSDAQ 등으로 받아들이므로 KS11 대신 KOSPI로 요청한다.
        df = await stock_data_service.get_market_index("KOSPI", days=60)

        volatility_index = None
        if df is not None and len(df) >= 20:
            returns = df["Close"].pct_change().dropna()
            daily_volatility = returns.std()
            annual_volatility = daily_volatility * (252 ** 0.5)
            volatility_index = float(annual_volatility * 100)
            logger.info(f"📊 [Quantitative/AssetAllocation] KOSPI 변동성: {volatility_index:.2f}%")
        else:
            logger.warning("⚠️ [Quantitative/AssetAllocation] KOSPI 데이터 부족, 변동성 기본값 사용")
            volatility_index = 20.0  # 기본값

        # 2. LLM 기반 자산 배분
        llm = get_llm(max_tokens=1000, temperature=0.1)

        prompt = f"""당신은 자산 배분 전문가입니다. 다음 정보를 바탕으로 주식/현금 비율을 결정하세요.

## 상황
- 시장 사이클: {market_cycle}
- 리스크 허용도: {risk_tolerance}
- KOSPI 변동성: {volatility_index:.2f}% (연환산)

## 요구사항
1. 주식 비중 20% ~ 95% 범위
2. 변동성 높을수록 현금 비중 증가
3. 리스크 허용도 반영
   - conservative: 보수적 배분
   - moderate: 균형 배분
   - aggressive: 공격적 배분

다음 JSON 형식으로 답변:
{{
  "stocks": 0.75,
  "cash": 0.25,
  "rationale": "배분 근거 (50자 이내)"
}}

**중요**: stocks + cash = 1.0"""

        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        result = parse_llm_json(response.content)

        # 범위 검증
        equity_weight = max(0.20, min(0.95, result["stocks"]))
        cash_weight = 1.0 - equity_weight

        logger.info(f"✅ [Quantitative/AssetAllocation] 주식 {equity_weight:.0%}, 현금 {cash_weight:.0%}")

        return {
            "asset_allocation": {
                "stocks": equity_weight,
                "cash": cash_weight,
                "rationale": result["rationale"]
            },
            "messages": [AIMessage(content=f"자산 배분 완료: 주식 {equity_weight:.0%}, 현금 {cash_weight:.0%}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/AssetAllocation] 배분 실패: {e}", exc_info=True)

        # Fallback: 균형 배분
        return {
            "asset_allocation": {
                "stocks": 0.60,
                "cash": 0.40,
                "rationale": f"분석 실패, 기본 배분 적용: {e}"
            },
            "messages": [AIMessage(content=f"자산 배분 (Fallback): 주식 60%, 현금 40%")]
        }


# ==================== 전략 세분화 노드 (Strategy Agent Specialists 이식) ====================

async def buy_decision_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    매수 점수 산정 (Buy Specialist 로직 이식)

    펀더멘털/기술적 분석 기반 1-10점 매수 점수 산정
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    fundamental_analysis = state.get("fundamental_analysis", {})
    technical_analysis = state.get("technical_analysis", {})
    market_outlook = state.get("market_outlook", {})
    sector_strategy = state.get("sector_strategy", {})

    logger.info(f"💰 [Quantitative/BuyDecision] 매수 점수 산정 시작: {stock_code}")

    try:
        llm = get_llm(temperature=0, max_tokens=1500)

        # 프롬프트 생성
        from src.prompts.quantitative.buy_decision import build_buy_decision_prompt

        prompt = build_buy_decision_prompt(
            stock_code=stock_code,
            query=state.get("query"),
            fundamental_analysis=fundamental_analysis,
            technical_analysis=technical_analysis,
            market_outlook=market_outlook,
            sector_strategy=sector_strategy,
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        result = parse_llm_json(response.content)

        buy_score = result.get("buy_score", 5)
        score_reason = result.get("score_reason", "분석 결과")

        logger.info(f"✅ [Quantitative/BuyDecision] 매수 점수: {buy_score}점")

        return {
            "buy_analysis": result,
            "messages": [AIMessage(content=f"매수 점수: {buy_score}점\n이유: {score_reason}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/BuyDecision] 실패: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"매수 점수 산정 실패: {e}")]
        }


async def sell_decision_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    매도 판단 (Sell Specialist 로직 이식)

    익절/손절/홀드 판단
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    fundamental_analysis = state.get("fundamental_analysis", {})
    technical_analysis = state.get("technical_analysis", {})
    market_outlook = state.get("market_outlook", {})

    logger.info(f"📤 [Quantitative/SellDecision] 매도 판단 시작: {stock_code}")

    try:
        llm = get_llm(temperature=0, max_tokens=1500)

        # 프롬프트 생성
        from src.prompts.quantitative.sell_decision import build_sell_decision_prompt

        prompt = build_sell_decision_prompt(
            stock_code=stock_code,
            query=state.get("query"),
            fundamental_analysis=fundamental_analysis,
            technical_analysis=technical_analysis,
            market_outlook=market_outlook,
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        result = parse_llm_json(response.content)

        decision = result.get("decision", "홀드")
        decision_reason = result.get("decision_reason", "분석 결과")

        logger.info(f"✅ [Quantitative/SellDecision] 매도 판단: {decision}")

        return {
            "sell_decision": result,
            "messages": [AIMessage(content=f"매도 판단: {decision}\n이유: {decision_reason}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/SellDecision] 실패: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"매도 판단 실패: {e}")]
        }


async def risk_reward_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    손절가/목표가 계산 (Risk/Reward Specialist 로직 이식)

    Risk/Reward Ratio 기반 가격대 설정
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    fundamental_analysis = state.get("fundamental_analysis", {})
    technical_analysis = state.get("technical_analysis", {})
    user_profile = state.get("user_profile", {})

    logger.info(f"⚖️ [Quantitative/RiskReward] 손절가/목표가 계산 시작: {stock_code}")

    try:
        llm = get_llm(temperature=0, max_tokens=1500)

        # 프롬프트 생성
        from src.prompts.quantitative.risk_reward import build_risk_reward_prompt

        # 현재가 추출 (technical_indicators 또는 valuation_metrics에서)
        current_price = None
        technical_indicators = state.get("technical_indicators", {})
        if technical_indicators and "current_price" in technical_indicators:
            current_price = technical_indicators["current_price"]

        # 변동성 추출
        volatility = technical_indicators.get("volatility") if technical_indicators else None

        prompt = build_risk_reward_prompt(
            stock_code=stock_code,
            query=state.get("query"),
            fundamental_analysis=fundamental_analysis,
            technical_analysis=technical_analysis,
            current_price=current_price,
            volatility=volatility,
            user_profile=user_profile,
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts.utils import parse_llm_json
        result = parse_llm_json(response.content)

        stop_loss_price = result.get("stop_loss_price", 0)
        risk_reward_ratio = result.get("risk_reward_ratio", "N/A")

        logger.info(f"✅ [Quantitative/RiskReward] 손절가: {stop_loss_price:,.0f}원, R/R: {risk_reward_ratio}")

        return {
            "risk_reward": result,
            "messages": [AIMessage(content=f"손절가: {stop_loss_price:,.0f}원, Risk/Reward: {risk_reward_ratio}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/RiskReward] 실패: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"손절가/목표가 계산 실패: {e}")]
        }


async def blueprint_creation_node(state: QuantitativeState) -> Dict[str, Any]:
    """
    Strategic Blueprint 생성

    모든 분석 결과를 통합하여 종합 투자 Blueprint 생성
    """
    if state.get("error"):
        return {}

    stock_code = state.get("stock_code")
    logger.info(f"📋 [Quantitative/Blueprint] Blueprint 생성 시작: {stock_code}")

    try:
        # 모든 분석 결과 수집
        market_outlook = state.get("market_outlook", {})
        sector_strategy = state.get("sector_strategy", {})
        asset_allocation = state.get("asset_allocation", {})
        fundamental_analysis = state.get("fundamental_analysis", {})
        technical_analysis = state.get("technical_analysis", {})
        buy_analysis = state.get("buy_analysis", {})
        sell_decision = state.get("sell_decision", {})
        risk_reward = state.get("risk_reward", {})
        strategy = state.get("strategy", {})

        # 사용자 프로파일
        user_profile = state.get("user_profile", {})
        risk_tolerance = user_profile.get("risk_tolerance", "moderate")

        # 투자 스타일 결정
        investment_style = {
            "type": user_profile.get("style", "balanced"),
            "horizon": strategy.get("time_horizon", "중기"),
            "approach": "분석 기반 투자",
        }

        # 제약 조건 (개별 종목)
        constraints = {
            "max_position_size": 0.20,  # 단일 종목 최대 20%
            "stop_loss_required": True,
            "rebalance_threshold": 0.05,  # 5% 이탈 시 재검토
        }

        # 신뢰도 종합
        confidence_scores = [
            market_outlook.get("confidence", 0.75),
            buy_analysis.get("confidence", 0.75),
            sell_decision.get("confidence", 0.75),
            risk_reward.get("confidence", 0.75),
        ]
        overall_confidence = sum(confidence_scores) / len(confidence_scores)

        # 주요 가정
        key_assumptions = [
            f"시장 사이클: {market_outlook.get('cycle', 'N/A')}",
            f"펀더멘털 점수: {fundamental_analysis.get('overall_score', 'N/A')}",
            f"기술적 시그널: {technical_analysis.get('signal', 'N/A')}",
        ]

        # Blueprint 구성
        blueprint = {
            "stock_code": stock_code,
            "market_context": {
                "market_cycle": market_outlook.get("cycle"),
                "overweight_sectors": sector_strategy.get("overweight", []),
                "stock_ratio": asset_allocation.get("stocks"),
            },
            "analysis_summary": {
                "fundamental_score": fundamental_analysis.get("overall_score"),
                "technical_signal": technical_analysis.get("signal"),
                "buy_score": buy_analysis.get("buy_score"),
                "sell_decision": sell_decision.get("decision"),
            },
            "investment_guidance": {
                "action": strategy.get("action"),
                "confidence": strategy.get("confidence"),
                "target_price": risk_reward.get("final_target_price"),
                "stop_loss": risk_reward.get("stop_loss_price"),
                "time_horizon": strategy.get("time_horizon"),
            },
            "investment_style": investment_style,
            "risk_tolerance": risk_tolerance,
            "constraints": constraints,
            "overall_confidence": overall_confidence,
            "key_assumptions": key_assumptions,
        }

        # 간단한 Dashboard 생성 (LLM 사용)
        llm = get_llm(temperature=0.3, max_tokens=2000)

        target_price = risk_reward.get("final_target_price", "N/A")
        stop_loss_price = risk_reward.get("stop_loss_price", "N/A")
        target_price_display = (
            f"{target_price:,.0f}원" if isinstance(target_price, (int, float)) else str(target_price)
        )
        stop_loss_display = (
            f"{stop_loss_price:,.0f}원" if isinstance(stop_loss_price, (int, float)) else str(stop_loss_price)
        )

        dashboard_prompt = f"""당신은 투자 분석 리포트 작성 전문가입니다. 다음 분석 결과를 바탕으로 간결한 투자 Blueprint를 작성하세요.

## 종목: {stock_code}

### 시장 환경
- 시장 사이클: {market_outlook.get('cycle', 'N/A')}
- 추천 주식 비중: {asset_allocation.get('stocks', 0):.0%}
- Overweight 섹터: {', '.join(sector_strategy.get('overweight', [])[:3])}

### 분석 결과
- 펀더멘털 점수: {fundamental_analysis.get('overall_score', 'N/A')}
- 기술적 신호: {technical_analysis.get('signal', 'N/A')}
- 매수 점수: {buy_analysis.get('buy_score', 'N/A')}/10
- 매도 판단: {sell_decision.get('decision', 'N/A')}

### 투자 가이드
- 전략: {strategy.get('action', 'N/A').upper()}
- 신뢰도: {strategy.get('confidence', 'N/A')}%
- 목표가: {target_price_display}
- 손절가: {stop_loss_display}

다음 마크다운 형식으로 200-300자 요약을 작성하세요:

# {stock_code} 투자 Blueprint

## 종합 의견
[전략과 신뢰도를 포함한 한 줄 요약]

## 핵심 포인트
- [강점 1개]
- [리스크 1개]
- [실행 가이드 1개]

**Overall Confidence**: {overall_confidence:.0%}"""

        response = await llm.ainvoke(dashboard_prompt)
        dashboard_content = response.content

        logger.info(f"✅ [Quantitative/Blueprint] Blueprint 생성 완료 (신뢰도: {overall_confidence:.0%})")

        return {
            "blueprint": blueprint,
            "messages": [AIMessage(content=f"📋 {stock_code} Blueprint 생성 완료\n\n{dashboard_content}")]
        }

    except Exception as e:
        logger.error(f"❌ [Quantitative/Blueprint] 실패: {e}", exc_info=True)

        # Fallback: 간단한 요약
        fallback_blueprint = {
            "stock_code": stock_code,
            "error": str(e),
            "summary": f"Blueprint 생성 중 오류 발생: {e}"
        }

        return {
            "blueprint": fallback_blueprint,
            "messages": [AIMessage(content=f"Blueprint 생성 실패: {e}")]
        }

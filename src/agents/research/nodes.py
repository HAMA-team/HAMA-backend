"""
Research Agent 노드 함수들

Langgraph 서브그래프 노드 구현
"""
import asyncio
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage

from src.config.settings import settings
from src.utils.llm_factory import get_llm
from src.utils.json_parser import safe_json_parse
from src.utils.indicators import calculate_all_indicators
from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service

from .state import ResearchState

logger = logging.getLogger(__name__)


# ==================== Data Collection Node ====================

async def collect_data_node(state: ResearchState) -> ResearchState:
    """
    1단계: 데이터 수집 노드

    실제 데이터 서비스 직접 호출:
    - 주가 데이터 (FinanceDataReader)
    - 재무제표 (DART)
    - 기업 정보 (DART)

    Legacy data_collection_agent 제거됨
    """
    stock_code = state.get("stock_code")
    request_id = state.get("request_id", "supervisor-call")

    # 종목 코드 추출 (query 또는 messages에서)
    if not stock_code:
        query_candidates = []
        if state.get("query"):
            query_candidates.append(state["query"])
        for message in state.get("messages", []):
            if isinstance(message, HumanMessage):
                query_candidates.append(message.content)

        pattern = re.compile(r"\b(\d{6})\b")
        for text in query_candidates:
            if not text:
                continue
            match = pattern.search(text)
            if match:
                stock_code = match.group(1)
                break

    stock_code = stock_code or "005930"

    logger.info(f"📊 [Research/Collect] 데이터 수집 시작: {stock_code}")

    try:
        # 1. 주가 데이터 (FinanceDataReader)
        price_df = await stock_data_service.get_stock_price(stock_code, days=30)
        if price_df is None or len(price_df) == 0:
            raise RuntimeError(f"주가 데이터 조회 실패: {stock_code}")

        price_data = {
            "stock_code": stock_code,
            "days": len(price_df),
            "prices": price_df.reset_index().to_dict("records"),
            "latest_close": float(price_df.iloc[-1]["Close"]),
            "latest_volume": int(price_df.iloc[-1]["Volume"]),
            "source": "FinanceDataReader"
        }

        # 2. 종목코드 → 고유번호 변환
        corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            logger.warning(f"⚠️ 고유번호 찾기 실패: {stock_code}, DART 데이터 스킵")
            financial_data = None
            company_data = None
        else:
            logger.info(f"✅ 고유번호 찾기 성공: {stock_code} -> {corp_code}")

            # 3. 재무제표 데이터 (DART)
            financial_statements = await dart_service.get_financial_statement(
                corp_code, bsns_year="2023"
            )
            financial_data = {
                "stock_code": stock_code,
                "corp_code": corp_code,
                "year": "2023",
                "statements": financial_statements or {},
                "source": "DART"
            }

            # 4. 기업 정보 (DART)
            company_info = await dart_service.get_company_info(corp_code)
            company_data = {
                "stock_code": stock_code,
                "corp_code": corp_code,
                "info": company_info or {},
                "source": "DART"
            }

        # 5. 기술적 지표 계산
        technical_indicators = calculate_all_indicators(price_df)

        # 6. 펀더멘털 데이터 수집 (PER, PBR, EPS 등)
        fundamental_data = await stock_data_service.get_fundamental_data(stock_code)

        # 7. 시가총액 및 거래 데이터 수집
        market_cap_data = await stock_data_service.get_market_cap_data(stock_code)

        # 8. 투자주체별 매매 동향 수집
        investor_trading_data = await stock_data_service.get_investor_trading(stock_code, days=30)

        # 9. 시장 지수 데이터 수집 (KOSPI) - Mock 데이터 포함
        try:
            market_df = await stock_data_service.get_market_index("KOSPI", days=30)
            market_data = {
                "index": "KOSPI",
                "current": float(market_df.iloc[-1]["Close"]) if market_df is not None and len(market_df) > 0 else None,
                "change": float(market_df.iloc[-1]["Close"] - market_df.iloc[-2]["Close"]) if market_df is not None and len(market_df) > 1 else None,
                "change_rate": float((market_df.iloc[-1]["Close"] / market_df.iloc[-2]["Close"] - 1) * 100) if market_df is not None and len(market_df) > 1 else None,
            }
        except Exception as e:
            logger.warning(f"⚠️ [Research/Collect] 시장 지수 데이터 수집 실패: {e}")
            market_data = {"index": "KOSPI", "current": None, "change": None, "change_rate": None}

        logger.info(f"✅ [Research/Collect] 데이터 수집 완료 (펀더멘털 + 기술적 지표 + 투자주체)")

        return {
            "stock_code": stock_code,
            "price_data": price_data,
            "financial_data": financial_data,
            "company_data": company_data,
            "market_index_data": market_data,
            "fundamental_data": fundamental_data,
            "market_cap_data": market_cap_data,
            "investor_trading_data": investor_trading_data,
            "technical_indicators": technical_indicators,
        }

    except Exception as e:
        logger.error(f"❌ [Research/Collect] 에러: {e}")
        return {
            "error": str(e)
        }


# ==================== Analysis Nodes ====================

async def bull_analyst_node(state: ResearchState) -> ResearchState:
    """
    2단계: 강세 분석 노드 (병렬 실행)

    LLM을 사용하여 긍정적 시나리오 분석
    """
    if state.get("error"):
        return state

    logger.info(f"🐂 [Research/Bull] 강세 분석 시작")

    llm = get_llm(
        max_tokens=2000,
        temperature=0.3
    )

    technical = state.get('technical_indicators') or {}
    market = state.get('market_index_data') or {}
    fundamental = state.get('fundamental_data') or {}
    market_cap = state.get('market_cap_data') or {}
    investor = state.get('investor_trading_data') or {}

    prompt = f"""당신은 낙관적 주식 애널리스트입니다. 다음 데이터를 분석하여 **긍정적 시나리오**를 제시하세요.

## 종목 정보
- 종목코드: {state['stock_code']}
- 기업명: {state.get('company_data', {}).get('corp_name', 'N/A')}
- 시가총액: {market_cap.get('market_cap', 0) / 1e12:.2f}조원 (대형주/중소형주 고려)

## 주가 데이터
- 현재가: {state.get('price_data', {}).get('latest_close', 0):,.0f}원
- 최근 거래량: {state.get('price_data', {}).get('latest_volume', 0):,.0f}주

## 펀더멘털 지표 (중요!)
- PER: {fundamental.get('PER', 'N/A')}배 (저평가/고평가 판단)
- PBR: {fundamental.get('PBR', 'N/A')}배
- EPS: {fundamental.get('EPS', 'N/A')}원
- 배당수익률: {fundamental.get('DIV', 'N/A')}%

## 투자주체별 매매 동향
- 외국인 순매수: {investor.get('foreign_net', 'N/A'):,}원 ({investor.get('foreign_trend', 'N/A')})
- 기관 순매수: {investor.get('institution_net', 'N/A'):,}원 ({investor.get('institution_trend', 'N/A')})

## 기술적 지표
{json.dumps(technical, ensure_ascii=False, indent=2) if technical else '기술적 지표 없음'}

## 시장 환경
- KOSPI 현재: {market.get('current') if market.get('current') is not None else 'N/A'} ({(market.get('change_rate') or 0):.2f}%)

## 재무 데이터
{json.dumps(state.get('financial_data'), ensure_ascii=False, indent=2) if state.get('financial_data') else '재무제표 없음'}

**강세 관점에서 분석:**
1. 긍정적 요인 3가지 (펀더멘털 + 기술적 지표 + 투자주체 동향 포함)
2. 목표가 (현재가 대비 상승 전망, PER/PBR 고려)
3. 신뢰도 (1-5)

JSON 형식으로:
{{
  "positive_factors": ["요인1", "요인2", "요인3"],
  "target_price": 목표가(숫자),
  "confidence": 1-5
}}
"""

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            content = response.content

            logger.debug(
                f"📝 [Research/Bull] LLM 응답 미리보기 (preview={content[:200]!r})"
            )

            # 안전한 JSON 파싱
            analysis = safe_json_parse(content, "Research/Bull")
            logger.info(f"✅ [Research/Bull] 강세 분석 완료")

            return {
                "bull_analysis": analysis,
            }
        except Exception as e:
            logger.error(f"❌ [Research/Bull] LLM 호출 실패 (시도 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                logger.info("   2초 대기 후 재시도...")
                await asyncio.sleep(2)
                continue

            raise RuntimeError(f"강세 분석 실패: {e}") from e


async def bear_analyst_node(state: ResearchState) -> ResearchState:
    """
    2단계: 약세 분석 노드 (병렬 실행)

    LLM을 사용하여 부정적 시나리오 분석
    """
    if state.get("error"):
        return state

    logger.info(f"🐻 [Research/Bear] 약세 분석 시작")

    llm = get_llm(
        max_tokens=2000,
        temperature=0.3
    )

    technical = state.get('technical_indicators') or {}
    market = state.get('market_index_data') or {}
    fundamental = state.get('fundamental_data') or {}
    market_cap = state.get('market_cap_data') or {}
    investor = state.get('investor_trading_data') or {}

    prompt = f"""당신은 보수적 주식 애널리스트입니다. 다음 데이터를 분석하여 **부정적 시나리오**를 제시하세요.

## 종목 정보
- 종목코드: {state['stock_code']}
- 기업명: {state.get('company_data', {}).get('corp_name', 'N/A')}
- 시가총액: {market_cap.get('market_cap', 0) / 1e12:.2f}조원

## 주가 데이터
- 현재가: {state.get('price_data', {}).get('latest_close', 0):,.0f}원
- 최근 거래량: {state.get('price_data', {}).get('latest_volume', 0):,.0f}주

## 펀더멘털 지표 (중요!)
- PER: {fundamental.get('PER', 'N/A')}배 (고평가 위험 고려)
- PBR: {fundamental.get('PBR', 'N/A')}배
- EPS: {fundamental.get('EPS', 'N/A')}원
- 배당수익률: {fundamental.get('DIV', 'N/A')}%

## 투자주체별 매매 동향
- 외국인 순매수: {investor.get('foreign_net', 'N/A'):,}원 ({investor.get('foreign_trend', 'N/A')})
- 기관 순매수: {investor.get('institution_net', 'N/A'):,}원 ({investor.get('institution_trend', 'N/A')})

## 기술적 지표
{json.dumps(technical, ensure_ascii=False, indent=2) if technical else '기술적 지표 없음'}

## 시장 환경
- KOSPI 현재: {market.get('current') if market.get('current') is not None else 'N/A'} ({(market.get('change_rate') or 0):.2f}%)

## 재무 데이터
{json.dumps(state.get('financial_data'), ensure_ascii=False, indent=2) if state.get('financial_data') else '재무제표 없음'}

**약세 관점에서 분석:**
1. 리스크 요인 3가지 (펀더멘털 + 기술적 지표 + 투자주체 동향 포함)
2. 하방 목표가 (PER/PBR 기반 하단 추정)
3. 신뢰도 (1-5)

JSON 형식으로:
{{
  "risk_factors": ["리스크1", "리스크2", "리스크3"],
  "downside_target": 하방목표가(숫자),
  "confidence": 1-5
}}
"""

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            content = response.content

            logger.debug(
                f"📝 [Research/Bear] LLM 응답 미리보기 (preview={content[:200]!r})"
            )

            # 안전한 JSON 파싱
            analysis = safe_json_parse(content, "Research/Bear")
            logger.info(f"✅ [Research/Bear] 약세 분석 완료")

            return {
                "bear_analysis": analysis,
            }
        except Exception as e:
            logger.error(f"❌ [Research/Bear] LLM 호출 실패 (시도 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                logger.info("   2초 대기 후 재시도...")
                await asyncio.sleep(2)
                continue

            raise RuntimeError(f"약세 분석 실패: {e}") from e


# ==================== Consensus Node ====================

async def consensus_node(state: ResearchState) -> ResearchState:
    """
    3단계: 합의 노드

    Bull/Bear 분석을 통합하여 최종 투자 의견 도출
    - 펀더멘털 지표 (PER/PBR) 반영
    - 투자주체별 매매 동향 반영
    - 기술적 지표 반영
    """
    if state.get("error"):
        return state

    logger.info(f"🤝 [Research/Consensus] 최종 의견 통합 시작")

    bull = state.get("bull_analysis") or {}
    bear = state.get("bear_analysis") or {}
    price_data = state.get('price_data') or {}
    current_price = price_data.get('latest_close', 0) if price_data else 0
    technical = state.get('technical_indicators') or {}
    fundamental = state.get('fundamental_data') or {}
    investor = state.get('investor_trading_data') or {}
    market_cap = state.get('market_cap_data') or {}

    # 목표가 계산 (Bull/Bear 가중 평균)
    bull_target = bull.get("target_price", current_price * 1.1)
    bear_target = bear.get("downside_target", current_price * 0.95)
    bull_conf = bull.get("confidence", 3)
    bear_conf = bear.get("confidence", 3)

    # 기술적 지표에 따른 가중치 조정
    tech_trend = technical.get("overall_trend", "중립")
    if tech_trend == "강세":
        bull_conf = min(bull_conf + 1, 5)  # 강세 신뢰도 증가
    elif tech_trend == "약세":
        bear_conf = min(bear_conf + 1, 5)  # 약세 신뢰도 증가

    # 펀더멘털 지표에 따른 가중치 조정
    per = fundamental.get("PER")
    pbr = fundamental.get("PBR")

    valuation_status = "적정"
    if per is not None and pbr is not None:
        # 고평가 판단: PER > 30배 또는 PBR > 3배
        if per > 30 or pbr > 3:
            valuation_status = "고평가"
            bull_conf = max(bull_conf - 1, 1)  # 고평가 시 강세 신뢰도 감소
            bear_conf = min(bear_conf + 1, 5)  # 약세 신뢰도 증가
        # 저평가 판단: PER < 10배 또는 PBR < 1배
        elif per < 10 or pbr < 1:
            valuation_status = "저평가"
            bull_conf = min(bull_conf + 1, 5)  # 저평가 시 강세 신뢰도 증가
            bear_conf = max(bear_conf - 1, 1)  # 약세 신뢰도 감소

    # 투자주체별 매매 동향 반영
    foreign_trend = investor.get("foreign_trend", "보합")
    institution_trend = investor.get("institution_trend", "보합")

    investor_sentiment = "중립"
    if foreign_trend == "매수" and institution_trend == "매수":
        investor_sentiment = "긍정"
        bull_conf = min(bull_conf + 1, 5)  # 외국인+기관 매수 시 강세 신뢰도 증가
    elif foreign_trend == "매도" and institution_trend == "매도":
        investor_sentiment = "부정"
        bear_conf = min(bear_conf + 1, 5)  # 외국인+기관 매도 시 약세 신뢰도 증가

    # 가중 평균 목표가
    total_conf = bull_conf + bear_conf
    target_price = int((bull_target * bull_conf + bear_target * bear_conf) / total_conf)

    # 투자 의견 결정 (기술적 지표 + 펀더멘털 + 투자주체 반영)
    upside = (target_price - current_price) / current_price

    # RSI 과매수/과매도 고려
    rsi_signal = technical.get("rsi", {}).get("signal", "중립")

    # 최종 의견 결정
    if upside > 0.15 and rsi_signal != "과매수" and valuation_status != "고평가":
        recommendation = "BUY"
    elif upside < -0.05 or rsi_signal == "과매수" or valuation_status == "고평가":
        recommendation = "SELL"
    else:
        recommendation = "HOLD"

    # 종합 신뢰도
    confidence = int((bull_conf + bear_conf) / 2)

    # 펀더멘털 요약
    fundamental_summary = {
        "PER": per,
        "PBR": pbr,
        "EPS": fundamental.get("EPS"),
        "DIV": fundamental.get("DIV"),
        "valuation": valuation_status
    }

    # 투자주체 요약
    investor_summary = {
        "foreign_trend": foreign_trend,
        "institution_trend": institution_trend,
        "foreign_net": investor.get("foreign_net"),
        "institution_net": investor.get("institution_net"),
        "sentiment": investor_sentiment
    }

    # 시가총액 정보
    market_cap_trillion = market_cap.get("market_cap", 0) / 1e12 if market_cap.get("market_cap") else None

    consensus = {
        "recommendation": recommendation,
        "target_price": target_price,
        "current_price": int(current_price),
        "upside_potential": f"{upside:.1%}",
        "confidence": confidence,
        "bull_case": bull.get("positive_factors", []),
        "bear_case": bear.get("risk_factors", []),
        "technical_summary": {
            "trend": tech_trend,
            "rsi": rsi_signal,
            "signals": technical.get("signals", [])
        },
        "fundamental_summary": fundamental_summary,
        "investor_summary": investor_summary,
        "market_cap_trillion": market_cap_trillion,
        "summary": (
            f"{state.get('company_data', {}).get('corp_name', state['stock_code'])} - {recommendation} "
            f"(목표가: {target_price:,}원, 펀더멘털: {valuation_status}, 투자주체: {investor_sentiment}, 기술적 추세: {tech_trend})"
        )
    }

    logger.info(f"✅ [Research/Consensus] 최종 의견: {recommendation} (펀더멘털: {valuation_status}, 투자주체: {investor_sentiment})")

    # 메시지 생성 (펀더멘털 + 투자주체 정보 포함)
    per_text = f"PER {per:.1f}배" if per is not None else "PER N/A"
    pbr_text = f"PBR {pbr:.2f}배" if pbr is not None else "PBR N/A"

    message = AIMessage(
        content=(
            f"추천: {recommendation} (목표가 {target_price:,}원, 현재가 {current_price:,}원). "
            f"상승여력 {upside:.1%}, 신뢰도 {confidence}/5. "
            f"펀더멘털: {per_text}, {pbr_text} ({valuation_status}). "
            f"투자주체: 외국인 {foreign_trend}, 기관 {institution_trend}."
        )
    )

    return {
        "consensus": consensus,
        "messages": [message],
    }

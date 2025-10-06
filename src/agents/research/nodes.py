"""
Research Agent 노드 함수들

LangGraph 서브그래프 노드 구현
"""
import json
import logging
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.legacy.data_collection import data_collection_agent
from src.config.settings import settings
from src.schemas.agent import AgentInput

from .state import ResearchState

logger = logging.getLogger(__name__)


# ==================== Data Collection Node ====================

async def collect_data_node(state: ResearchState) -> ResearchState:
    """
    1단계: 데이터 수집 노드

    - 주가 데이터 (FinanceDataReader)
    - 재무제표 (DART)
    - 기업 정보 (DART)
    """
    stock_code = state.get("stock_code")
    request_id = state.get("request_id", "supervisor-call")

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
        # 주가 데이터
        price_input = AgentInput(
            request_id=request_id,
            context={"data_type": "stock_price", "stock_code": stock_code, "days": 30}
        )
        price_result = await data_collection_agent.process(price_input)
        if price_result.status != "success":
            raise RuntimeError(f"주가 데이터 수집 실패: {price_result.message}")

        # 재무제표 데이터
        financial_input = AgentInput(
            request_id=request_id,
            context={"data_type": "financial_statement", "stock_code": stock_code, "year": "2023"}
        )
        financial_result = await data_collection_agent.process(financial_input)
        if financial_result.status != "success":
            raise RuntimeError(f"재무제표 데이터 수집 실패: {financial_result.message}")

        # 기업 정보
        company_input = AgentInput(
            request_id=request_id,
            context={"data_type": "company_info", "stock_code": stock_code}
        )
        company_result = await data_collection_agent.process(company_input)
        if company_result.status != "success":
            raise RuntimeError(f"기업 정보 수집 실패: {company_result.message}")

        logger.info(f"✅ [Research/Collect] 데이터 수집 완료")

        return {
            **state,
            "stock_code": stock_code,
            "price_data": price_result.data,
            "financial_data": financial_result.data,
            "company_data": company_result.data,
        }

    except Exception as e:
        logger.error(f"❌ [Research/Collect] 에러: {e}")
        return {
            **state,
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

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다")

    llm = ChatAnthropic(
        model=settings.CLAUDE_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=2000,
        temperature=0.3
    )

    prompt = f"""당신은 낙관적 주식 애널리스트입니다. 다음 데이터를 분석하여 **긍정적 시나리오**를 제시하세요.

## 종목 정보
- 종목코드: {state['stock_code']}
- 기업명: {state.get('company_data', {}).get('corp_name', 'N/A')}

## 주가 데이터
- 현재가: {state.get('price_data', {}).get('latest_close', 0):,.0f}원
- 최근 거래량: {state.get('price_data', {}).get('latest_volume', 0):,.0f}주

## 재무 데이터
{json.dumps(state.get('financial_data'), ensure_ascii=False, indent=2) if state.get('financial_data') else '재무제표 없음'}

**강세 관점에서 분석:**
1. 긍정적 요인 3가지
2. 목표가 (현재가 대비 상승 전망)
3. 신뢰도 (1-5)

JSON 형식으로:
{{
  "positive_factors": ["요인1", "요인2", "요인3"],
  "target_price": 목표가(숫자),
  "confidence": 1-5
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
        else:
            json_str = content.strip()

        analysis = json.loads(json_str)
        logger.info(f"✅ [Research/Bull] 강세 분석 완료")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "bull_analysis": analysis,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"❌ [Research/Bull] LLM 호출 실패: {e}")
        raise RuntimeError(f"강세 분석 실패: {e}") from e


async def bear_analyst_node(state: ResearchState) -> ResearchState:
    """
    2단계: 약세 분석 노드 (병렬 실행)

    LLM을 사용하여 부정적 시나리오 분석
    """
    if state.get("error"):
        return state

    logger.info(f"🐻 [Research/Bear] 약세 분석 시작")

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다")

    llm = ChatAnthropic(
        model=settings.CLAUDE_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=2000,
        temperature=0.3
    )

    prompt = f"""당신은 보수적 주식 애널리스트입니다. 다음 데이터를 분석하여 **부정적 시나리오**를 제시하세요.

## 종목 정보
- 종목코드: {state['stock_code']}
- 기업명: {state.get('company_data', {}).get('corp_name', 'N/A')}

## 주가 데이터
- 현재가: {state.get('price_data', {}).get('latest_close', 0):,.0f}원
- 최근 거래량: {state.get('price_data', {}).get('latest_volume', 0):,.0f}주

## 재무 데이터
{json.dumps(state.get('financial_data'), ensure_ascii=False, indent=2) if state.get('financial_data') else '재무제표 없음'}

**약세 관점에서 분석:**
1. 리스크 요인 3가지
2. 하방 목표가
3. 신뢰도 (1-5)

JSON 형식으로:
{{
  "risk_factors": ["리스크1", "리스크2", "리스크3"],
  "downside_target": 하방목표가(숫자),
  "confidence": 1-5
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
        else:
            json_str = content.strip()

        analysis = json.loads(json_str)
        logger.info(f"✅ [Research/Bear] 약세 분석 완료")

        # Supervisor 호환성: messages 전파
        messages = list(state.get("messages", []))

        return {
            "bear_analysis": analysis,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"❌ [Research/Bear] LLM 호출 실패: {e}")
        raise RuntimeError(f"약세 분석 실패: {e}") from e


# ==================== Consensus Node ====================

async def consensus_node(state: ResearchState) -> ResearchState:
    """
    3단계: 합의 노드

    Bull/Bear 분석을 통합하여 최종 투자 의견 도출
    """
    if state.get("error"):
        return state

    logger.info(f"🤝 [Research/Consensus] 최종 의견 통합 시작")

    bull = state.get("bull_analysis", {})
    bear = state.get("bear_analysis", {})
    current_price = state.get('price_data', {}).get('latest_close', 0)

    # 목표가 계산 (Bull/Bear 가중 평균)
    bull_target = bull.get("target_price", current_price * 1.1)
    bear_target = bear.get("downside_target", current_price * 0.95)
    bull_conf = bull.get("confidence", 3)
    bear_conf = bear.get("confidence", 3)

    # 가중 평균 목표가
    total_conf = bull_conf + bear_conf
    target_price = int((bull_target * bull_conf + bear_target * bear_conf) / total_conf)

    # 투자 의견 결정
    upside = (target_price - current_price) / current_price
    if upside > 0.15:
        recommendation = "BUY"
    elif upside < -0.05:
        recommendation = "SELL"
    else:
        recommendation = "HOLD"

    # 종합 신뢰도
    confidence = int((bull_conf + bear_conf) / 2)

    consensus = {
        "recommendation": recommendation,
        "target_price": target_price,
        "current_price": int(current_price),
        "upside_potential": f"{upside:.1%}",
        "confidence": confidence,
        "bull_case": bull.get("positive_factors", []),
        "bear_case": bear.get("risk_factors", []),
        "summary": f"{state.get('company_data', {}).get('corp_name', state['stock_code'])} - {recommendation} (목표가: {target_price:,}원)"
    }

    logger.info(f"✅ [Research/Consensus] 최종 의견: {recommendation}")

    messages = list(state.get("messages", []))
    messages.append(
        AIMessage(
            content=(
                f"추천: {recommendation} (목표가 {target_price:,}원, 현재가 {current_price:,}원). "
                f"상승여력 {upside:.1%}, 신뢰도 {confidence}/5."
            )
        )
    )

    return {
        **state,
        "consensus": consensus,
        "messages": messages,
    }

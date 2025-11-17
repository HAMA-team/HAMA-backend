"""
Research Agent 전용 프롬프트 모음
"""
from typing import Any, Dict, List, Optional
import json

from ..utils import build_prompt


def build_bull_case_prompt(
    stock_code: str,
    corp_name: str,
    industry: str,
    price_snapshot: Dict[str, Any],
    market_cap_snapshot: Dict[str, Any],
    fundamental: Dict[str, Any],
    technical: Dict[str, Any],
    market_index: Dict[str, Any],
    financial_year: Optional[str],
    user_query: Optional[str] = None,
) -> str:
    context = {
        "종목코드": stock_code,
        "기업명": corp_name,
        "업종": industry or "N/A",
    }

    input_data = _compose_data_sections(
        {
            "user_query": user_query or "사용자 쿼리 없음",
            "price": price_snapshot,
            "market_cap": market_cap_snapshot,
            "fundamental": fundamental,
            "technical": technical,
            "market_index": market_index,
            "financial_year": financial_year,
        }
    )

    task = """제공된 데이터를 바탕으로 강세(낙관적) 시나리오를 작성하세요.

<requirements>
1. positive_factors는 최소 3개, 구체적 수치/사건 포함
2. target_price는 수치 또는 null, 근거 부족 시 notes에 이유 명시
3. confidence는 1~5 정수
4. 데이터가 부족하면 해당 필드를 null로 두고 notes에 "데이터 부족" 사유를 기록
5. 응답은 반드시 '{'로 시작하는 순수 JSON으로만 제공
</requirements>"""

    output_format = """{
  "positive_factors": ["강세 근거"],
  "target_price": 목표가 또는 null,
  "confidence": 1-5,
  "notes": ["추가 설명 또는 데이터 부족 사유"]
}"""

    guidelines = """1. 목표가는 100원 단위 반올림을 권장합니다.
2. 확신이 낮으면 confidence를 1~2로 설정하고 이유를 notes에 추가하세요.
3. JSON 외 텍스트를 추가하지 마세요."""

    return build_prompt(
        role="강세 시나리오 전문 애널리스트",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
        guidelines=guidelines,
    )


def build_bear_case_prompt(
    stock_code: str,
    corp_name: str,
    industry: str,
    price_snapshot: Dict[str, Any],
    market_cap_snapshot: Dict[str, Any],
    fundamental: Dict[str, Any],
    technical: Dict[str, Any],
    market_index: Dict[str, Any],
    financial_year: Optional[str],
    user_query: Optional[str] = None,
) -> str:
    context = {
        "종목코드": stock_code,
        "기업명": corp_name,
        "업종": industry or "N/A",
    }

    input_data = _compose_data_sections(
        {
            "user_query": user_query or "사용자 쿼리 없음",
            "price": price_snapshot,
            "market_cap": market_cap_snapshot,
            "fundamental": fundamental,
            "technical": technical,
            "market_index": market_index,
            "financial_year": financial_year,
        }
    )

    task = """제공된 데이터를 바탕으로 약세/리스크 시나리오를 작성하세요.

<requirements>
1. risk_factors는 최소 3개, 리스크 발생 조건을 구체적으로 적시
2. downside_target은 수치 또는 null, 추정 불가 시 notes에 이유 기재
3. confidence는 1~5 정수
4. 데이터가 부족하면 해당 필드를 null로 두고 notes에 "데이터 부족" 사유를 기록
5. 응답은 반드시 '{'로 시작하는 순수 JSON으로만 제공
</requirements>"""

    output_format = """{
  "risk_factors": ["리스크"],
  "downside_target": 하락목표 또는 null,
  "confidence": 1-5,
  "notes": ["추가 설명 또는 데이터 부족 사유"]
}"""

    guidelines = """1. downside_target 계산 근거가 약하면 confidence를 낮추고 notes에 불확실성을 명시하세요.
2. JSON 외 텍스트를 금지합니다."""

    return build_prompt(
        role="보수적 주식 애널리스트",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
        guidelines=guidelines,
    )


def build_macro_impact_prompt(
    stock_code: str,
    company_name: str,
    macro_data: Dict[str, Any],
) -> str:
    context = {
        "종목코드": stock_code,
        "기업명": company_name,
    }

    input_data = _compose_data_sections({"macro": macro_data})

    task = """거시경제 지표가 해당 기업에 미치는 영향을 평가하세요.

<requirements>
1. 금리/물가/환율 각각에 대해 영향과 이유를 제시
2. 데이터가 없으면 impact를 "데이터없음"으로 설정하고 reason에 설명
3. overall_macro_sentiment는 긍정적/부정적/중립 중 하나
4. 응답은 JSON만 가능하며 '{'로 시작해야 합니다.
</requirements>"""

    output_format = """{
  "interest_rate_impact": "긍정적" | "부정적" | "중립" | "데이터없음",
  "interest_rate_reason": "이유",
  "inflation_impact": "긍정적" | "부정적" | "중립" | "데이터없음",
  "inflation_reason": "이유",
  "exchange_rate_impact": "긍정적" | "부정적" | "중립" | "데이터없음",
  "exchange_rate_reason": "이유",
  "overall_macro_sentiment": "긍정적" | "부정적" | "중립",
  "summary": "한 줄 요약"
}"""

    return build_prompt(
        role="거시경제 전문 애널리스트",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
    )


def build_research_technical_prompt(
    stock_code: str,
    price_data: Dict[str, Any],
    technical_indicators: Dict[str, Any],
) -> str:
    context = {
        "종목코드": stock_code,
        "현재가": price_data.get("latest_close"),
        "거래량": price_data.get("latest_volume"),
    }

    input_data = _compose_data_sections(
        {"price": price_data, "technical": technical_indicators}
    )

    task = """기술적 지표를 기반으로 상세 분석을 제공하세요.

분석 항목:
- 추세, 이평선, 지지/저항선, 거래량 패턴, RSI/MACD/볼린저밴드 해석, 1~2주 전망

지침:
1. 분석 불가 시 해당 필드를 null로 두고 short_term_outlook에 "데이터 부족" 명시
2. confidence는 1~5 정수
3. JSON 외 텍스트 금지, 반드시 '{'로 시작"""

    output_format = """{
  "trend": "상승추세" | "하락추세" | "횡보" | "데이터없음",
  "trend_strength": 1-5,
  "moving_average_analysis": {
    "arrangement": "정배열" | "역배열" | "혼재" | "데이터없음",
    "golden_cross": true | false,
    "death_cross": true | false,
    "ma5": 값 또는 null,
    "ma20": 값 또는 null,
    "ma60": 값 또는 null
  },
  "support_resistance": {
    "support_levels": [값 또는 null],
    "resistance_levels": [값 또는 null]
  },
  "volume_pattern": {
    "trend": "증가" | "감소" | "보합" | "데이터없음",
    "price_volume_relationship": "설명"
  },
  "technical_signals": {
    "rsi_signal": "과매수" | "과매도" | "중립" | "데이터없음",
    "macd_signal": "매수" | "매도" | "중립" | "데이터없음",
    "bollinger_signal": "상단돌파" | "하단돌파" | "중립" | "데이터없음"
  },
  "short_term_outlook": "1-2주 전망",
  "trading_strategy": "기술적 관점 매매 전략",
  "confidence": 1-5
}"""

    return build_prompt(
        role="기술적 분석 전문가",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
    )


def build_trading_flow_prompt(
    stock_code: str,
    price_data: Dict[str, Any],
    investor_data: Dict[str, Any],
) -> str:
    context = {
        "종목코드": stock_code,
        "현재가": price_data.get("latest_close"),
    }

    input_data = _compose_data_sections({"investor_flow": investor_data})

    task = """투자 주체별 거래 동향을 분석하고 수급 전망을 제시하세요.

<requirements>
1. 외국인/기관/개인 각각의 추세, 강도, 상관관계를 서술
2. 데이터가 없으면 trend를 "데이터없음"으로 설정하고 analysis에 사유 명시
3. supply_demand_analysis에는 leading_investor, supply_strength, outlook, forecast 네 값을 포함
4. 응답은 반드시 '{'로 시작하는 JSON이어야 합니다.
</requirements>"""

    output_format = """{
  "foreign_investor": {
    "trend": "순매수" | "순매도" | "보합" | "데이터없음",
    "strength": 1-5,
    "correlation_with_price": "양의 상관관계" | "음의 상관관계" | "무관" | "데이터없음",
    "net_amount": 값 또는 null,
    "analysis": "상세 설명"
  },
  "institutional_investor": {
    "trend": "순매수" | "순매도" | "보합" | "데이터없음",
    "strength": 1-5,
    "correlation_with_price": "양의 상관관계" | "음의 상관관계" | "무관" | "데이터없음",
    "net_amount": 값 또는 null,
    "analysis": "상세 설명"
  },
  "individual_investor": {
    "trend": "순매수" | "순매도" | "보합" | "데이터없음",
    "opposite_trading": true | false | null,
    "analysis": "상세 설명"
  },
  "supply_demand_analysis": {
    "leading_investor": "외국인" | "기관" | "개인" | "혼재" | "데이터없음",
    "supply_strength": "강함" | "약함" | "보통" | "데이터없음",
    "outlook": "긍정적" | "부정적" | "중립" | "데이터없음",
    "forecast": "향후 수급 전망"
  },
  "confidence": 1-5
}"""

    return build_prompt(
        role="거래 동향 분석 전문가",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
    )


def build_information_prompt(
    stock_code: str,
    company_info: Dict[str, Any],
    price_snapshot: Dict[str, Any],
    fundamental_data: Dict[str, Any],
    technical_indicators: Dict[str, Any],
    macro_summary: Dict[str, Any],
    user_query: Optional[str] = None,
    news_data: Optional[List[Dict[str, Any]]] = None,
) -> str:
    context = {
        "종목코드": stock_code,
        "기업명": company_info.get("corp_name", "알 수 없음"),
        "사용자 질의": user_query or "정보 요약 요청",
    }

    input_data = _compose_data_sections(
        {
            "company": company_info,
            "price": price_snapshot,
            "fundamental": fundamental_data,
            "technical": technical_indicators,
            "macro": macro_summary,
            "news": news_data if news_data else [],
        }
    )

    task = """주어진 데이터를 기반으로 정보/뉴스 관점의 정성적 분석을 작성하세요.

<requirements>
1. 시장/기업 센티먼트를 "긍정적/부정적/중립/데이터없음" 중 하나로 정리하고 근거를 서술하세요.
2. 리스크 레벨을 "낮음/보통/높음" 중 하나로 분류하고, 변화를 이끄는 요인을 적으세요.
3. positive_factors, negative_factors, key_themes는 각각 최소 2개씩 제시하세요. 데이터가 부족하면 "데이터 부족"으로 명시하세요.
4. summary에는 전체 요약 문장을 넣고, analysis에는 2-3줄 상세 설명을 포함하세요.
5. 반드시 JSON만, '{'로 시작하는 형식을 유지하세요.
</requirements>"""

    output_format = """{
  "market_sentiment": "긍정적" | "부정적" | "중립" | "데이터없음",
  "sentiment_reason": "간단한 이유",
  "risk_level": "낮음" | "보통" | "높음",
  "risk_drivers": ["리스크 요인"],
  "positive_factors": ["강점", "..."],
  "negative_factors": ["약점", "..."],
  "key_themes": ["키워드1", "키워드2"],
  "summary": "3줄 요약",
  "analysis": "2-3줄 상세 설명"
}"""

    guidelines = """1. 데이터를 명시적으로 언급하면서 요약하세요. 2. 숫자/지표를 사용할 수 없으면 '데이터 부족'을 재확인하세요. 3. JSON 외 텍스트는 추가하지 마세요."""

    return build_prompt(
        role="정보 분석 전문가",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
        guidelines=guidelines,
    )


def _compose_data_sections(sections: Dict[str, Any]) -> str:
    blocks = []
    for key, value in sections.items():
        if value in (None, "", {}):
            blocks.append(f"<{key}>데이터 없음</{key}>")
        else:
            blocks.append(
                f"<{key}>\n{json.dumps(value, ensure_ascii=False, indent=2, default=str)}\n</{key}>"
            )
    return "\n\n".join(blocks)

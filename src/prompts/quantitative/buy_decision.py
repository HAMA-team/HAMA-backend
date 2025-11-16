"""
Buy Decision Prompt (Quantitative용)

매수 점수 산정 프롬프트
"""
from typing import Optional, Dict, Any
from src.prompts.utils import build_prompt


def build_buy_decision_prompt(
    stock_code: str,
    query: Optional[str] = None,
    fundamental_analysis: Optional[Dict] = None,
    technical_analysis: Optional[Dict] = None,
    market_outlook: Optional[Dict] = None,
    sector_strategy: Optional[Dict] = None,
) -> str:
    """
    매수 점수 산정 프롬프트 생성

    Args:
        stock_code: 종목 코드
        query: 사용자 쿼리
        fundamental_analysis: 펀더멘털 분석 결과
        technical_analysis: 기술적 분석 결과
        market_outlook: 시장 전망
        sector_strategy: 섹터 전략

    Returns:
        Claude 프롬프트
    """
    context = {"stock_code": stock_code}

    # 펀더멘털 분석 요약
    if fundamental_analysis:
        context["fundamental_score"] = fundamental_analysis.get("overall_score", "N/A")
        context["valuation_assessment"] = fundamental_analysis.get("valuation_assessment", "N/A")

    # 기술적 분석 요약
    if technical_analysis:
        context["technical_signal"] = technical_analysis.get("signal", "N/A")
        context["trend_direction"] = technical_analysis.get("trend", {}).get("direction", "N/A")

    # 시장 전망
    if market_outlook:
        context["market_cycle"] = market_outlook.get("cycle", "N/A")
        context["market_confidence"] = market_outlook.get("confidence", "N/A")

    # 섹터 전략
    if sector_strategy:
        context["overweight_sectors"] = ", ".join(sector_strategy.get("overweight", []))
        context["underweight_sectors"] = ", ".join(sector_strategy.get("underweight", []))

    task = f"""<role>당신은 매수 점수를 산정하는 전문가입니다.</role>

<query>{query or f'{stock_code} 매수 점수 산정'}</query>

<instructions>
이미 수행된 펀더멘털 및 기술적 분석을 바탕으로 다음 5가지 기준으로 종합 평가하여 매수 점수(1-10점)를 산정하세요.

<evaluation_criteria>
1. Valuation (가치평가): 펀더멘털 분석 결과 기반
2. Momentum (모멘텀): 기술적 분석 결과 기반
3. Quality (품질): 재무건전성, ROE, 성장성
4. Macro Fit (거시 적합성): 시장 사이클과 섹터 전략 부합도
5. Risk Factors (리스크): 변동성, 업종 리스크, 개별 종목 리스크
</evaluation_criteria>

<scoring_guide>
9-10점: 강력 매수 (Strong Buy) - 모든 기준 우수
7-8점: 매수 (Buy) - 긍정적 전망
5-6점: 보유 (Hold) - 중립적 입장
3-4점: 비중 축소 (Reduce) - 부정적 요소 다수
1-2점: 매도 (Sell) - 투자 부적합
</scoring_guide>

<thinking_process>
1. 펀더멘털 분석 결과를 Valuation/Quality 점수로 변환
2. 기술적 분석 결과를 Momentum 점수로 변환
3. 시장 사이클과 섹터 전략 부합도로 Macro Fit 점수 산정
4. 변동성 및 리스크 요인으로 Risk 점수 산정
5. 가중평균하여 종합 매수 점수 계산
6. 강점과 우려사항 구체적으로 식별
</thinking_process>
</instructions>"""

    output_format = """{
  "buy_score": 8,
  "score_reason": "펀더멘털 우수(90점), 기술적 매수 시그널 포착. 시장 사이클 확장기에 진입하였으며, overweight 섹터 포함.",
  "valuation_score": 9,
  "momentum_score": 8,
  "quality_score": 9,
  "macro_fit_score": 8,
  "risk_score": 7,
  "key_strengths": [
    "펀더멘털 종합 점수 90점으로 우수",
    "기술적 매수 시그널 발생",
    "시장 사이클 확장기, overweight 섹터 포함"
  ],
  "key_concerns": [
    "단기 변동성 확대 우려",
    "섹터 내 경쟁 심화"
  ],
  "confidence": 0.85
}"""

    examples = [
        {
            "input": "삼성전자 매수 점수",
            "output": """{
  "buy_score": 7,
  "score_reason": "펀더멘털 양호(75점), 기술적 중립. 반도체 업황 회복기 진입.",
  "valuation_score": 8,
  "momentum_score": 5,
  "quality_score": 9,
  "macro_fit_score": 7,
  "risk_score": 7,
  "key_strengths": ["글로벌 1위 반도체 기업", "재무건전성 최상위"],
  "key_concerns": ["단기 실적 부진", "중국 경기 둔화"],
  "confidence": 0.80
}"""
        }
    ]

    guidelines = """1. 점수 산정 시 객관성 유지 (펀더멘털/기술적 분석 결과 기반)
2. 5가지 평가 기준 모두 고려
3. key_strengths/key_concerns는 구체적 근거 포함
4. confidence는 분석 근거의 확실성 반영 (데이터 충분도)
5. JSON 형식 엄수"""

    return build_prompt(
        role="Buy Decision Specialist - 매수 점수 산정 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

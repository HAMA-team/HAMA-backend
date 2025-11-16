"""
Sell Decision Prompt (Quantitative용)

매도 판단 프롬프트
"""
from typing import Optional, Dict, Any
from src.prompts.utils import build_prompt


def build_sell_decision_prompt(
    stock_code: str,
    query: Optional[str] = None,
    fundamental_analysis: Optional[Dict] = None,
    technical_analysis: Optional[Dict] = None,
    market_outlook: Optional[Dict] = None,
    purchase_price: Optional[float] = None,
    current_price: Optional[float] = None,
) -> str:
    """
    매도 판단 프롬프트 생성

    Args:
        stock_code: 종목 코드
        query: 사용자 쿼리
        fundamental_analysis: 펀더멘털 분석 결과
        technical_analysis: 기술적 분석 결과
        market_outlook: 시장 전망
        purchase_price: 매수가 (옵션)
        current_price: 현재가 (옵션)

    Returns:
        Claude 프롬프트
    """
    context = {"stock_code": stock_code}

    if purchase_price and current_price:
        profit_loss_pct = ((current_price - purchase_price) / purchase_price) * 100
        context["profit_loss"] = f"{profit_loss_pct:+.2f}%"
        context["purchase_price"] = f"{purchase_price:,.0f}원"
        context["current_price"] = f"{current_price:,.0f}원"

    # 펀더멘털 분석 요약
    if fundamental_analysis:
        context["fundamental_score"] = fundamental_analysis.get("overall_score", "N/A")

    # 기술적 분석 요약
    if technical_analysis:
        context["technical_signal"] = technical_analysis.get("signal", "N/A")

    # 시장 전망
    if market_outlook:
        context["market_cycle"] = market_outlook.get("cycle", "N/A")

    task = f"""<role>당신은 매도 판단을 내리는 전문가입니다.</role>

<query>{query or f'{stock_code} 매도 판단'}</query>

<instructions>
이미 수행된 펀더멘털 및 기술적 분석을 바탕으로 다음 기준으로 매도 여부를 판단하세요.

<decision_criteria>
1. 펀더멘털 변화: 분석 점수 추이, 투자 논리 유효성
2. 기술적 신호: 추세 전환, 지지선 이탈, 매도 시그널
3. 시장 환경: 사이클 변화, 섹터 로테이션
4. 수익률 달성도: 목표 수익률 도달 여부 (데이터 있는 경우)
5. 리스크 증가: 변동성 확대, 악재 발생
</decision_criteria>

<decision_options>
- 익절 (Take Profit): 목표가 도달, 과열 신호, 논리 완성
- 손절 (Stop Loss): 펀더멘털 악화, 기술적 추세 전환, 리스크 급증
- 홀드 (Hold): 논리 유효, 추가 상승 여력 존재
</decision_options>

<thinking_process>
1. 펀더멘털 분석 결과 재검토
2. 기술적 분석 신호 확인
3. 시장 환경 평가
4. 매도 결정 및 비율 제안
5. 대안 전략 제시
</thinking_process>
</instructions>"""

    output_format = """{
  "decision": "익절",
  "decision_reason": "펀더멘털 목표 달성, 기술적 과열 신호 포착. 수익 실현 권장.",
  "target_sell_ratio": 0.5,
  "timing": "1-2주 내 분할 매도",
  "alternative_action": "50% 익절 후 나머지는 trailing stop 적용",
  "risk_if_hold": "단기 조정 시 수익률 10%p 감소 우려",
  "confidence": 0.80
}"""

    examples = [
        {
            "input": "삼성전자 매도 판단",
            "output": """{
  "decision": "홀드",
  "decision_reason": "펀더멘털 양호, 기술적 상승 추세 유지. 추가 상승 여력 존재.",
  "target_sell_ratio": 0.0,
  "timing": "목표가 +30% 도달 시",
  "alternative_action": "trailing stop 10% 설정 후 보유",
  "risk_if_hold": "단기 조정 시 수익률 5-7%p 감소 가능",
  "confidence": 0.75
}"""
        },
        {
            "input": "NAVER 손절 판단",
            "output": """{
  "decision": "손절",
  "decision_reason": "펀더멘털 점수 하락(90 → 65), 기술적 지지선 이탈. 추가 하락 우려.",
  "target_sell_ratio": 1.0,
  "timing": "즉시 매도",
  "alternative_action": "손절 후 업종 내 대체 종목 물색",
  "risk_if_hold": "추가 -10% 하락 가능성 높음",
  "confidence": 0.85
}"""
        }
    ]

    guidelines = """1. 감정적 판단 배제, 분석 결과 기반 판단
2. target_sell_ratio: 0.0(전량 보유) ~ 1.0(전량 매도)
3. timing은 구체적으로 (예: "1-2주 내", "즉시")
4. alternative_action으로 유연성 제공
5. risk_if_hold는 정량적으로 제시"""

    return build_prompt(
        role="Sell Decision Specialist - 매도 판단 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

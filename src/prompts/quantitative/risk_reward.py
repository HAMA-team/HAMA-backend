"""
Risk/Reward Prompt (Quantitative용)

손절가/목표가 계산 프롬프트
"""
from typing import Optional, Dict, Any
from src.prompts.utils import build_prompt


def build_risk_reward_prompt(
    stock_code: str,
    query: Optional[str] = None,
    fundamental_analysis: Optional[Dict] = None,
    technical_analysis: Optional[Dict] = None,
    current_price: Optional[float] = None,
    volatility: Optional[float] = None,
    user_profile: Optional[Dict] = None,
) -> str:
    """
    손절가/목표가 계산 프롬프트 생성

    Args:
        stock_code: 종목 코드
        query: 사용자 쿼리
        fundamental_analysis: 펀더멘털 분석 결과
        technical_analysis: 기술적 분석 결과
        current_price: 현재가 (옵션)
        volatility: 변동성 (옵션)
        user_profile: 사용자 프로파일

    Returns:
        Claude 프롬프트
    """
    context = {"stock_code": stock_code}

    if current_price:
        context["current_price"] = f"{current_price:,.0f}원"

    if volatility:
        context["volatility"] = f"{volatility:.2f}%"

    # 사용자 리스크 허용도
    risk_tolerance = "moderate"
    if user_profile:
        risk_tolerance = user_profile.get("risk_tolerance", "moderate")
    context["risk_tolerance"] = risk_tolerance

    # 기술적 지지/저항선
    if technical_analysis:
        support_resistance = technical_analysis.get("support_resistance", {})
        if support_resistance:
            context["support_levels"] = str(support_resistance.get("support", []))
            context["resistance_levels"] = str(support_resistance.get("resistance", []))

    task = f"""<role>당신은 손절가와 목표가를 계산하는 전문가입니다.</role>

<query>{query or f'{stock_code} 손절가/목표가 계산'}</query>

<instructions>
이미 수행된 펀더멘털 및 기술적 분석을 바탕으로 손절가와 목표가를 계산하여 Risk/Reward 비율을 제시하세요.

<calculation_factors>
1. 기술적 분석: 지지선/저항선, 추세, 모멘텀
2. 변동성: 일일 변동폭, ATR (제공된 경우)
3. Risk/Reward Ratio: 최소 1:2 이상 권장
4. 사용자 리스크 허용도: {risk_tolerance}
5. 펀더멘털 신뢰도: 분석 점수 기반
</calculation_factors>

<stop_loss_guide>
- conservative: -5% ~ -7%
- moderate: -8% ~ -12%
- aggressive: -15% ~ -20%

단, 기술적 지지선이 있다면 우선 고려
</stop_loss_guide>

<target_price_guide>
- 1차 목표: Risk/Reward 1:2 (단기)
- 2차 목표: Risk/Reward 1:3 (중기)
- 최종 목표: 기술적 저항선 돌파 (장기)

펀더멘털 점수가 높을수록 공격적 목표가 설정
</target_price_guide>

<thinking_process>
1. 현재가와 주요 지지/저항선 확인
2. 리스크 허용도 기반 손절가 범위 산정
3. 펀더멘털 점수 고려하여 목표가 계산
4. Risk/Reward 1:2 이상 보장 확인
5. 단계별 익절 전략 수립
6. 100원 단위 반올림 (심리가 고려)
</thinking_process>
</instructions>"""

    output_format = """{
  "stop_loss_price": 48000,
  "stop_loss_pct": -8.5,
  "stop_loss_reason": "주요 지지선 50,000원 이탈 시 추가 하락 우려",
  "target_price_1": 60000,
  "target_price_1_pct": 14.3,
  "target_price_2": 68000,
  "target_price_2_pct": 29.5,
  "final_target_price": 75000,
  "final_target_pct": 42.9,
  "risk_reward_ratio": "1:2.5",
  "strategy": "1차 목표가 도달 시 30% 익절, 2차 목표가 도달 시 추가 40% 익절, trailing stop 10% 적용",
  "confidence": 0.80
}"""

    examples = [
        {
            "input": "삼성전자 손절가/목표가",
            "output": """{
  "stop_loss_price": 63000,
  "stop_loss_pct": -10.0,
  "stop_loss_reason": "200일 이동평균선 65,000원 이탈 시 추세 전환",
  "target_price_1": 77000,
  "target_price_1_pct": 10.0,
  "target_price_2": 84000,
  "target_price_2_pct": 20.0,
  "final_target_price": 91000,
  "final_target_pct": 30.0,
  "risk_reward_ratio": "1:3",
  "strategy": "trailing stop 7% 설정, 1차 목표가 도달 시 50% 익절",
  "confidence": 0.75
}"""
        }
    ]

    guidelines = """1. 가격은 100원 단위로 반올림 (심리적 가격대 고려)
2. Risk/Reward Ratio는 최소 1:2 이상
3. stop_loss_reason은 기술적 근거 명시 (지지선, 이동평균선 등)
4. strategy는 구체적 실행 계획 (분할 매도 비율 포함)
5. 변동성 고려하여 너무 타이트한 손절가 지양"""

    return build_prompt(
        role="Risk/Reward Specialist - 손절가/목표가 계산 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

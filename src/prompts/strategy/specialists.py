"""
Strategy Agent Specialist 프롬프트

Buy, Sell, Risk/Reward Specialist용 Claude 4.x 프롬프트
"""
from typing import Optional, Dict, Any
from ..utils import build_prompt


def build_buy_specialist_prompt(
    query: str,
    stock_code: Optional[str] = None,
    market_outlook: Optional[Dict] = None,
    sector_strategy: Optional[Dict] = None,
    current_price: Optional[float] = None,
    fundamental_data: Optional[Dict] = None,
) -> str:
    """
    Buy Specialist 프롬프트 (매수 점수 산정)

    Args:
        query: 사용자 쿼리
        stock_code: 종목 코드
        market_outlook: 시장 전망 (옵션)
        sector_strategy: 섹터 전략 (옵션)
        current_price: 현재가 (옵션)
        fundamental_data: 펀더멘털 데이터 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {}

    if market_outlook:
        context["market_cycle"] = market_outlook.get("cycle", "expansion")
        context["market_confidence"] = market_outlook.get("confidence", 0.75)

    if sector_strategy:
        context["overweight_sectors"] = sector_strategy.get("overweight", [])
        context["underweight_sectors"] = sector_strategy.get("underweight", [])

    if stock_code:
        context["stock_code"] = stock_code

    if current_price:
        context["current_price"] = f"{current_price:,.0f}원"

    if fundamental_data:
        context["fundamental"] = fundamental_data

    task = f"""<role>당신은 매수 점수를 산정하는 전문가입니다.</role>

<query>{query}</query>

<instructions>
다음 5가지 기준으로 종합 평가하여 매수 점수(1-10점)를 산정하세요.

<evaluation_criteria>
1. Valuation (가치평가): PER, PBR, 업종 대비 밸류에이션
2. Momentum (모멘텀): 주가 추세, 거래량, 기술적 지표
3. Quality (품질): ROE, 재무건전성, 성장성
4. Macro Fit (거시 적합성): 시장 사이클과 섹터 전략 부합도
5. Risk Factors (리스크): 업종 리스크, 개별 종목 리스크
</evaluation_criteria>

<scoring_guide>
9-10점: 강력 매수 (Strong Buy) - 모든 기준 우수
7-8점: 매수 (Buy) - 긍정적 전망
5-6점: 보유 (Hold) - 중립적 입장
3-4점: 비중 축소 (Reduce) - 부정적 요소 다수
1-2점: 매도 (Sell) - 투자 부적합
</scoring_guide>

<thinking_process>
1. 각 기준별 점수 산정 (1-10점)
2. 강점과 우려사항 구체적으로 식별
3. 종합 점수 계산 (가중평균)
4. 확신도 평가 (데이터 충분성)
</thinking_process>
</instructions>"""

    output_format = """{
  "buy_score": 8,
  "score_reason": "시장 사이클 확장기에 진입하였으며, IT 섹터 overweight 전략과 부합. PER 15배로 업종 평균 대비 저평가, 최근 거래량 급증으로 모멘텀 강세.",
  "valuation_score": 8,
  "momentum_score": 9,
  "quality_score": 7,
  "macro_fit_score": 9,
  "risk_score": 7,
  "key_strengths": [
    "업종 대비 저평가 (PER 15배 vs 업종 평균 20배)",
    "최근 3개월 거래량 200% 증가",
    "ROE 18%로 업종 최상위권"
  ],
  "key_concerns": [
    "단기 과열 우려 (RSI 75)",
    "외국인 매도세 지속"
  ],
  "confidence": 0.85
}"""

    examples = [
        {
            "input": "삼성전자 지금 사도 될까요?",
            "output": """{
  "buy_score": 7,
  "score_reason": "반도체 업황 회복기 진입, 밸류에이션 매력적. 다만 단기 모멘텀은 약세.",
  "valuation_score": 8,
  "momentum_score": 5,
  "quality_score": 9,
  "macro_fit_score": 7,
  "risk_score": 7,
  "key_strengths": ["글로벌 1위 반도체 기업", "PBR 1.2배 저평가"],
  "key_concerns": ["단기 실적 부진", "중국 경기 둔화"],
  "confidence": 0.80
}"""
        },
        {
            "input": "NAVER 매수 타이밍인가요?",
            "output": """{
  "buy_score": 5,
  "score_reason": "플랫폼 안정적이나 성장 동력 약화. 현 시점 중립 입장.",
  "valuation_score": 6,
  "momentum_score": 4,
  "quality_score": 7,
  "macro_fit_score": 5,
  "risk_score": 6,
  "key_strengths": ["안정적 광고 매출", "LINE 일본 시장 장악"],
  "key_concerns": ["성장률 둔화", "AI 경쟁 심화"],
  "confidence": 0.75
}"""
        }
    ]

    guidelines = """1. 점수 산정 시 객관성 유지 (데이터 기반)
2. 5가지 평가 기준 모두 고려
3. key_strengths/key_concerns는 구체적 수치 포함
4. confidence는 분석 근거의 확실성 반영 (데이터 충분도)
5. JSON 형식 엄수"""

    return build_prompt(
        role="Buy Specialist - 매수 점수 산정 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_sell_specialist_prompt(
    query: str,
    stock_code: Optional[str] = None,
    purchase_price: Optional[float] = None,
    current_price: Optional[float] = None,
    holding_period: Optional[int] = None,
    market_outlook: Optional[Dict] = None,
) -> str:
    """
    Sell Specialist 프롬프트 (매도 판단)

    Args:
        query: 사용자 쿼리
        stock_code: 종목 코드
        purchase_price: 매수가 (옵션)
        current_price: 현재가 (옵션)
        holding_period: 보유 기간(일) (옵션)
        market_outlook: 시장 전망 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {}

    if stock_code:
        context["stock_code"] = stock_code

    if purchase_price and current_price:
        profit_loss_pct = ((current_price - purchase_price) / purchase_price) * 100
        context["profit_loss"] = f"{profit_loss_pct:+.2f}%"
        context["purchase_price"] = f"{purchase_price:,.0f}원"
        context["current_price"] = f"{current_price:,.0f}원"

    if holding_period:
        context["holding_period"] = f"{holding_period}일"

    if market_outlook:
        context["market_cycle"] = market_outlook.get("cycle", "expansion")

    task = f"""<role>당신은 매도 판단을 내리는 전문가입니다.</role>

<query>{query}</query>

<instructions>
다음 기준으로 매도 여부를 판단하세요.

<decision_criteria>
1. 수익률 달성도: 목표 수익률 도달 여부
2. 투자 논리: 매수 시점의 논리가 여전히 유효한가?
3. 시장 환경: 사이클 변화, 섹터 로테이션
4. 기술적 신호: 추세 전환, 지지선 이탈
5. 리스크 증가: 펀더멘털 악화, 악재 발생
</decision_criteria>

<decision_options>
- 익절 (Take Profit): 목표가 도달, 논리 완성
- 손절 (Stop Loss): 논리 훼손, 리스크 급증
- 홀드 (Hold): 논리 유효, 추가 상승 여력
</decision_options>

<thinking_process>
1. 현재 수익률 확인
2. 매수 논리 재검토
3. 시장/기술적 환경 평가
4. 매도 결정 및 비율 제안
5. 대안 전략 제시
</thinking_process>
</instructions>"""

    output_format = """{
  "decision": "익절",
  "decision_reason": "목표 수익률 +25% 도달, 업종 과열 신호 포착. 수익 실현 권장.",
  "target_sell_ratio": 0.5,
  "timing": "1-2주 내 분할 매도",
  "alternative_action": "50% 익절 후 나머지는 trailing stop 적용",
  "risk_if_hold": "단기 조정 시 수익률 10%p 감소 우려",
  "confidence": 0.80
}"""

    examples = [
        {
            "input": "삼성전자 20% 올랐는데 팔아야 할까요?",
            "output": """{
  "decision": "홀드",
  "decision_reason": "반도체 업황 회복 초기 단계, 추가 상승 여력 존재",
  "target_sell_ratio": 0.0,
  "timing": "목표가 +30% 도달 시",
  "alternative_action": "trailing stop 10% 설정 후 보유",
  "risk_if_hold": "단기 조정 시 수익률 5-7%p 감소 가능",
  "confidence": 0.75
}"""
        },
        {
            "input": "NAVER -15% 손실인데 손절해야 하나요?",
            "output": """{
  "decision": "손절",
  "decision_reason": "투자 논리(AI 성장) 훼손, 경쟁 심화로 추가 하락 우려",
  "target_sell_ratio": 1.0,
  "timing": "즉시 매도",
  "alternative_action": "손절 후 IT 섹터 내 대체 종목 물색",
  "risk_if_hold": "추가 -10% 하락 가능성 높음",
  "confidence": 0.85
}"""
        }
    ]

    guidelines = """1. 감정적 판단 배제, 데이터 기반 분석
2. target_sell_ratio: 0.0(전량 보유) ~ 1.0(전량 매도)
3. timing은 구체적으로 (예: "1-2주 내", "즉시")
4. alternative_action으로 유연성 제공
5. risk_if_hold는 정량적으로 제시"""

    return build_prompt(
        role="Sell Specialist - 매도 판단 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_risk_reward_specialist_prompt(
    query: str,
    stock_code: Optional[str] = None,
    current_price: Optional[float] = None,
    purchase_price: Optional[float] = None,
    volatility: Optional[float] = None,
) -> str:
    """
    Risk/Reward Specialist 프롬프트 (손절가/목표가 계산)

    Args:
        query: 사용자 쿼리
        stock_code: 종목 코드
        current_price: 현재가 (옵션)
        purchase_price: 매수가 (옵션)
        volatility: 변동성 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {}

    if stock_code:
        context["stock_code"] = stock_code

    if current_price:
        context["current_price"] = f"{current_price:,.0f}원"

    if purchase_price:
        context["purchase_price"] = f"{purchase_price:,.0f}원"

    if volatility:
        context["volatility"] = f"{volatility:.2f}%"

    task = f"""<role>당신은 손절가와 목표가를 계산하는 전문가입니다.</role>

<query>{query}</query>

<instructions>
손절가와 목표가를 계산하여 Risk/Reward 비율을 제시하세요.

<calculation_factors>
1. 기술적 분석: 지지선/저항선, 피보나치, 이동평균선
2. 변동성: ATR, 일일 변동폭
3. Risk/Reward Ratio: 최소 1:2 이상 권장
4. 투자 스타일: 단기/중기/장기
5. 심리적 가격대: 정수가, 52주 고저점
</calculation_factors>

<stop_loss_guide>
- 보수적: -5% ~ -7%
- 중립적: -8% ~ -12%
- 공격적: -15% ~ -20%
</stop_loss_guide>

<target_price_guide>
- 1차 목표: Risk/Reward 1:2
- 2차 목표: Risk/Reward 1:3
- 최종 목표: 기술적 저항선 돌파
</target_price_guide>

<thinking_process>
1. 현재가와 주요 지지/저항선 확인
2. 변동성 기반 손절가 범위 산정
3. Risk/Reward 1:2 이상 목표가 계산
4. 단계별 익절 전략 수립
5. 100원 단위 반올림 (심리가 고려)
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
            "input": "삼성전자 70,000원에 샀는데 손절가 어디로 설정할까요?",
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
3. stop_loss_reason은 기술적 근거 명시
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

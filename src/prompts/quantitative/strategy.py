"""
전략 통합 프롬프트
"""
from typing import Dict, Any

from ..utils import build_prompt


def build_strategy_synthesis_prompt(
    stock_code: str,
    fundamental_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    query: str
) -> str:
    """
    전략 통합 프롬프트 생성

    펀더멘털 + 기술적 분석을 종합하여 투자 전략 제안
    """
    context = {
        "종목코드": stock_code,
        "사용자_질문": query or "사용자 질문 없음",
    }

    input_data = f"""<fundamental_analysis>
{_format_fundamental_analysis(fundamental_analysis)}
</fundamental_analysis>

<technical_analysis>
{_format_technical_analysis(technical_analysis)}
</technical_analysis>"""

    task = """펀더멘털과 기술적 분석 결과를 교차 검증해 투자 전략을 제안하세요.

<strategy_requirements>
1. action은 buy/hold/sell 중 하나, 근거(reasoning)는 200자 이내
2. target_price와 stop_loss는 숫자 또는 null, 데이터 부족 시 null로 설정하고 이유를 key_risks에 기재
3. fundamental_weight와 technical_weight 합은 100이 되도록 설정
4. key_catalysts/risks는 각각 최소 2개, 구체적 이벤트를 포함
5. 응답은 반드시 '{'로 시작하는 순수 JSON만 허용, 설명 금지
</strategy_requirements>"""

    output_format = """{
  "action": "buy" | "hold" | "sell",
  "confidence": 0-100,
  "target_price": 목표가격 또는 null,
  "stop_loss": 손절가격 또는 null,
  "time_horizon": "단기" | "중기" | "장기",
  "reasoning": "전략 근거 (200자 이내)",
  "fundamental_weight": 0-100,
  "technical_weight": 0-100,
  "key_catalysts": ["촉매1", "촉매2"],
  "key_risks": ["리스크1", "리스크2"],
  "fallback_plan": "데이터 부족 시 권장 행동"
}"""

    examples = [
        {
            "input": "Fundamental 강세 + Technical 과열",
            "output": """{
  "action": "hold",
  "confidence": 62,
  "target_price": 87000,
  "stop_loss": 78000,
  "time_horizon": "중기",
  "reasoning": "이익 모멘텀은 견조하나 기술적 과열로 진입가 조정 대기",
  "fundamental_weight": 60,
  "technical_weight": 40,
  "key_catalysts": ["DRAM ASP 상승", "주주환원 확대"],
  "key_risks": ["원/달러 급등", "데이터 부족: 경쟁사 가이던스"],
  "fallback_plan": "80,000원 부근 재진입 또는 과열 해소까지 대기"
}"""
        }
    ]

    guidelines = """1. confidence는 0~100 정수입니다.
2. target_price/stop_loss 계산 근거가 없으면 null로 표시하고 key_risks에 '근거 부족'을 추가하세요.
3. fundamental_weight + technical_weight = 100 규칙을 지키세요."""

    return build_prompt(
        role="한국 주식 투자 전략가",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def _format_fundamental_analysis(data: Dict[str, Any]) -> str:
    """펀더멘털 분석 결과 포맷팅"""
    if not data:
        return "분석 결과 없음"

    overall_score = data.get("overall_score", "N/A")
    strengths = data.get("key_strengths", [])
    risks = data.get("key_risks", [])
    valuation = data.get("valuation", {})

    return "\n".join(
        [
            f"- 종합 점수: {overall_score}",
            f"- 밸류에이션: {valuation.get('current_status', 'N/A')}",
            f"- 주요 강점: {', '.join(strengths) if strengths else '없음'}",
            f"- 주요 리스크: {', '.join(risks) if risks else '없음'}",
        ]
    )


def _format_technical_analysis(data: Dict[str, Any]) -> str:
    """기술적 분석 결과 포맷팅"""
    if not data:
        return "분석 결과 없음"

    overall_score = data.get("overall_score", "N/A")
    trend = data.get("trend", {})
    signal = data.get("signal", {})

    return "\n".join(
        [
            f"- 종합 점수: {overall_score}",
            f"- 추세: {trend.get('direction', 'N/A')} ({trend.get('strength', 'N/A')})",
            f"- 시그널: {signal.get('action', 'N/A')} (신뢰도: {signal.get('confidence', 'N/A')}%)",
        ]
    )

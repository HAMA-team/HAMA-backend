"""
전략 통합 프롬프트
"""
from typing import Dict, Any


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
    return f"""당신은 투자 전략가입니다. {stock_code}에 대한 종합 분석을 바탕으로 투자 전략을 제안하세요.

## 사용자 질문
{query}

## 펀더멘털 분석 결과
{_format_fundamental_analysis(fundamental_analysis)}

## 기술적 분석 결과
{_format_technical_analysis(technical_analysis)}

## 전략 수립 원칙

1. **펀더멘털과 기술적 분석의 조화**: 두 분석이 일치하면 강한 신호
2. **리스크 관리**: 손절/익절 라인 명확히 제시
3. **시간 프레임**: 단기(1주~1개월), 중기(1~6개월), 장기(6개월 이상)
4. **신뢰도**: 분석의 확신 수준을 정직하게 표현

## 출력 형식 (JSON)

```json
{{
  "action": "buy" | "hold" | "sell",
  "confidence": 0-100,
  "target_price": 목표가격 (숫자),
  "stop_loss": 손절가격 (숫자),
  "time_horizon": "단기" | "중기" | "장기",
  "reasoning": "전략 근거 (200자 이내)",
  "fundamental_weight": 0-100,
  "technical_weight": 0-100,
  "key_catalysts": ["촉매1", "촉매2"],
  "key_risks": ["리스크1", "리스크2"]
}}
```

**중요**:
- action은 반드시 "buy", "hold", "sell" 중 하나여야 합니다
- confidence는 0-100 사이의 정수여야 합니다
- 펀더멘털과 기술적 분석이 상충하면 confidence를 낮추세요
"""


def _format_fundamental_analysis(data: Dict[str, Any]) -> str:
    """펀더멘털 분석 결과 포맷팅"""
    if not data:
        return "분석 결과 없음"

    overall_score = data.get("overall_score", "N/A")
    strengths = data.get("key_strengths", [])
    risks = data.get("key_risks", [])
    valuation = data.get("valuation", {})

    formatted = f"""
- 종합 점수: {overall_score}/100
- 밸류에이션: {valuation.get('current_status', 'N/A')}
- 주요 강점: {', '.join(strengths) if strengths else '없음'}
- 주요 리스크: {', '.join(risks) if risks else '없음'}
"""

    return formatted


def _format_technical_analysis(data: Dict[str, Any]) -> str:
    """기술적 분석 결과 포맷팅"""
    if not data:
        return "분석 결과 없음"

    overall_score = data.get("overall_score", "N/A")
    trend = data.get("trend", {})
    signal = data.get("signal", {})

    formatted = f"""
- 종합 점수: {overall_score}/100
- 추세: {trend.get('direction', 'N/A')} ({trend.get('strength', 'N/A')})
- 시그널: {signal.get('action', 'N/A')} (신뢰도: {signal.get('confidence', 'N/A')}%)
"""

    return formatted

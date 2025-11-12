"""
기술적 분석 프롬프트
"""
from typing import Dict, Any


def build_technical_analysis_prompt(
    stock_code: str,
    technical_indicators: Dict[str, Any]
) -> str:
    """
    기술적 분석 프롬프트 생성

    기술적 지표를 기반으로 매매 시그널 분석
    """
    return f"""당신은 전문 기술적 분석가입니다. {stock_code}의 기술적 지표를 분석하세요.

## 제공된 기술적 지표

{_format_technical_indicators(technical_indicators)}

## 분석 항목

1. **추세 분석**: 이동평균선 (5일, 20일, 60일, 120일)
2. **모멘텀**: RSI, MACD, Stochastic
3. **변동성**: Bollinger Bands, ATR
4. **거래량**: 거래량 추이 및 패턴

## 출력 형식 (JSON)

```json
{{
  "trend": {{
    "direction": "상승/하락/횡보",
    "strength": "강함/중간/약함",
    "summary": "추세 요약"
  }},
  "momentum": {{
    "signal": "과매수/중립/과매도",
    "summary": "모멘텀 요약"
  }},
  "support_resistance": {{
    "support": [지지선1, 지지선2],
    "resistance": [저항선1, 저항선2]
  }},
  "signal": {{
    "action": "buy/hold/sell",
    "confidence": 0-100,
    "entry_point": "진입 시점 제안",
    "exit_point": "청산 시점 제안"
  }},
  "overall_score": 0-100
}}
```"""


def _format_technical_indicators(data: Dict[str, Any]) -> str:
    """기술적 지표 포맷팅"""
    if not data:
        return "데이터 없음"

    # 주요 지표 추출
    latest = data.get("latest", {})
    moving_averages = data.get("moving_averages", {})
    rsi = latest.get("rsi")
    macd = latest.get("macd", {})
    bollinger = latest.get("bollinger_bands", {})

    formatted = f"""
### 이동평균선
- MA5: {moving_averages.get('ma5', 'N/A')}
- MA20: {moving_averages.get('ma20', 'N/A')}
- MA60: {moving_averages.get('ma60', 'N/A')}
- MA120: {moving_averages.get('ma120', 'N/A')}

### 모멘텀 지표
- RSI(14): {rsi if rsi else 'N/A'}
"""

    if macd:
        formatted += f"""- MACD: {macd.get('value', 'N/A')}
- Signal: {macd.get('signal', 'N/A')}
- Histogram: {macd.get('histogram', 'N/A')}
"""

    if bollinger:
        formatted += f"""
### Bollinger Bands
- Upper: {bollinger.get('upper', 'N/A')}
- Middle: {bollinger.get('middle', 'N/A')}
- Lower: {bollinger.get('lower', 'N/A')}
"""

    return formatted

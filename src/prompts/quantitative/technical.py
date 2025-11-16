"""
기술적 분석 프롬프트
"""
from typing import Dict, Any

from ..utils import build_prompt


def build_technical_analysis_prompt(
    stock_code: str,
    technical_indicators: Dict[str, Any]
) -> str:
    """
    기술적 분석 프롬프트 생성

    기술적 지표를 기반으로 매매 시그널 분석
    """
    context = {
        "종목코드": stock_code,
        "지표_출처": "pykrx + 커스텀 indicators",
    }

    input_data = _format_technical_indicators(technical_indicators)

    task = """기술적 지표를 검토하여 추세/모멘텀/변동성/거래량을 평가하고 실행 가능한 시그널을 제시하세요.

<analysis_requirements>
1. 이동평균, 모멘텀, 변동성, 거래량, 지지/저항선을 각각 해석
2. 지표가 없거나 계산 실패 시 해당 필드를 null로 두고 이유를 signal.summary에 적시
3. action은 buy/hold/sell 중 하나, confidence는 0~100 정수
4. 응답은 반드시 '{'로 시작하는 순수 JSON으로만 반환
</analysis_requirements>"""

    output_format = """{
  "trend": {
    "direction": "상승/하락/횡보/데이터없음",
    "strength": "강함/중간/약함/데이터없음",
    "summary": "추세 요약"
  },
  "momentum": {
    "signal": "과매수/중립/과매도/데이터없음",
    "summary": "모멘텀 요약"
  },
  "support_resistance": {
    "support": [지지선 혹은 null],
    "resistance": [저항선 혹은 null]
  },
  "signal": {
    "action": "buy/hold/sell",
    "confidence": 0-100,
    "entry_point": "진입 시점 또는 null",
    "exit_point": "청산 시점 또는 null",
    "warnings": ["데이터 부족 시 경고"]
  },
  "overall_score": 0-100
}"""

    examples = [
        {
            "input": "골든크로스 + RSI 72",
            "output": """{
  "trend": {"direction": "상승", "strength": "중간", "summary": "20일선 위에서 정배열 유지"},
  "momentum": {"signal": "과매수", "summary": "RSI 72"},
  "support_resistance": {"support": [72000], "resistance": [78000]},
  "signal": {"action": "hold", "confidence": 63, "entry_point": null, "exit_point": "78,000 돌파 실패 시", "warnings": ["과매수 구간 접근"]},
  "overall_score": 64
}"""
        }
    ]

    guidelines = """1. 분석 가능한 지표가 없으면 전체를 null로 설정하고 warnings에 사유를 기입하세요.
2. 가격대는 100원 단위 반올림을 권장합니다.
3. JSON 이외의 텍스트를 추가하지 마세요."""

    return build_prompt(
        role="한국 주식 기술적 분석가",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def _format_technical_indicators(data: Dict[str, Any]) -> str:
    """기술적 지표 포맷팅"""
    if not data:
        return "<indicators>데이터 없음</indicators>"

    moving_averages = data.get("moving_averages", {})
    latest = data.get("latest", {})
    macd = latest.get("macd", {})
    bollinger = latest.get("bollinger_bands", {})

    return f"""
<moving_averages>
- MA5: {moving_averages.get('ma5', 'N/A')}
- MA20: {moving_averages.get('ma20', 'N/A')}
- MA60: {moving_averages.get('ma60', 'N/A')}
- MA120: {moving_averages.get('ma120', 'N/A')}
</moving_averages>

<momentum>
- RSI(14): {latest.get('rsi', 'N/A')}
- Stochastic: {latest.get('stochastic', 'N/A')}
</momentum>

<macd>
- MACD: {macd.get('value', 'N/A')}
- Signal: {macd.get('signal', 'N/A')}
- Histogram: {macd.get('histogram', 'N/A')}
</macd>

<bollinger>
- Upper: {bollinger.get('upper', 'N/A')}
- Middle: {bollinger.get('middle', 'N/A')}
- Lower: {bollinger.get('lower', 'N/A')}
</bollinger>
"""

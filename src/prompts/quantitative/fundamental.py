"""
펀더멘털 분석 프롬프트
"""
from typing import Dict, Any
from ..utils import build_prompt


def build_fundamental_analysis_prompt(
    stock_code: str,
    financial_statements: Dict[str, Any],
    valuation_metrics: Dict[str, Any]
) -> str:
    """
    펀더멘털 분석 프롬프트 생성

    재무제표와 밸류에이션 지표를 기반으로 기업 가치 평가
    """
    context = {
        "종목코드": stock_code,
        "데이터_출처": "DART, pykrx",
    }

    input_data = f"""<financials>
{_format_financial_statements(financial_statements)}
</financials>

<valuation_metrics>
{_format_valuation_metrics(valuation_metrics)}
</valuation_metrics>"""

    task = """다음 데이터를 활용해 기업의 펀더멘털을 평가하세요.

<analysis_requirements>
1. 재무건전성, 수익성, 성장성, 밸류에이션을 각각 0-100 점수와 요약으로 제시
2. 데이터가 없거나 불확실하면 null을 사용하고 "데이터 부족" 사유를 key_risks에 포함
3. 강점/리스크는 최소 2개 이상, 구체적 수치 또는 연도 언급 권장
4. 추측 금지: 제공되지 않은 데이터에 근거해 숫자를 만들어내지 마세요
5. 응답은 반드시 '{'로 시작하는 순수 JSON이어야 하며 추가 설명을 붙이지 마세요
</analysis_requirements>"""

    output_format = """{
  "financial_health": {
    "score": 0-100,
    "summary": "재무건전성 요약"
  },
  "profitability": {
    "score": 0-100,
    "summary": "수익성 요약"
  },
  "growth": {
    "score": 0-100,
    "summary": "성장성 요약"
  },
  "valuation": {
    "score": 0-100,
    "fair_value": "적정 주가 평가 또는 null",
    "current_status": "할인/적정/프리미엄/데이터없음"
  },
  "overall_score": 0-100,
  "key_strengths": ["강점1", "강점2"],
  "key_risks": ["리스크1", "리스크2"],
  "confidence": 0-100
}"""

    examples = [
        {
            "input": "매출 증가 + PER 12배",
            "output": """{
  "financial_health": {"score": 72, "summary": "부채비율 90%로 안정적"},
  "profitability": {"score": 78, "summary": "ROE 15%로 업종 상위"},
  "growth": {"score": 65, "summary": "3년 매출 CAGR 8%"},
  "valuation": {"score": 60, "fair_value": "82,000", "current_status": "할인"},
  "overall_score": 69,
  "key_strengths": ["현금흐름 플러스", "이익률 회복"],
  "key_risks": ["원자재 가격 상승", "데이터 부족: CAPEX"],
  "confidence": 80
}"""
        }
    ]

    guidelines = """1. 점수는 0~100 범위의 정수로 제한하세요.
2. 데이터가 없으면 해당 필드는 null 또는 "데이터없음"으로 설정하고 이유를 key_risks에 남기세요.
3. confidence는 분석 신뢰도를 0~100 정수로 표현하세요."""

    return build_prompt(
        role="한국 주식 펀더멘털 애널리스트",
        context=context,
        input_data=input_data,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def _format_financial_statements(data: Dict[str, Any]) -> str:
    """재무제표 데이터 포맷팅"""
    if not data:
        return "데이터 없음"

    latest = data.get("latest_quarter", {})

    return "\n".join(
        [
            f"- 매출액: {_fmt_currency(latest.get('revenue'))}",
            f"- 영업이익: {_fmt_currency(latest.get('operating_profit'))}",
            f"- 순이익: {_fmt_currency(latest.get('net_profit'))}",
            f"- 자산총계: {_fmt_currency(latest.get('total_assets'))}",
            f"- 부채총계: {_fmt_currency(latest.get('total_liabilities'))}",
            f"- 자본총계: {_fmt_currency(latest.get('total_equity'))}",
        ]
    )


def _format_valuation_metrics(data: Dict[str, Any]) -> str:
    """밸류에이션 지표 포맷팅"""
    if not data:
        return "데이터 없음"

    return "\n".join(
        [
            f"- PER: {_fmt_value(data.get('per'))}",
            f"- PBR: {_fmt_value(data.get('pbr'))}",
            f"- ROE: {_fmt_value(data.get('roe'))}%",
            f"- 배당수익률: {_fmt_value(data.get('dividend_yield'))}%",
        ]
    )


def _fmt_currency(value: Any) -> str:
    try:
        number = float(str(value).replace(",", ""))
        return f"{number:,.0f}원"
    except Exception:
        return "데이터 없음"


def _fmt_value(value: Any) -> str:
    return "데이터 없음" if value is None else str(value)

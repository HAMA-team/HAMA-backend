"""
펀더멘털 분석 프롬프트
"""
from typing import Dict, Any


def build_fundamental_analysis_prompt(
    stock_code: str,
    financial_statements: Dict[str, Any],
    valuation_metrics: Dict[str, Any]
) -> str:
    """
    펀더멘털 분석 프롬프트 생성

    재무제표와 밸류에이션 지표를 기반으로 기업 가치 평가
    """
    return f"""당신은 전문 증권 애널리스트입니다. {stock_code}의 펀더멘털을 분석하세요.

## 제공된 데이터

### 재무제표
{_format_financial_statements(financial_statements)}

### 밸류에이션 지표
{_format_valuation_metrics(valuation_metrics)}

## 분석 항목

1. **재무건전성**: 부채비율, 유동비율, 이자보상배율
2. **수익성**: ROE, ROA, 영업이익률, 순이익률
3. **성장성**: 매출 성장률, 영업이익 성장률
4. **밸류에이션**: PER, PBR, PSR 적정성 평가

## 출력 형식 (JSON)

```json
{{
  "financial_health": {{
    "score": 0-100,
    "summary": "재무건전성 요약"
  }},
  "profitability": {{
    "score": 0-100,
    "summary": "수익성 요약"
  }},
  "growth": {{
    "score": 0-100,
    "summary": "성장성 요약"
  }},
  "valuation": {{
    "score": 0-100,
    "fair_value": "적정 주가 평가",
    "current_status": "할인/적정/프리미엄"
  }},
  "overall_score": 0-100,
  "key_strengths": ["강점1", "강점2"],
  "key_risks": ["리스크1", "리스크2"]
}}
```"""


def _format_financial_statements(data: Dict[str, Any]) -> str:
    """재무제표 데이터 포맷팅"""
    if not data:
        return "데이터 없음"

    # 최신 분기 데이터 추출
    latest = data.get("latest_quarter", {})

    return f"""
- 매출액: {latest.get('revenue', 'N/A'):,}원
- 영업이익: {latest.get('operating_profit', 'N/A'):,}원
- 순이익: {latest.get('net_profit', 'N/A'):,}원
- 자산총계: {latest.get('total_assets', 'N/A'):,}원
- 부채총계: {latest.get('total_liabilities', 'N/A'):,}원
- 자본총계: {latest.get('total_equity', 'N/A'):,}원
"""


def _format_valuation_metrics(data: Dict[str, Any]) -> str:
    """밸류에이션 지표 포맷팅"""
    if not data:
        return "데이터 없음"

    return f"""
- PER: {data.get('per', 'N/A')}
- PBR: {data.get('pbr', 'N/A')}
- ROE: {data.get('roe', 'N/A')}%
- 배당수익률: {data.get('dividend_yield', 'N/A')}%
"""

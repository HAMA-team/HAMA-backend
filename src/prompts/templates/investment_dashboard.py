"""
META Investment Dashboard Template

사용자 제공 양식 기반 투자 분석 대시보드 템플릿
"""

INVESTMENT_DASHBOARD_TEMPLATE = """
# {stock_name} Investment Dashboard
Last Updated: {date} | Next Earnings: {next_earnings}

🎯 Investment Thesis Scorecard
{scorecard}

📊 Critical Metrics Tracking
{metrics}

🔍 What to Watch Next Quarter
{watch_points}

💭 Investment Decision Framework
{decision_framework}

🚨 Red Flags That Would Change Thesis
{red_flags}
"""


SCORECARD_TEMPLATE = """
| Factor | Status | Trend | Target/Threshold |
|--------|--------|-------|------------------|
{rows}
"""


CRITICAL_METRICS_TEMPLATE = """
**The Big Picture**
- Revenue: {revenue}
- Adj. EPS: {eps}
- Operating Margin: {operating_margin}
- User Growth: {user_growth}

**The Concerns**
{concerns}

**The Positives**
{positives}
"""


DECISION_FRAMEWORK_TEMPLATE = """
**BULLISH Case ({horizon})**
{bullish_points}

**BEARISH Case**
{bearish_points}

**Decision Triggers**
- INCREASE POSITION IF: {increase_conditions}
- REDUCE POSITION IF: {reduce_conditions}
- HOLD IF: {hold_conditions}
"""


def build_dashboard_prompt(
    stock_name: str,
    analysis_results: dict,
) -> str:
    """
    Investment Dashboard 생성을 위한 프롬프트 빌더

    Args:
        stock_name: 종목명
        analysis_results: 분석 결과 딕셔너리
            - bull_analysis: 강세 시나리오
            - bear_analysis: 약세 시나리오
            - technical_analysis: 기술적 분석
            - fundamental_analysis: 재무 분석
            - trading_flow: 수급 분석
            - information: 뉴스/이슈 분석

    Returns:
        Dashboard 생성 프롬프트
    """
    from ..utils import build_prompt, add_formatting_guidelines

    # 분석 결과 정리
    analysis_summary = "\n\n".join([
        f"### {key}\n{value}"
        for key, value in analysis_results.items()
        if value
    ])

    task = f"""다음 분석 결과를 Investment Dashboard 형식으로 정리하세요.

분석 대상: {stock_name}

Dashboard에 포함할 섹션:

1. **Investment Thesis Scorecard**:
   - 주요 투자 팩터 (매출 성장, 수익성, 시장 지위 등)를 표로 정리
   - 각 팩터의 상태 (✅ Strong, ⚠️ Moderate, 🔴 Weak)
   - 트렌드 (↗️ 상승, ↔️ 유지, ↘️ 하락)
   - 목표/임계값

2. **Critical Metrics Tracking**:
   - The Big Picture: 핵심 지표 4-5개 (매출, EPS, 마진, 성장률 등)
   - The Concerns: 우려 사항 3-4개
   - The Positives: 긍정적 요인 3-4개

3. **What to Watch Next Quarter**:
   - 다음 분기 주목할 지표
   - 실적 발표일, 이벤트
   - 핵심 질문들

4. **Investment Decision Framework**:
   - BULLISH Case: 매수 근거 3-4개
   - BEARISH Case: 리스크 요인 3-4개
   - Decision Triggers: 포지션 증가/감소/유지 조건

5. **Red Flags**:
   - 투자 논리를 변경할 수 있는 위험 신호 3-5개
"""

    output_format = INVESTMENT_DASHBOARD_TEMPLATE

    examples = [
        {
            "input": "삼성전자 - 반도체 업황 회복, PER 12배",
            "output": """# 삼성전자 Investment Dashboard

🎯 Investment Thesis Scorecard
| Factor | Status | Trend | Target/Threshold |
|--------|--------|-------|------------------|
| Revenue Growth | ⚠️ Moderate | ↗️ | >15% YoY |
| Operating Margin | ✅ Strong | ↗️ | >35% |
| Market Share | ✅ Leading | ↔️ | Top 2 |

📊 Critical Metrics Tracking
**The Big Picture**
- Revenue: 70조원 (+10% YoY)
- Operating Profit: 25조원 (+35% YoY)
..."""
        }
    ]

    guidelines = add_formatting_guidelines()

    return build_prompt(
        role="한국 주식 시장 투자 분석가",
        context={
            "종목": stock_name,
            "목표": "META Investment Dashboard 양식의 투자 분석 보고서 작성",
        },
        input_data=analysis_summary,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

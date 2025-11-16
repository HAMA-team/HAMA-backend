"""
Integrated Investment Dashboard 템플릿

Research + Strategy 결과를 통합한 최종 투자 리포트
"""
from typing import Dict, Any
from ..utils import build_prompt


INTEGRATED_DASHBOARD_TEMPLATE = """
# 📊 Comprehensive Investment Analysis Report
Generated: {date} | Request ID: {request_id}

---

## 🎯 Executive Summary

{executive_summary}

**Key Recommendation**: {recommendation}
**Confidence Level**: {confidence}%

---

## 📈 Research Analysis Highlights

{research_highlights}

### Investment Thesis Scorecard
{thesis_scorecard}

### Critical Metrics
{critical_metrics}

---

## 🎬 Strategic Blueprint

{strategy_highlights}

### Market Positioning
- **Market Cycle**: {market_cycle}
- **Strategic Stance**: {strategic_stance}
- **Recommended Allocation**: Stocks {stock_ratio}% | Cash {cash_ratio}%

### Sector Strategy
**Overweight**: {overweight_sectors}
**Underweight**: {underweight_sectors}

---

## 💡 Actionable Insights

### Immediate Actions (This Week)
{immediate_actions}

### Short-term Strategy (1-3 Months)
{short_term_strategy}

### Risk Management
{risk_management}

---

## ⚠️ Key Risks & Monitoring Points

{key_risks}

**Red Flags to Watch**:
{red_flags}

---

## 📋 Investment Decision Checklist

- [ ] {checklist_item_1}
- [ ] {checklist_item_2}
- [ ] {checklist_item_3}
- [ ] {checklist_item_4}
- [ ] {checklist_item_5}

---

*This report integrates multi-agent AI analysis. Always conduct your own due diligence before making investment decisions.*
"""


def build_integrated_dashboard_prompt(
    research_result: Dict[str, Any],
    strategy_result: Dict[str, Any],
    query: str,
) -> str:
    """
    Integrated Investment Dashboard 생성 프롬프트

    Args:
        research_result: Research Agent 결과
        strategy_result: Strategy Agent 결과 (Blueprint)
        query: 사용자 쿼리

    Returns:
        Dashboard 생성 프롬프트
    """
    context = {
        "query": query,
        "has_research": bool(research_result),
        "has_strategy": bool(strategy_result),
    }

    # Research 결과 추출
    if research_result:
        context["research_consensus"] = research_result.get("consensus", "NEUTRAL")
        context["research_dashboard"] = research_result.get("dashboard", "")
        context["research_summary"] = research_result.get("summary", "")

    # Strategy 결과 추출
    if strategy_result:
        context["market_cycle"] = strategy_result.get("market_cycle", "expansion")
        context["stock_ratio"] = strategy_result.get("stock_ratio", 0.7)
        context["strategy_dashboard"] = strategy_result.get("dashboard", "")
        context["strategy_summary"] = strategy_result.get("summary", "")

    task = f"""Research Agent와 Strategy Agent의 분석 결과를 통합하여 최종 Investment Dashboard를 생성하세요.

사용자 쿼리: "{query}"

**입력 데이터**:

1. **Research Agent 결과**:
{research_result.get("dashboard", research_result.get("summary", "분석 없음")) if research_result else "Research 분석 없음"}

2. **Strategy Agent 결과**:
{strategy_result.get("dashboard", strategy_result.get("summary", "전략 없음")) if strategy_result else "Strategy 분석 없음"}

**생성 요구사항**:

1. **Executive Summary** (2-3문장):
   - Research와 Strategy의 핵심 메시지 통합
   - 투자자가 5초 안에 이해할 수 있도록 간결하게

2. **Research Analysis Highlights**:
   - Research Dashboard의 핵심 내용 요약
   - Investment Thesis Scorecard 포함
   - Critical Metrics 포함

3. **Strategic Blueprint**:
   - Strategy Dashboard의 핵심 내용 요약
   - Market Positioning, Sector Strategy 포함

4. **Actionable Insights**:
   - 즉시 실행 가능한 액션 아이템 (우선순위별)
   - 단기 전략 (1-3개월)
   - 리스크 관리 방안

5. **Key Risks & Monitoring Points**:
   - Research와 Strategy에서 식별된 주요 리스크 통합
   - Red Flags (전략 변경 트리거)

6. **Investment Decision Checklist**:
   - 투자 실행 전 확인 사항 5개
   - 구체적이고 실행 가능한 항목

**데이터 누락 처리 지침**:
- 특정 섹션에 필요한 데이터가 없으면 "데이터 없음" 또는 null로 표시하고 왜 비어있는지 설명하세요.
- 추측하거나 만들어내지 말고, 부족한 부분은 key_risks 혹은 checklist에 "추가 데이터 필요" 항목으로 명시하세요.
- 응답은 템플릿을 그대로 채우되, 존재하지 않는 정보는 생략하지 말고 명시적으로 비어있음을 알려야 합니다.

**중요 원칙**:
- 두 Agent의 결과가 충돌하면, 그 이유를 명시하고 균형잡힌 시각 제시
- Research는 "종목 분석", Strategy는 "포트폴리오 전략"에 집중
- 모든 권장사항은 구체적 근거 포함
- 과도한 마크다운 포맷 지양 (가독성 우선)"""

    output_format = f"""다음 템플릿을 채워서 반환하세요:

{INTEGRATED_DASHBOARD_TEMPLATE}

**템플릿 변수 설명**:
- {{date}}: 현재 날짜 (YYYY-MM-DD)
- {{request_id}}: 요청 ID
- {{executive_summary}}: 2-3문장 핵심 요약
- {{recommendation}}: "Strong Buy" / "Buy" / "Hold" / "Reduce" / "Sell"
- {{confidence}}: 신뢰도 0-100
- {{research_highlights}}: Research 핵심 내용 (3-4문장)
- {{thesis_scorecard}}: Investment Thesis 점수표
- {{critical_metrics}}: 주요 지표 요약
- {{strategy_highlights}}: Strategy 핵심 내용 (3-4문장)
- {{market_cycle}}: 시장 사이클
- {{strategic_stance}}: 전략적 포지션
- {{stock_ratio}}, {{cash_ratio}}: 자산 배분 비율
- {{overweight_sectors}}, {{underweight_sectors}}: 섹터 전략
- {{immediate_actions}}: 즉시 실행 액션 (불릿 포인트)
- {{short_term_strategy}}: 단기 전략 (불릿 포인트)
- {{risk_management}}: 리스크 관리 (불릿 포인트)
- {{key_risks}}: 주요 리스크 (불릿 포인트)
- {{red_flags}}: 경고 신호 (불릿 포인트)
- {{checklist_item_1-5}}: 체크리스트 항목

**중요**: 모든 변수를 실제 값으로 채워야 합니다."""

    examples = [
        {
            "input": "Research: 삼성전자 강력매수, Strategy: IT overweight",
            "output": """# 📊 Comprehensive Investment Analysis Report
Generated: 2025-01-15 | Request ID: req_001

---

## 🎯 Executive Summary

삼성전자는 반도체 업황 회복과 AI 수요 증가로 강력한 매수 기회를 제공합니다. 현재 시장 사이클(확장기)과 IT 섹터 overweight 전략이 완벽하게 부합하며, PER 15배로 업종 대비 저평가 상태입니다.

**Key Recommendation**: Strong Buy
**Confidence Level**: 85%

---

## 📈 Research Analysis Highlights

삼성전자는 반도체 업황 회복 초입에 진입하였으며, AI 반도체 수요 급증으로 향후 2-3년간 강력한 실적 개선이 예상됩니다. HBM3E 양산 본격화와 파운드리 사업 턴어라운드가 핵심 투자 포인트입니다.

### Investment Thesis Scorecard
- Valuation: 8/10 (PER 15배, 업종 대비 -25%)
- Growth: 9/10 (AI 수요, HBM 독점)
- Quality: 9/10 (글로벌 1위, 기술력)
- Momentum: 7/10 (외국인 순매수 전환)

### Critical Metrics
- Target Price: 90,000원 (+29% upside)
- P/E Ratio: 15x (Sector avg: 20x)
- HBM Market Share: 60%

---

## 🎬 Strategic Blueprint

시장 사이클 확장기 진입과 함께 IT 섹터를 중심으로 공격적 성장 전략을 권장합니다. 주식 비중 70%, IT 섹터 25% 배분으로 업황 회복기 수혜를 극대화합니다.

### Market Positioning
- **Market Cycle**: 확장기 (Expansion)
- **Strategic Stance**: Moderate Bullish
- **Recommended Allocation**: Stocks 70% | Cash 30%

### Sector Strategy
**Overweight**: IT (25%), 금융 (20%), 소비재 (15%)
**Underweight**: 에너지, 소재

---

## 💡 Actionable Insights

### Immediate Actions (This Week)
- 삼성전자 포트폴리오 25% 배분 (분할 매수 시작)
- 목표가 90,000원, 손절가 65,000원 설정
- IT 섹터 ETF 추가 검토

### Short-term Strategy (1-3 Months)
- 1개월: 삼성전자 20% 매수 완료
- 2개월: SK하이닉스 추가 매수 검토
- 3개월: 포트폴리오 리밸런싱 (IT 25% 목표)

### Risk Management
- Trailing stop 10% 설정
- 월 1회 정기 리밸런싱
- HBM 매출 비중 모니터링

---

## ⚠️ Key Risks & Monitoring Points

- 중국 경기 둔화로 인한 반도체 수요 감소
- 미중 기술 분쟁 심화
- 파운드리 사업 턴어라운드 지연

**Red Flags to Watch**:
- HBM 매출 비중 감소
- 외국인 2주 연속 순매도
- KOSPI 200일 이평선 하향 이탈

---

## 📋 Investment Decision Checklist

- [ ] 삼성전자 재무제표 확인 (최근 분기 실적)
- [ ] IT 섹터 비중 25% 이하인지 확인
- [ ] 손절가 65,000원 주문 설정 완료
- [ ] 월 1회 리밸런싱 일정 등록
- [ ] HBM 관련 뉴스 모니터링 설정

---

*This report integrates multi-agent AI analysis. Always conduct your own due diligence before making investment decisions.*"""
        }
    ]

    guidelines = """1. Executive Summary는 반드시 2-3문장으로 제한
2. Research와 Strategy가 충돌하면 명시적으로 언급
3. Actionable Insights는 구체적이고 실행 가능해야 함
4. Checklist는 실제로 확인 가능한 항목만 포함
5. 날짜는 현재 날짜 사용
6. 신뢰도는 두 Agent의 confidence 평균
7. 과도한 emoji 사용 지양 (섹션 제목만)
8. 불릿 포인트는 "-" 사용"""

    return build_prompt(
        role="Integrated Investment Report Generator - Research + Strategy 통합 분석가",
        context=context,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

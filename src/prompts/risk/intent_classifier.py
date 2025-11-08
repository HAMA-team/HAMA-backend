"""
Risk Agent Intent Classifier 프롬프트
"""
from typing import Optional, Dict, List
from ..utils import build_prompt


def build_risk_intent_classifier_prompt(
    query: str,
    user_profile: Optional[Dict] = None,
    portfolio_data: Optional[Dict] = None,
) -> str:
    """
    Risk Agent용 Intent Classifier 프롬프트

    Args:
        query: 사용자 쿼리
        user_profile: 사용자 프로필 (옵션)
        portfolio_data: 포트폴리오 데이터 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {}

    if user_profile:
        context["risk_tolerance"] = user_profile.get("risk_tolerance", "moderate")

    if portfolio_data:
        context["holdings_count"] = len(portfolio_data.get("holdings", []))

    task = f"""사용자 쿼리를 분석하여 리스크 분석 의도를 분류하세요.

쿼리: "{query}"

분류 기준:

**1. Analysis Depth (분석 깊이)**:
- **quick**: 간단한 리스크 점수만 (1-2개 지표)
- **standard**: 표준 리스크 분석 (집중도 + 시장 리스크)
- **comprehensive**: 종합 리스크 분석 (모든 지표 + 시나리오 분석)

**2. Focus Areas (집중 영역)**:
- concentration: 집중도 리스크 (종목, 섹터, 산업 집중)
- market: 시장 리스크 (VaR, 변동성, 베타)
- scenario: 시나리오 분석 (최악의 경우, 스트레스 테스트)

**3. Required Specialists (필요한 Specialist)**:
- concentration_specialist: 집중도 리스크 분석
- market_risk_specialist: 시장 리스크 분석
- scenario_specialist: 시나리오 분석 (comprehensive만)"""

    output_format = """{
  "depth": "standard",
  "focus_areas": ["concentration", "market"],
  "specialists": ["concentration_specialist", "market_risk_specialist"],
  "reasoning": "표준적인 리스크 분석 요청. 집중도와 시장 리스크 분석 필요.",
  "confidence": 0.85
}"""

    examples = [
        {
            "input": "내 포트폴리오 리스크가 얼마나 돼?",
            "output": """{
  "depth": "quick",
  "focus_areas": ["concentration", "market"],
  "specialists": ["concentration_specialist", "market_risk_specialist"],
  "reasoning": "간단한 리스크 점수 요청. 주요 지표만 제공.",
  "confidence": 0.80
}"""
        },
        {
            "input": "시장 폭락 시 내 포트폴리오 얼마나 손실 날까?",
            "output": """{
  "depth": "comprehensive",
  "focus_areas": ["concentration", "market", "scenario"],
  "specialists": ["concentration_specialist", "market_risk_specialist", "scenario_specialist"],
  "reasoning": "시나리오 분석 요청. 최악의 경우 손실 추정 필요.",
  "confidence": 0.90
}"""
        },
        {
            "input": "삼성전자 비중이 너무 높은 거 아니야?",
            "output": """{
  "depth": "standard",
  "focus_areas": ["concentration"],
  "specialists": ["concentration_specialist"],
  "reasoning": "집중도 리스크 우려. 종목 집중도 분석만 필요.",
  "confidence": 0.85
}"""
        }
    ]

    guidelines = """1. quick depth는 2개 specialist 이하
2. comprehensive depth는 scenario_specialist 포함
3. focus_areas는 specialists와 일치
4. confidence는 쿼리 명확성 반영
5. 리스크 분석은 보수적으로 접근 (의심스러우면 comprehensive)"""

    return build_prompt(
        role="Risk Intent Classifier - 리스크 분석 의도 분석 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_risk_planner_prompt(
    query: str,
    analysis_depth: str,
    focus_areas: List[str],
) -> str:
    """
    Risk Agent용 Planner 프롬프트

    Args:
        query: 사용자 쿼리
        analysis_depth: 분석 깊이
        focus_areas: 집중 영역

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {
        "analysis_depth": analysis_depth,
        "focus_areas": focus_areas,
    }

    task = f"""리스크 분석 계획을 수립하세요.

쿼리: "{query}"
분석 깊이: {analysis_depth}
집중 영역: {', '.join(focus_areas)}

계획 수립 기준:

**1. Specialist 선택**:
Available Specialists:
- collect_data: 포트폴리오 데이터 수집 (항상 필요)
- concentration_specialist: 집중도 리스크 분석
- market_risk_specialist: 시장 리스크 분석 (VaR, 변동성)
- final_assessment: 최종 평가 (항상 마지막)

**2. 실행 순서**:
항상 sequential (리스크 분석은 순차적 의존성)

**3. 예상 시간**:
- collect_data: 5초
- concentration_specialist: 10초
- market_risk_specialist: 15초
- final_assessment: 5초

Depth별 기본 전략:
- **quick**: collect_data → concentration → final_assessment (20초)
- **standard**: collect_data → concentration → market_risk → final_assessment (35초)
- **comprehensive**: 전체 + 시나리오 분석 (50초)"""

    output_format = """{
  "specialists": ["collect_data", "concentration_specialist", "market_risk_specialist", "final_assessment"],
  "execution_order": "sequential",
  "estimated_time": "35",
  "reasoning": "표준 리스크 분석이므로 집중도와 시장 리스크 모두 필요.",
  "skip_steps": []
}"""

    examples = [
        {
            "input": "quick depth, concentration only",
            "output": """{
  "specialists": ["collect_data", "concentration_specialist", "final_assessment"],
  "execution_order": "sequential",
  "estimated_time": "20",
  "reasoning": "간단한 집중도 리스크만 확인.",
  "skip_steps": ["market_risk_specialist"]
}"""
        }
    ]

    guidelines = """1. collect_data와 final_assessment는 항상 포함
2. execution_order는 항상 sequential
3. estimated_time은 specialists 개수 기반 계산
4. 리스크 분석은 보수적으로 (의심스러우면 모든 specialist 포함)"""

    return build_prompt(
        role="Risk Planner - 리스크 분석 계획 수립 전문가",
        context=context,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

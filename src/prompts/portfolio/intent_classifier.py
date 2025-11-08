"""
Portfolio Agent Intent Classifier 프롬프트
"""
from typing import Optional, Dict, List
from ..utils import build_prompt


def build_portfolio_intent_classifier_prompt(
    query: str,
    user_profile: Optional[Dict] = None,
    current_holdings: Optional[List[Dict]] = None,
) -> str:
    """
    Portfolio Agent용 Intent Classifier 프롬프트

    Args:
        query: 사용자 쿼리
        user_profile: 사용자 프로필 (옵션)
        current_holdings: 현재 보유 종목 (옵션)

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {}

    if user_profile:
        context["risk_profile"] = user_profile.get("risk_profile", "moderate")
        context["horizon"] = user_profile.get("horizon", "mid_term")

    if current_holdings:
        context["holdings_count"] = len(current_holdings)
        context["total_value"] = sum(h.get("value", 0) for h in current_holdings)

    task = f"""사용자 쿼리를 분석하여 포트폴리오 작업 의도를 분류하세요.

쿼리: "{query}"

분류 기준:

**1. Intent Type (의도 유형)**:
- **view**: 단순 조회 (현재 포트폴리오 확인, 수익률 조회)
- **analyze**: 분석 요청 (포트폴리오 건강도, 리스크 분석)
- **optimize**: 최적화 요청 (더 나은 포트폴리오 구성 제안)
- **rebalance**: 리밸런싱 요청 (실제 매매를 통한 조정)

**2. Analysis Depth (분석 깊이)**:
- **quick**: 간단한 요약만 (1-2개 지표)
- **standard**: 표준 분석 (3-4개 지표)
- **comprehensive**: 종합 분석 (5개 이상 지표)

**3. Focus Areas (집중 영역)**:
선택 가능한 영역:
- portfolio_snapshot: 포트폴리오 스냅샷
- market_condition: 시장 상황 분석
- optimization: 최적화 제안
- constraints: 제약 조건 검증
- rebalancing: 리밸런싱 계획
- execution: 실행 계획

**4. Required Specialists (필요한 Specialist)**:
- market_condition_specialist: 시장 상황 분석
- optimization_specialist: 포트폴리오 최적화
- constraint_validator: 제약 조건 검증
- rebalance_planner: 리밸런싱 계획 수립"""

    output_format = """{
  "intent_type": "analyze",
  "depth": "standard",
  "focus_areas": ["portfolio_snapshot", "market_condition", "optimization"],
  "specialists": ["market_condition_specialist", "optimization_specialist"],
  "reasoning": "사용자가 현재 포트폴리오의 건강도를 확인하고 개선 방안을 원함. 시장 상황과 최적화 제안이 필요.",
  "view_only": false,
  "confidence": 0.85
}"""

    examples = [
        {
            "input": "내 포트폴리오 좀 보여줘",
            "output": """{
  "intent_type": "view",
  "depth": "quick",
  "focus_areas": ["portfolio_snapshot"],
  "specialists": [],
  "reasoning": "단순 조회 요청. 분석 불필요.",
  "view_only": true,
  "confidence": 0.95
}"""
        },
        {
            "input": "포트폴리오 리밸런싱 필요할까?",
            "output": """{
  "intent_type": "analyze",
  "depth": "standard",
  "focus_areas": ["portfolio_snapshot", "market_condition", "optimization"],
  "specialists": ["market_condition_specialist", "optimization_specialist"],
  "reasoning": "리밸런싱 필요성 판단 요청. 현재 상태와 최적 상태 비교 필요.",
  "view_only": false,
  "confidence": 0.80
}"""
        },
        {
            "input": "포트폴리오 리밸런싱 해줘",
            "output": """{
  "intent_type": "rebalance",
  "depth": "comprehensive",
  "focus_areas": ["portfolio_snapshot", "market_condition", "optimization", "constraints", "rebalancing", "execution"],
  "specialists": ["market_condition_specialist", "optimization_specialist", "constraint_validator", "rebalance_planner"],
  "reasoning": "실제 리밸런싱 실행 요청. 모든 단계 필요 (분석 → 최적화 → 제약 검증 → 계획 → 실행).",
  "view_only": false,
  "confidence": 0.90
}"""
        },
        {
            "input": "삼성전자 비중이 너무 높은 것 같은데",
            "output": """{
  "intent_type": "analyze",
  "depth": "standard",
  "focus_areas": ["portfolio_snapshot", "constraints"],
  "specialists": ["constraint_validator"],
  "reasoning": "집중도 리스크 우려. 제약 조건 검증 필요.",
  "view_only": false,
  "confidence": 0.85
}"""
        }
    ]

    guidelines = """1. intent_type은 반드시 view/analyze/optimize/rebalance 중 하나
2. view_only: true면 specialists는 빈 배열
3. rebalance intent는 자동으로 comprehensive depth
4. focus_areas는 intent_type에 따라 자동 추론
5. confidence는 쿼리 명확성 반영 (0.0-1.0)"""

    return build_prompt(
        role="Portfolio Intent Classifier - 포트폴리오 작업 의도 분석 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_portfolio_planner_prompt(
    query: str,
    intent_type: str,
    analysis_depth: str,
    focus_areas: List[str],
) -> str:
    """
    Portfolio Agent용 Planner 프롬프트

    Args:
        query: 사용자 쿼리
        intent_type: 의도 유형
        analysis_depth: 분석 깊이
        focus_areas: 집중 영역

    Returns:
        Claude 4.x 구조화 프롬프트
    """
    context = {
        "intent_type": intent_type,
        "analysis_depth": analysis_depth,
        "focus_areas": focus_areas,
    }

    task = f"""포트폴리오 작업 계획을 수립하세요.

쿼리: "{query}"
의도: {intent_type}
분석 깊이: {analysis_depth}
집중 영역: {', '.join(focus_areas)}

계획 수립 기준:

**1. Specialist 선택**:
Available Specialists:
- collect_portfolio: 포트폴리오 데이터 수집 (항상 필요)
- market_condition_specialist: 시장 상황 분석
- optimization_specialist: 포트폴리오 최적화
- constraint_validator: 제약 조건 검증
- rebalance_planner: 리밸런싱 계획
- summary_generator: 요약 생성 (항상 마지막)

**2. 실행 순서**:
- sequential: 순차 실행 (의존성 있음)
- parallel: 병렬 실행 (독립적)

**3. 예상 시간**:
- collect_portfolio: 5초
- market_condition_specialist: 10초
- optimization_specialist: 15초
- constraint_validator: 5초
- rebalance_planner: 10초
- summary_generator: 5초

Intent별 기본 전략:
- **view**: collect_portfolio → summary_generator (10초)
- **analyze**: collect_portfolio → market_condition → optimization → summary (30초)
- **optimize**: collect_portfolio → market_condition → optimization → constraint_validator → summary (35초)
- **rebalance**: 전체 파이프라인 (50초)"""

    output_format = """{
  "specialists": ["collect_portfolio", "market_condition_specialist", "optimization_specialist", "summary_generator"],
  "execution_order": "sequential",
  "estimated_time": "30",
  "reasoning": "분석 요청이므로 시장 상황과 최적화 제안이 필요. 순차 실행으로 안정성 확보.",
  "skip_steps": []
}"""

    examples = [
        {
            "input": "view intent, quick depth",
            "output": """{
  "specialists": ["collect_portfolio", "summary_generator"],
  "execution_order": "sequential",
  "estimated_time": "10",
  "reasoning": "단순 조회이므로 데이터 수집과 요약만 필요.",
  "skip_steps": ["market_condition_specialist", "optimization_specialist", "constraint_validator", "rebalance_planner"]
}"""
        },
        {
            "input": "rebalance intent, comprehensive depth",
            "output": """{
  "specialists": ["collect_portfolio", "market_condition_specialist", "optimization_specialist", "constraint_validator", "rebalance_planner", "summary_generator"],
  "execution_order": "sequential",
  "estimated_time": "50",
  "reasoning": "리밸런싱 실행이므로 전체 파이프라인 필요. 안전을 위해 순차 실행.",
  "skip_steps": []
}"""
        }
    ]

    guidelines = """1. collect_portfolio와 summary_generator는 항상 포함
2. execution_order는 현재 버전에서는 항상 sequential
3. estimated_time은 specialists 개수 기반 계산
4. skip_steps는 실행하지 않을 specialist 나열
5. reasoning은 구체적으로 작성"""

    return build_prompt(
        role="Portfolio Planner - 포트폴리오 작업 계획 수립 전문가",
        context=context,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )

"""
Planner Prompts

Intent Classifier 결과를 바탕으로 실행할 작업 목록을 생성하는 프롬프트
"""
from typing import Dict, List, Optional
from ..utils import build_prompt


def build_research_planner_prompt(
    query: str,
    analysis_depth: str,
    focus_areas: List[str],
) -> str:
    """
    Research Agent용 Planner 프롬프트

    Args:
        query: 사용자 쿼리
        analysis_depth: "quick" | "standard" | "comprehensive"
        focus_areas: Intent Classifier가 선택한 집중 영역

    Returns:
        Planner 프롬프트
    """
    context = {
        "분석 깊이": analysis_depth,
        "집중 영역": ", ".join(focus_areas) if focus_areas else "자동 선택",
    }

    task = f"""사용자 쿼리와 분석 깊이를 고려하여 실행할 Worker 목록을 선택하세요.

## Available Workers

1. **data**: 원시 데이터 수집
   - 주가, 거래량, 시가총액
   - 재무제표 (매출, 영업이익, ROE 등)
   - 기본 정보

2. **technical**: 기술적 분석
   - 차트 패턴
   - RSI, MACD, Stochastic
   - 이동평균선
   - 지지선/저항선

3. **trading_flow**: 수급 분석
   - 외국인/기관/개인 매매 동향
   - 순매수/순매도 금액
   - 수급 강도

4. **information**: 정보 분석
   - 최근 뉴스
   - 공시
   - 호재/악재 이슈

5. **macro**: 거시경제 분석
   - 금리, 환율
   - 경기 사이클
   - 업황 전망

6. **bull**: 강세 시나리오
   - 상승 요인
   - 긍정적 전망
   - 목표가

7. **bear**: 약세 시나리오
   - 하락 요인
   - 리스크
   - 손절가

8. **insight**: 최종 인사이트 통합

## Worker 선택 기준

### Quick (1-3개 Worker)
분석 깊이가 quick이면 최소한의 Worker만 선택:
- 단순 조회 → data만
- 기술적 지표 → data + technical
- 수급 확인 → data + trading_flow

### Standard (4-5개 Worker)
일반적 분석:
- 기본: data + technical + trading_flow + information
- 필요시: macro 또는 bull/bear 중 하나

### Comprehensive (7-8개 Worker)
심층 분석:
- 거의 모든 Worker
- 특히 bull + bear (양쪽 시나리오 필수)
- insight는 항상 포함

## Focus Areas 반영

Intent Classifier가 선택한 focus_areas를 우선시하세요:
- focus_areas에 "technical"이 있으면 → technical Worker 필수
- focus_areas에 "trading_flow"가 있으면 → trading_flow Worker 필수
- focus_areas가 비어있으면 → analysis_depth에 따라 자동 선택

## 실행 순서

Worker 실행 순서를 결정하세요:

**Sequential (순차)**:
- Worker 간 의존성이 있을 때
- 예: data → technical → bull/bear → insight

**Parallel (병렬)**:
- Worker 간 독립적일 때
- 예: technical, trading_flow, information 동시 실행

일반적으로 data는 먼저 실행하고, 나머지는 병렬 가능합니다.
"""

    output_format = """{
  "workers": ["data", "technical", "trading_flow", ...],
  "execution_order": "sequential" | "parallel" | "mixed",
  "reasoning": "Worker 선택 및 순서 결정 근거",
  "estimated_time": "예상 소요 시간 (초)"
}

execution_order 설명:
- "sequential": 모든 Worker 순차 실행
- "parallel": 모든 Worker 병렬 실행 (data 제외)
- "mixed": data 먼저 실행 후, 나머지 병렬"""

    examples = [
        {
            "input": """Query: "삼성전자 현재가"
Depth: quick
Focus: ["data"]""",
            "output": """{
  "workers": ["data"],
  "execution_order": "sequential",
  "reasoning": "단순 가격 조회이므로 data Worker만 필요",
  "estimated_time": "10"
}"""
        },
        {
            "input": """Query: "삼성전자 분석해줘"
Depth: standard
Focus: ["technical", "trading_flow"]""",
            "output": """{
  "workers": ["data", "technical", "trading_flow", "information"],
  "execution_order": "mixed",
  "reasoning": "일반 분석이므로 기본 4개 Worker. data 먼저 수집 후 나머지 병렬 실행",
  "estimated_time": "35"
}"""
        },
        {
            "input": """Query: "삼성전자 매수할까?"
Depth: comprehensive
Focus: ["technical", "trading_flow", "bull", "bear"]""",
            "output": """{
  "workers": ["data", "technical", "trading_flow", "information", "macro", "bull", "bear", "insight"],
  "execution_order": "mixed",
  "reasoning": "매수 판단이므로 전체 Worker 실행. Bull/Bear 시나리오 필수. data 먼저, 나머지 병렬",
  "estimated_time": "70"
}"""
        }
    ]

    guidelines = """선택한 Worker 수가 analysis_depth와 일치하는지 확인하세요:
- quick: 1-3개
- standard: 4-5개
- comprehensive: 7-8개

Focus areas가 명시되었다면 해당 Worker는 반드시 포함하세요."""

    return build_prompt(
        role="투자 분석 작업 계획 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_strategy_planner_prompt(
    query: str,
    analysis_depth: str,
    focus_areas: List[str],
) -> str:
    """
    Strategy Agent용 Planner 프롬프트

    Args:
        query: 사용자 쿼리
        analysis_depth: "quick" | "standard" | "comprehensive"
        focus_areas: Intent Classifier가 선택한 집중 영역

    Returns:
        Planner 프롬프트
    """
    context = {
        "분석 깊이": analysis_depth,
        "집중 영역": ", ".join(focus_areas) if focus_areas else "자동 선택",
    }

    task = """사용자 쿼리와 분석 깊이를 고려하여 실행할 Specialist 목록을 선택하세요.

## Available Specialists

1. **market_specialist**: 시장 사이클 분석 (Bull/Bear 판단)
2. **sector_specialist**: 섹터 로테이션 전략
3. **asset_specialist**: 자산 배분 비율 결정
4. **buy_specialist**: 매수 점수 산정 (1-10점)
5. **sell_specialist**: 매도 판단 (익절/손절/홀드)
6. **risk_reward_specialist**: 손절가/목표가 계산

## 선택 기준

### Quick (1-2개)
- 특정 요청에만 응답
- 예: "매수 점수만" → buy_specialist

### Standard (2-4개)
- 일반적 전략 수립
- 예: "투자 전략" → market + sector + asset

### Comprehensive (4-6개)
- 전체 전략 + 의사결정
- 예: "종합 전략" → 전체

## Focus Areas 매핑

- buy_decision → buy_specialist, risk_reward_specialist
- sell_decision → sell_specialist
- market_outlook → market_specialist
- full_strategy → market + sector + asset
- risk_reward → risk_reward_specialist
"""

    output_format = """{
  "specialists": ["buy_specialist", "risk_reward_specialist"],
  "execution_order": "sequential" | "parallel",
  "reasoning": "...",
  "estimated_time": "..."
}"""

    examples = [
        {
            "input": """Query: "매수해도 될까?"
Depth: comprehensive
Focus: ["buy_decision", "risk_reward"]""",
            "output": """{
  "specialists": ["buy_specialist", "risk_reward_specialist"],
  "execution_order": "sequential",
  "reasoning": "매수 판단과 리스크 평가 필요. 순차 실행 (buy 점수 먼저 계산 후 risk_reward)",
  "estimated_time": "25"
}"""
        }
    ]

    return build_prompt(
        role="투자 전략 작업 계획 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
    )

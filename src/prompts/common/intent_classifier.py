"""
Query Intent Classifier Prompts

사용자 쿼리의 의도와 분석 깊이를 판단하는 프롬프트
LLM 완전 자체 판단 기반 (키워드 의존 제거)
"""
from typing import Dict, List, Optional
from ..utils import build_prompt


def build_research_intent_classifier_prompt(
    query: str,
    user_profile: Optional[Dict] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> str:
    """
    Research Agent용 Intent Classifier 프롬프트

    Args:
        query: 사용자 쿼리
        user_profile: 사용자 프로필 정보
            - expertise_level: "beginner" | "intermediate" | "expert"
            - preferred_depth: "brief" | "detailed" | "comprehensive"
            - recent_depth_choices: 최근 선택한 분석 깊이 리스트
        conversation_history: 대화 히스토리 (선택적)

    Returns:
        Intent Classifier 프롬프트
    """
    # 사용자 프로필 기본값
    profile = user_profile or {}
    expertise_level = profile.get("expertise_level", "intermediate")
    preferred_depth = profile.get("preferred_depth", "detailed")
    recent_choices = profile.get("recent_depth_choices", [])

    # 컨텍스트 구성
    context = {
        "투자 경험 수준": expertise_level,
        "선호 분석 깊이": preferred_depth,
    }

    if recent_choices:
        recent_str = ", ".join(recent_choices[-5:])  # 최근 5개
        context["최근 5개 선택"] = recent_str

    if conversation_history:
        context["대화 컨텍스트"] = f"이전 {len(conversation_history)}개 메시지 참조"

    # Task 정의
    task = """<role>당신은 투자 분석 요청의 복잡도와 필요한 분석 영역을 판단하는 전문가입니다.</role>

<instructions>
사용자 쿼리를 분석하여 분석 깊이(depth)와 집중 영역(focus_areas)을 결정하세요.

## 분석 깊이 결정

<depth_criteria>
**quick**: 단일 정보 조회
- 예: "현재가는?", "PER 얼마야?", "외국인 매수량은?"
- 조건: 단일 데이터 포인트, 계산 불필요

**standard**: 일반적 분석
- 예: "어때?", "분석해줘", "A vs B 비교"
- 조건: 여러 지표 통합, 기본 해석 필요

**comprehensive**: 투자 의사결정
- 예: "매수할까?", "지금 팔아야 할까?", "투자 전략 짜줘"
- 조건: 다면적 분석, 미래 예측, 리스크 평가 필요
</depth_criteria>

## 집중 영역 선택

<focus_areas_mapping>
사용 가능한 Worker:
- data: 기본 데이터 (주가, 재무제표)
- technical: 기술적 분석 (차트, 지표)
- trading_flow: 수급 분석 (외국인/기관/개인)
- information: 뉴스/공시 분석
- macro: 거시경제 분석
- bull/bear: 상승/하락 시나리오
- insight: 최종 인사이트

쿼리별 매핑:
- "차트 분석" → ["technical"]
- "외국인 매수 추세" → ["trading_flow"]
- "매수할까?" → ["technical", "trading_flow", "information", "bull", "bear"]
- "뉴스 있어?" → ["information"]
</focus_areas_mapping>

<thinking_process>
다음 순서로 판단하세요:

1. **의도 파악**: 데이터 조회? 분석? 의사결정?
2. **복잡도 평가**: 필요한 정보의 양과 분석 깊이
3. **사용자 고려**: {expertise_level} 수준에 맞는 깊이 조정
   - beginner → 더 상세한 분석 선호
   - expert → 핵심만 간결하게
4. **암묵적 요구 파악**: 명시하지 않았지만 필요한 정보
   - "오를까?" → 목표가, 리스크, 타이밍
   - "어때?" → 강점/약점, 전망
</thinking_process>

<critical_rules>
1. 키워드만 보지 말고 전체 맥락을 파악하세요
   - "빠르게 전략 짜줘" → standard (단순 조회 아님)
2. 의사결정 질문은 comprehensive
   - "~할까?", "~해도 될까?" 형태
3. 애매하면 standard (quick은 명확할 때만)
4. confidence는 정직하게
   - 명확: 0.9-1.0
   - 일반: 0.7-0.85
   - 애매: 0.5-0.65
</critical_rules>
</instructions>
"""

    # Output Format
    output_format = """{
  "depth": "quick" | "standard" | "comprehensive",
  "confidence": 0.0-1.0,
  "reasoning": "1-2문장으로 판단 근거 설명",
  "focus_areas": ["technical", "trading_flow", ...],
  "implicit_needs": "사용자가 명시하지 않았지만 필요할 것으로 예상되는 정보"
}"""

    # Examples
    examples = [
        {
            "input": "삼성전자 현재가",
            "output": """{
  "depth": "quick",
  "confidence": 1.0,
  "reasoning": "단순 가격 정보 조회 요청",
  "focus_areas": ["data"],
  "implicit_needs": null
}"""
        },
        {
            "input": "삼성전자 매수해도 될까?",
            "output": """{
  "depth": "comprehensive",
  "confidence": 0.95,
  "reasoning": "매수 의사결정 요청, 다면적 분석 필요",
  "focus_areas": ["technical", "trading_flow", "information", "bull", "bear"],
  "implicit_needs": "목표가, 손절가, 리스크 평가, 적정 매수 타이밍, Bull/Bear 시나리오"
}"""
        },
        {
            "input": "삼성전자 어때?",
            "output": """{
  "depth": "standard",
  "confidence": 0.8,
  "reasoning": "일반적 분석 요청, 의사결정 의도는 불명확",
  "focus_areas": ["technical", "trading_flow", "information"],
  "implicit_needs": "현재 시점 투자 매력도, 강점/약점, 단기 전망"
}"""
        },
        {
            "input": "삼성전자 RSI 과매수야?",
            "output": """{
  "depth": "quick",
  "confidence": 0.95,
  "reasoning": "특정 기술 지표 확인 요청",
  "focus_areas": ["technical"],
  "implicit_needs": "RSI 수치, 과매수/과매도 판단 기준"
}"""
        },
        {
            "input": "빠르게 삼성전자 투자 전략 짜줘",
            "output": """{
  "depth": "standard",
  "confidence": 0.75,
  "reasoning": "'빠르게'라는 키워드가 있지만 전략 수립은 중간 복잡도. Quick은 단순 조회에만 적용",
  "focus_areas": ["technical", "trading_flow", "bull", "bear"],
  "implicit_needs": "목표 수익률, 투자 기간, 리스크 수준"
}"""
        },
        {
            "input": "삼성전자 외국인 매수 현황",
            "output": """{
  "depth": "quick",
  "confidence": 0.9,
  "reasoning": "특정 수급 데이터 조회 요청",
  "focus_areas": ["trading_flow"],
  "implicit_needs": "최근 추세, 순매수/순매도 금액"
}"""
        }
    ]

    guidelines = f"""이 쿼리는 투자 경험 {expertise_level} 사용자의 요청입니다.

사용자의 최근 패턴을 참고하되, **쿼리 자체의 복잡도를 우선시**하세요.

절대로 키워드("빠르게", "상세히")에만 의존하지 마세요. 전체 문맥을 이해하고 판단하세요."""

    return build_prompt(
        role="투자 분석 요청의 복잡도를 판단하는 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
        guidelines=guidelines,
    )


def build_strategy_intent_classifier_prompt(
    query: str,
    user_profile: Optional[Dict] = None,
) -> str:
    """
    Strategy Agent용 Intent Classifier 프롬프트

    Args:
        query: 사용자 쿼리
        user_profile: 사용자 프로필 정보

    Returns:
        Intent Classifier 프롬프트
    """
    profile = user_profile or {}
    expertise_level = profile.get("expertise_level", "intermediate")

    context = {
        "투자 경험 수준": expertise_level,
    }

    task = """<role>당신은 투자 전략 요청의 범위를 판단하는 전문가입니다.</role>

<instructions>
사용자가 필요로 하는 전략 Specialist를 선택하세요.

<available_specialists>
1. market_specialist: 시장 사이클 분석 (Bull/Bear)
2. sector_specialist: 섹터 로테이션 전략
3. asset_specialist: 자산 배분 비율
4. buy_specialist: 매수 점수 (1-10점)
5. sell_specialist: 매도 판단 (익절/손절/홀드)
6. risk_reward_specialist: 손절가/목표가 계산
</available_specialists>

<query_mapping>
쿼리 패턴별 Specialist 매핑:
- "매수해도 될까?" → buy_specialist, risk_reward_specialist
- "매수 점수만" → buy_specialist
- "팔아야 할까?" → sell_specialist
- "손절가는?" → risk_reward_specialist
- "투자 전략 짜줘" → market, sector, asset
- "시장 전망" → market_specialist
- "포트폴리오 구성" → sector, asset
- "종합 전략" → 전체 (6개)
</query_mapping>

<decision_logic>
1. 의사결정 요청 → buy/sell + risk_reward
2. 정보 제공 → market/sector/asset
3. 모호한 요청 → 여러 Specialist
4. 사용자 수준 고려
   - beginner → 더 많은 Specialist (교육 필요)
   - expert → 필요한 것만
</decision_logic>
</instructions>
"""

    output_format = """{
  "depth": "quick" | "standard" | "comprehensive",
  "focus_areas": ["buy_decision", "market_outlook", ...],
  "specialists": ["buy_specialist", "risk_reward_specialist"],
  "reasoning": "..."
}"""

    examples = [
        {
            "input": "삼성전자 매수해도 될까?",
            "output": """{
  "depth": "comprehensive",
  "focus_areas": ["buy_decision", "risk_reward"],
  "specialists": ["buy_specialist", "risk_reward_specialist"],
  "reasoning": "매수 판단 + 리스크 평가 필요"
}"""
        },
        {
            "input": "매수 점수만 알려줘",
            "output": """{
  "depth": "quick",
  "focus_areas": ["buy_decision"],
  "specialists": ["buy_specialist"],
  "reasoning": "매수 점수만 요청"
}"""
        },
        {
            "input": "투자 전략 짜줘",
            "output": """{
  "depth": "comprehensive",
  "focus_areas": ["full_strategy"],
  "specialists": ["market_specialist", "sector_specialist", "asset_specialist"],
  "reasoning": "전체 투자 전략 수립 필요"
}"""
        }
    ]

    return build_prompt(
        role="투자 전략 요청의 범위를 판단하는 전문가",
        context=context,
        input_data=query,
        task=task,
        output_format=output_format,
        examples=examples,
    )

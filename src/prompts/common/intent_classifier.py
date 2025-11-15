"""
Query Intent Classifier Prompts

사용자 쿼리의 의도와 분석 깊이를 판단하는 프롬프트
"""
from typing import Dict, Optional
from ..utils import build_prompt


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

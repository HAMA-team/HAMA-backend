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
    task = """사용자 쿼리를 분석하여 필요한 분석 깊이와 집중 영역을 결정하세요.

## 분석 기준

### 1. 쿼리 의도 파악

쿼리를 다음 카테고리로 분류하세요:

**단순 정보 조회** → quick
- 현재가, 거래량, PER 같은 단일 정보 요청
- "얼마야?", "몇 주야?", "언제야?" 형태
- 예: "삼성전자 현재가", "코스피 지수 얼마?"

**일반 분석 요청** → standard
- 종목에 대한 전반적 분석
- "어때?", "분석해줘", "괜찮아?" 형태
- 예: "삼성전자 어때?", "이 종목 분석해줘"

**투자 의사결정** → comprehensive
- 매수/매도/홀드 판단 필요
- "할까?", "해도 될까?", "타이밍" 관련
- 예: "삼성전자 매수할까?", "지금 팔아야 할까?"

### 2. 복잡도 판단

쿼리의 복잡도를 평가하세요:

**Low Complexity (quick)**:
- 단일 데이터 포인트 조회
- 계산이 필요 없는 정보
- 시간 제약 명시 (예: "빠르게", "간단히" - 하지만 이것만으로 판단하지 말 것)

**Medium Complexity (standard)**:
- 여러 데이터 통합 필요
- 기본적인 분석 및 해석
- 비교 요청 (예: "A vs B")

**High Complexity (comprehensive)**:
- 다면적 분석 (기술적 + 재무 + 수급)
- 미래 예측 또는 판단
- 리스크/리워드 평가

### 3. 사용자 성향 반영

사용자의 투자 경험 수준과 선호도를 고려하세요:

**Beginner + 복잡한 쿼리**:
- 자동으로 comprehensive 선호
- 이유: 초보자는 상세한 설명과 교육이 필요

**Expert + 간단한 쿼리**:
- quick 가능
- 이유: 전문가는 핵심만 빠르게 파악

**최근 선택 패턴**:
- 사용자가 최근에 comprehensive를 자주 선택했다면 → 기본값 상향
- 사용자가 quick을 선호한다면 → 간결함 중시

### 4. 암묵적 요구사항 파악

사용자가 명시하지 않았지만 필요할 것으로 예상되는 정보를 식별하세요:

예시:
- "오를까?" → 목표가, 손절가, 매수 타이밍, 리스크 필요
- "어때?" → 현재 평가, 강점/약점, 향후 전망 필요
- "비교해줘" → 동종업계 벤치마크, 상대적 가치 필요

### 5. Focus Areas 선택

분석에 집중해야 할 영역을 선택하세요:

Available Workers:
- **data**: 원시 데이터 수집 (주가, 거래량, 재무제표)
- **technical**: 기술적 분석 (차트, RSI, MACD, 이평선)
- **trading_flow**: 수급 분석 (외국인, 기관, 개인 매매)
- **information**: 뉴스, 공시, 이슈 분석
- **macro**: 거시경제 분석 (금리, 환율, 경기)
- **bull**: 강세 시나리오 (상승 요인)
- **bear**: 약세 시나리오 (하락 요인)
- **insight**: 최종 인사이트 통합

Focus Areas 매핑 예시:
- "차트 분석" → ["technical"]
- "외국인 매수하고 있어?" → ["trading_flow"]
- "매수할까?" → ["technical", "trading_flow", "information", "bull", "bear"]
- "뉴스 있어?" → ["information"]

## 중요 원칙

1. **키워드에만 의존하지 마세요**: "빠르게"라는 단어가 있어도 복잡한 질문이면 comprehensive 가능
   - 예: "빠르게 투자 전략 짜줘" → standard (단순 조회 아님)

2. **전체 맥락을 고려하세요**: 단어 하나가 아니라 전체 문장의 의도를 파악

3. **보수적으로 판단하세요**:
   - 의사결정이 필요하면 comprehensive
   - 애매하면 standard (quick은 명확할 때만)

4. **confidence 점수를 정직하게**:
   - 명확한 경우: 0.9-1.0
   - 일반적 경우: 0.7-0.85
   - 애매한 경우: 0.5-0.65
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

    task = """사용자가 필요로 하는 전략 분석 범위를 결정하세요.

## 분석 범위 옵션

다음 Specialist 중 필요한 것을 선택하세요:

1. **market_specialist**: 시장 사이클 분석 (Bull/Bear 판단)
2. **sector_specialist**: 섹터 로테이션 전략
3. **asset_specialist**: 자산 배분 비율 결정
4. **buy_specialist**: 매수 점수 산정 (1-10점)
5. **sell_specialist**: 매도 판단 (익절/손절/홀드)
6. **risk_reward_specialist**: 손절가/목표가 계산

## 쿼리 패턴별 매핑

- "매수해도 될까?" → buy_specialist, risk_reward_specialist
- "매수 점수만" → buy_specialist
- "팔아야 할까?" → sell_specialist
- "손절가 계산" → risk_reward_specialist
- "투자 전략 짜줘" → market_specialist, sector_specialist, asset_specialist
- "시장 전망" → market_specialist
- "포트폴리오 구성" → sector_specialist, asset_specialist
- "종합 전략" → 전체 (6개 모두)

## 판단 기준

1. **의사결정 vs 정보 제공**:
   - 의사결정 (매수/매도) → buy/sell_specialist + risk_reward
   - 정보 제공 (시장 전망) → market_specialist

2. **범위**:
   - 특정 요청 → 해당 Specialist만
   - 모호한 요청 ("전략 짜줘") → 여러 Specialist

3. **사용자 경험**:
   - Beginner → 더 많은 Specialist (설명 필요)
   - Expert → 필요한 것만
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

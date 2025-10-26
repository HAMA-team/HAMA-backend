# Week 4: AI 생성 프로파일 + Memory 기반 점진적 학습

## 📋 목표

1. **초기 온보딩**: 스크리닝 + 포트폴리오 분석을 통한 AI 생성 프로파일
2. **점진적 학습**: 대화 중 사용자 선호도 파악 및 프로파일 자동 업데이트
3. **Frontend 요구사항**: Artifact 저장, 포트폴리오 미리보기 API

---

## 1. AI 생성 프로파일 (초기 온보딩)

### 1.1 온보딩 플로우

```
[회원가입/로그인]
        ↓
[초기 스크리닝] ← Frontend 팀 담당 (설문 UI)
  - 투자 목표 (단기수익/장기성장/안정적수익)
  - 투자 기간 (1년 미만/1-3년/3년 이상)
  - 위험 성향 (5단계 질문)
  - 관심 섹터 (복수 선택)
  - 평균 매매 빈도 예상
        ↓
[포트폴리오 분석] ← Backend (선택적)
  - 기존 포트폴리오 업로드 (CSV/엑셀)
  - AI가 보유 패턴 분석
        ↓
[AI 프로파일 생성] ← Backend
  - LLM이 스크리닝 + 포트폴리오 종합 분석
  - 자연어 프로파일 생성
  - DB 저장 (user_profiles.llm_generated_profile)
        ↓
[프로파일 확인 및 시작]
```

### 1.2 Backend API 설계

#### `POST /onboarding/screening`

**요청:**
```json
{
  "user_id": "uuid",
  "screening_answers": {
    "investment_goal": "long_term_growth",
    "investment_period": "3_years_plus",
    "risk_questions": [
      {"q": "시장 급락 시 행동은?", "a": "추가 매수"},
      {"q": "손실 허용 범위는?", "a": "10-20%"},
      {"q": "변동성 수용도는?", "a": "높음"}
    ],
    "preferred_sectors": ["반도체", "배터리", "바이오"],
    "expected_trade_frequency": "주 1회"
  },
  "portfolio_data": [  // 선택적
    {"stock_code": "005930", "quantity": 10, "avg_price": 70000},
    {"stock_code": "000660", "quantity": 5, "avg_price": 140000}
  ]
}
```

**응답:**
```json
{
  "user_id": "uuid",
  "profile": {
    "expertise_level": "intermediate",
    "investment_style": "aggressive",
    "risk_tolerance": "high",
    "preferred_sectors": ["반도체", "배터리", "바이오"],
    "trading_style": "long_term",
    "portfolio_concentration": 0.6,
    "technical_level": "intermediate",
    "preferred_depth": "detailed",
    "wants_explanations": false,
    "wants_analogies": false,
    "llm_generated_profile": "이 투자자는 장기 성장을 목표로 하며, 반도체와 배터리 섹터에 집중 투자하는 공격적 성향입니다. 시장 변동성에 강하며, 기술주 중심의 포트폴리오를 선호합니다. 평균 보유 기간이 6개월 이상으로, 단기 매매보다는 펀더멘털 기반 장기 투자를 선호합니다."
  }
}
```

#### `GET /user/investment-profile`

**응답:**
```json
{
  "user_id": "uuid",
  "profile_summary": "공격적 성장 투자자 | 기술주 선호 | 장기 보유",
  "key_characteristics": [
    "반도체/배터리 집중 투자",
    "변동성 수용 가능",
    "펀더멘털 기반 의사결정",
    "6개월+ 보유 성향"
  ],
  "llm_generated_profile": "...",
  "last_updated": "2025-10-21T10:00:00Z"
}
```

### 1.3 AI 프로파일 생성 로직

**구현 파일:** `src/services/profile_generator.py`

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

async def generate_ai_profile(
    screening_answers: dict,
    portfolio_data: list = None
) -> dict:
    """
    스크리닝 응답 + 포트폴리오 데이터를 LLM으로 분석하여 프로파일 생성

    Args:
        screening_answers: 온보딩 설문 응답
        portfolio_data: 기존 포트폴리오 (선택적)

    Returns:
        생성된 프로파일 (dict)
    """

    # 1. 포트폴리오 분석 (있는 경우)
    portfolio_analysis = ""
    if portfolio_data:
        portfolio_analysis = analyze_portfolio_pattern(portfolio_data)

    # 2. LLM 프롬프트 구성
    profile_prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 투자자 성향 분석 전문가입니다.

**임무:**
1. 스크리닝 응답 분석
2. 포트폴리오 보유 패턴 분석 (있는 경우)
3. 투자 성향 프로파일 생성

**출력 형식:**
JSON으로 다음 필드를 반환하세요:
- expertise_level: "beginner" | "intermediate" | "expert"
- investment_style: "conservative" | "moderate" | "aggressive"
- risk_tolerance: "low" | "medium" | "high"
- preferred_sectors: list[str]
- trading_style: "short_term" | "long_term"
- portfolio_concentration: 0.0-1.0 (집중도)
- technical_level: "basic" | "intermediate" | "advanced"
- preferred_depth: "brief" | "detailed" | "comprehensive"
- wants_explanations: bool
- wants_analogies: bool
- llm_generated_profile: str (자연어 프로파일 200자 이내)

**분석 기준:**
1. **expertise_level**: 투자 경험, 용어 이해도
2. **investment_style**: 위험 성향 질문 종합
3. **trading_style**: 매매 빈도, 보유 기간
4. **portfolio_concentration**: 포트폴리오 분산 정도
5. **technical_level**: 기술적 분석 이해도
"""),
        ("human", """**스크리닝 응답:**
{screening_answers}

**포트폴리오 분석:**
{portfolio_analysis}

위 정보를 바탕으로 투자자 프로파일을 생성하세요.""")
    ])

    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    structured_llm = llm.with_structured_output(UserProfile)

    result = await structured_llm.ainvoke(
        profile_prompt.format_messages(
            screening_answers=json.dumps(screening_answers, ensure_ascii=False, indent=2),
            portfolio_analysis=portfolio_analysis or "(포트폴리오 데이터 없음)"
        )
    )

    return result.dict()


def analyze_portfolio_pattern(portfolio_data: list) -> str:
    """
    기존 포트폴리오에서 패턴 추출

    Args:
        portfolio_data: 보유 종목 리스트

    Returns:
        자연어 분석 결과
    """
    # 섹터 분포
    sector_distribution = calculate_sector_distribution(portfolio_data)

    # 집중도 (HHI)
    concentration = calculate_hhi(portfolio_data)

    # 종목 수
    stock_count = len(portfolio_data)

    analysis = f"""
포트폴리오 분석:
- 종목 수: {stock_count}개
- 집중도: {concentration:.2f} (0=완전분산, 1=완전집중)
- 주요 섹터: {', '.join(sector_distribution[:3])}
- 패턴: {"집중 투자" if concentration > 0.5 else "분산 투자"}
"""

    return analysis
```

---

## 2. Memory 기반 점진적 학습

### 2.1 개념

**목표:** 대화 중 사용자가 드러내는 선호도를 자동으로 파악하여 프로파일 업데이트

**예시:**
- 사용자: "나는 반도체 관심 많아" → `preferred_sectors`에 "반도체" 추가
- 사용자: "DCF 계산은 복잡해서 싫어" → `preferred_depth` = "detailed" (comprehensive 제외)
- 사용자: "용어 설명 좀 해줘" → `wants_explanations` = True
- 사용자: "PER, PBR만 보여줘" → `technical_level` = "intermediate"

### 2.2 아키텍처

```
┌─────────────────────────────────────────────────┐
│          사용자 대화                            │
│     "나는 반도체에 관심 많아"                    │
└────────────────┬────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│      Memory Detector (LLM)                      │
│  - 대화에서 선호도 신호 감지                     │
│  - 프로파일 업데이트 필요 여부 판단              │
└────────────────┬────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│      UserProfileService.update_profile()        │
│  - preferred_sectors에 "반도체" 추가            │
│  - DB 업데이트 + 캐시 무효화                    │
└────────────────┬────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│      다음 응답부터 반영                          │
│  - Router가 업데이트된 프로파일 로드            │
│  - "반도체 관련 뉴스도 함께 제공"               │
└─────────────────────────────────────────────────┘
```

### 2.3 구현: Memory Detector

**구현 파일:** `src/agents/memory_detector.py`

```python
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

class ProfileUpdate(BaseModel):
    """프로파일 업데이트 신호"""
    update_needed: bool
    field: str | None  # "preferred_sectors", "wants_explanations", etc.
    value: Any
    reasoning: str


async def detect_profile_updates(
    user_message: str,
    current_profile: dict,
    conversation_history: list
) -> ProfileUpdate | None:
    """
    대화에서 프로파일 업데이트 신호 감지

    Args:
        user_message: 사용자 최신 메시지
        current_profile: 현재 프로파일
        conversation_history: 대화 히스토리

    Returns:
        ProfileUpdate 또는 None
    """

    detector_prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 사용자 대화에서 투자 선호도 변화를 감지하는 전문가입니다.

**임무:**
사용자의 대화에서 다음과 같은 신호를 감지하세요:

1. **선호 섹터 변화**
   - "나는 반도체에 관심 많아" → preferred_sectors에 "반도체" 추가
   - "배터리는 이제 별로야" → preferred_sectors에서 "배터리" 제거

2. **답변 깊이 선호**
   - "DCF는 너무 복잡해" → preferred_depth = "detailed" (comprehensive 제외)
   - "자세히 설명해줘" → preferred_depth = "comprehensive"

3. **설명 필요성**
   - "PER이 뭐야?" → wants_explanations = True
   - "용어 설명 불필요해" → wants_explanations = False

4. **비유 선호**
   - "쉽게 비유로 설명해줘" → wants_analogies = True

5. **기술적 수준**
   - "지표만 간단히 보여줘" → technical_level = "intermediate"
   - "민감도 분석까지 해줘" → technical_level = "advanced"

6. **투자 성향 변화**
   - "요즘 보수적으로 가려고" → investment_style = "conservative"

**현재 프로파일:**
{current_profile}

**출력 형식:**
JSON으로 다음을 반환:
- update_needed: bool (업데이트 필요 여부)
- field: str (업데이트할 필드명)
- value: Any (새 값)
- reasoning: str (판단 근거)

**주의:**
- 명확한 신호가 없으면 update_needed = False
- 애매한 경우 업데이트하지 말 것
"""),
        ("human", """**사용자 메시지:**
{user_message}

**이전 대화:**
{conversation_history}

프로파일 업데이트가 필요한지 판단하세요.""")
    ])

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(ProfileUpdate)

    result = await structured_llm.ainvoke(
        detector_prompt.format_messages(
            user_message=user_message,
            current_profile=json.dumps(current_profile, ensure_ascii=False, indent=2),
            conversation_history="\n".join([
                f"{m['role']}: {m['content']}"
                for m in conversation_history[-5:]  # 최근 5턴
            ])
        )
    )

    if result.update_needed:
        return result
    return None
```

### 2.4 통합: Aggregator에서 호출

**수정 파일:** `src/agents/graph_master.py`

```python
async def run_graph_with_memory(
    query: str,
    user_id: str,
    automation_level: int = 2,
    conversation_history: list = None
):
    """
    Memory 기능이 적용된 그래프 실행
    """

    # 1. 프로파일 로드
    user_profile = await user_profile_service.get_user_profile(user_id, db)

    # 2. Memory Detector 실행 (대화 중 선호도 변화 감지)
    if conversation_history:
        profile_update = await detect_profile_updates(
            user_message=query,
            current_profile=user_profile,
            conversation_history=conversation_history
        )

        if profile_update:
            logger.info(f"🧠 [Memory] 프로파일 업데이트 감지: {profile_update.field} = {profile_update.value}")

            # 3. 프로파일 업데이트
            updated_profile = await user_profile_service.update_user_profile(
                user_id=user_id,
                updates={profile_update.field: profile_update.value},
                db=db
            )

            user_profile = updated_profile

    # 4. Router 실행 (업데이트된 프로파일 사용)
    routing_decision = await route_query(
        query=query,
        user_profile=user_profile,
        conversation_history=conversation_history or []
    )

    # 5. 에이전트 실행
    # ...
```

### 2.5 사용자 피드백 (선택적)

Memory 업데이트 시 사용자에게 알림 (선택적):

```json
{
  "message": "삼성전자 분석 결과...",
  "profile_updated": {
    "field": "preferred_sectors",
    "value": ["반도체"],
    "message": "💡 '반도체'를 선호 섹터로 저장했어요. 앞으로 반도체 관련 정보를 더 제공할게요!"
  }
}
```

---

## 3. Frontend 요구사항

### 3.1 Artifact 저장 API

**목적:** AI가 생성한 분석 결과, 차트, 포트폴리오 등을 저장하여 나중에 재조회

#### `POST /artifacts/`

**요청:**
```json
{
  "user_id": "uuid",
  "type": "stock_analysis",  // stock_analysis | portfolio | chart | strategy
  "title": "삼성전자 심층 분석",
  "content": {
    "stock_code": "005930",
    "analysis": "...",
    "metrics": {...},
    "chart_data": {...}
  },
  "metadata": {
    "generated_at": "2025-10-21T10:00:00Z",
    "agents_used": ["research", "strategy"]
  }
}
```

**응답:**
```json
{
  "artifact_id": "uuid",
  "created_at": "2025-10-21T10:00:00Z"
}
```

#### `GET /artifacts/`

**쿼리 파라미터:**
- `user_id` (required)
- `type` (optional): 필터링
- `limit` (default: 10)

**응답:**
```json
{
  "artifacts": [
    {
      "artifact_id": "uuid",
      "type": "stock_analysis",
      "title": "삼성전자 심층 분석",
      "preview": "삼성전자는 현재 저평가 상태로...",
      "created_at": "2025-10-21T10:00:00Z"
    }
  ]
}
```

#### `GET /artifacts/{artifact_id}`

**응답:** 전체 content 반환

---

### 3.2 포트폴리오 미리보기 API

**목적:** 거래 실행 전 예상 포트폴리오 시뮬레이션

#### `POST /portfolio/preview`

**요청:**
```json
{
  "user_id": "uuid",
  "current_portfolio": [
    {"stock_code": "005930", "quantity": 10, "avg_price": 70000}
  ],
  "proposed_trades": [
    {"action": "buy", "stock_code": "000660", "quantity": 5, "price": 140000}
  ]
}
```

**응답:**
```json
{
  "before": {
    "total_value": 700000,
    "stocks": [
      {"stock_code": "005930", "value": 700000, "weight": 1.0}
    ],
    "risk_metrics": {
      "concentration": 1.0,
      "volatility": 0.25
    }
  },
  "after": {
    "total_value": 1400000,
    "stocks": [
      {"stock_code": "005930", "value": 700000, "weight": 0.5},
      {"stock_code": "000660", "value": 700000, "weight": 0.5}
    ],
    "risk_metrics": {
      "concentration": 0.5,
      "volatility": 0.20
    }
  },
  "changes": {
    "risk_reduction": 0.05,
    "diversification_improved": true
  }
}
```

---

## 4. 구현 계획

### Week 4 Task List

**Day 1-2: AI 프로파일 생성**
- [ ] `src/services/profile_generator.py` 구현
- [ ] `POST /onboarding/screening` API
- [ ] `GET /user/investment-profile` API
- [ ] 포트폴리오 패턴 분석 함수 (HHI, 섹터 분포)

**Day 3-4: Memory 기능**
- [ ] `src/agents/memory_detector.py` 구현
- [ ] `run_graph_with_memory()` 통합
- [ ] 프로파일 업데이트 로직
- [ ] 테스트: 대화 중 프로파일 변화 감지

**Day 5: Frontend 요구사항**
- [ ] Artifact 저장 API (`POST /artifacts/`, `GET /artifacts/`)
- [ ] 포트폴리오 미리보기 API (`POST /portfolio/preview`)
- [ ] DB 스키마 추가 (artifacts 테이블)

**Day 6-7: 테스트 및 문서화**
- [ ] AI 프로파일 생성 품질 검증 (10명 샘플)
- [ ] Memory 감지 정확도 테스트
- [ ] Frontend 연동 테스트
- [ ] 문서 업데이트

---

## 5. 예상 성과

| 지표 | 목표 |
|------|------|
| **프로파일 생성 정확도** | 85%+ (사용자 만족도 설문) |
| **Memory 감지율** | 70%+ (명확한 신호 감지) |
| **프로파일 개선 주기** | 대화 10회당 1회 업데이트 |
| **API 응답 속도** | < 2초 (프로파일 생성), < 500ms (artifact 저장) |

---

## 6. 다음 단계 (Week 5)

- Strategy, General, Portfolio Agent ReAct 전환
- 전체 시스템 통합 테스트
- 성능 최적화
- 캡스톤 시연 준비

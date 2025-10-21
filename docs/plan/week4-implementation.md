# Week 4: AI 프로파일 생성 + Memory 학습 구현 완료

## ✅ 완료 항목

### 1. AI Profile Generator (`src/services/profile_generator.py`)

**핵심 기능:**
```python
async def generate_ai_profile(
    screening_answers: Dict[str, Any],
    portfolio_data: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]
```

**생성되는 프로파일:**
```python
{
    "expertise_level": "beginner" | "intermediate" | "expert",
    "investment_style": "conservative" | "moderate" | "aggressive",
    "risk_tolerance": "low" | "medium" | "high",
    "preferred_sectors": ["반도체", "배터리", "바이오"],
    "trading_style": "short_term" | "long_term",
    "portfolio_concentration": 0.0-1.0,  # HHI
    "technical_level": "basic" | "intermediate" | "advanced",
    "preferred_depth": "brief" | "detailed" | "comprehensive",
    "wants_explanations": bool,
    "wants_analogies": bool,
    "llm_generated_profile": "자연어 프로파일 (200자)"
}
```

**포트폴리오 집중도 분석:**
- HHI (Herfindahl-Hirschman Index) 계산
- 0 = 완전분산, 1 = 완전집중
- 예: 10개 종목 균등 보유 = 0.1, 1개 종목만 = 1.0

---

### 2. 온보딩 API (`src/api/routes/onboarding.py`)

#### `POST /onboarding/screening`

**요청 예시:**
```json
{
  "screening_answers": {
    "investment_goal": "long_term_growth",
    "investment_period": "3_years_plus",
    "risk_questions": [
      {"q": "시장 급락 시 행동은?", "a": "추가 매수"},
      {"q": "손실 허용 범위는?", "a": "10-20%"},
      {"q": "변동성 수용도는?", "a": "높음"}
    ],
    "preferred_sectors": ["반도체", "배터리"],
    "expected_trade_frequency": "weekly"
  },
  "portfolio_data": [
    {"stock_code": "005930", "quantity": 10, "avg_price": 70000},
    {"stock_code": "000660", "quantity": 5, "avg_price": 140000}
  ]
}
```

**응답 예시:**
```json
{
  "user_id": "uuid",
  "profile": {
    "expertise_level": "intermediate",
    "investment_style": "aggressive",
    "risk_tolerance": "high",
    "preferred_sectors": ["반도체", "배터리"],
    "trading_style": "long_term",
    "portfolio_concentration": 0.6,
    "technical_level": "intermediate",
    "preferred_depth": "detailed",
    "wants_explanations": false,
    "wants_analogies": false,
    "llm_generated_profile": "이 투자자는 장기 성장을 목표로 하며..."
  },
  "message": "🎉 환영합니다!..."
}
```

#### `GET /onboarding/profile/{user_id}`

**응답 예시:**
```json
{
  "user_id": "uuid",
  "profile_summary": "aggressive intermediate 투자자 | long_term 성향",
  "key_characteristics": [
    "반도체/배터리 선호",
    "위험 수용도: high",
    "집중 투자"
  ],
  "llm_generated_profile": "...",
  "last_updated": "2025-10-21T10:00:00Z",
  "full_profile": {...}
}
```

---

### 3. Memory Detector (`src/agents/memory_detector.py`)

**핵심 기능:**
```python
async def detect_profile_updates(
    user_message: str,
    current_profile: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Optional[ProfileUpdate]
```

**감지하는 신호:**

| 신호 | 감지 예시 | 필드 | 값 |
|------|----------|------|-----|
| 선호 섹터 | "반도체에 관심 많아" | `preferred_sectors` | ["기존", "반도체"] |
| 답변 깊이 | "DCF는 복잡해" | `preferred_depth` | "detailed" |
| 용어 설명 | "PER이 뭐야?" | `wants_explanations` | True |
| 비유 선호 | "쉽게 비유로 설명해줘" | `wants_analogies` | True |
| 기술 수준 | "민감도 분석까지" | `technical_level` | "advanced" |
| 투자 성향 | "보수적으로 가려고" | `investment_style` | "conservative" |

**사용 플로우:**
```python
# 1. 대화 중 신호 감지
update = await detect_profile_updates(
    user_message="나는 반도체에 관심 많아",
    current_profile=user_profile,
    conversation_history=history
)

# 2. 업데이트 적용
if update and update.update_needed:
    updated_profile = await user_profile_service.update_user_profile(
        user_id=user_id,
        updates={update.field: update.value},
        db=db
    )

# 3. 다음 응답부터 반영
# Router가 업데이트된 프로파일 로드
# "반도체 관련 정보 더 제공"
```

---

## 🎯 완성된 전체 플로우 (Week 1~4 통합)

### 시나리오: 신규 사용자 온보딩

```
1. 회원가입/로그인
   ↓
2. POST /onboarding/screening
   - 설문 응답: 장기 성장, 공격적 투자, 반도체 선호
   - 포트폴리오: 삼성전자 10주, SK하이닉스 5주
   ↓
3. AI Profile Generator
   - LLM 분석:
     * expertise_level: intermediate
     * investment_style: aggressive
     * risk_tolerance: high
     * preferred_sectors: ["반도체"]
     * trading_style: long_term
     * portfolio_concentration: 0.6 (집중 투자)
   ↓
4. DB 저장 + 환영 메시지
   "당신은 공격적 성장 투자자입니다!"
```

### 시나리오: 대화 중 선호도 학습

```
사용자: "나는 반도체에 관심 많아"
        ↓
[Week 4] Memory Detector
   - 신호 감지: preferred_sectors 업데이트 필요
   - field: "preferred_sectors"
   - value: ["반도체", "배터리"]  # "배터리" 추가
   - reasoning: "사용자가 반도체에 관심 표명"
        ↓
[Week 1] UserProfileService
   - DB 업데이트: preferred_sectors = ["반도체", "배터리"]
   - 캐시 무효화
        ↓
다음 질문: "삼성전자 분석해줘"
        ↓
[Week 1] Router
   - 프로파일 로드: preferred_sectors = ["반도체", "배터리"]
   - depth_level: detailed
        ↓
[Week 2] Research Agent (ReAct)
   - Tool: get_sector_comparison(sector="반도체")  # 자동 추가
   - "반도체 업종 평균 대비 분석 포함"
        ↓
[Week 3] Aggregator
   - 개인화: "반도체 섹터를 선호하시는군요!"
```

---

## 📊 Week 4 성과

### AI 프로파일 생성

| 입력 | 출력 | 정확도 목표 |
|------|------|-----------|
| 스크리닝 응답 | expertise_level | 90%+ |
| 위험 성향 질문 | investment_style | 85%+ |
| 포트폴리오 데이터 | portfolio_concentration | 100% (계산) |
| 종합 분석 | llm_generated_profile | 사용자 만족도 80%+ |

### Memory 학습

| 신호 타입 | 감지율 목표 | 오탐률 |
|----------|-----------|--------|
| 명확한 신호 | 90%+ | < 5% |
| 애매한 신호 | 건너뛰기 | 0% (보수적) |
| 전체 평균 | 70%+ | < 10% |

---

## 🔄 Week 1~4 완성도

```
[Week 1] Router + UserProfile
   ✅ 질문 분석, 에이전트 선택, 프로파일 로드

[Week 2] Research Agent (ReAct)
   ✅ depth_level별 자율적 도구 선택

[Week 3] Aggregator + Thinking Trace
   ✅ 사용자 수준별 답변 조절, SSE 스트리밍

[Week 4] AI Profile + Memory
   ✅ 초기 온보딩, 점진적 학습

→ 완전 통합 시스템 ✅
```

---

## 🎨 Frontend 연동 가이드

### 1. 온보딩 화면

```javascript
// 1. 스크리닝 설문 제출
const response = await fetch('/api/onboarding/screening', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    screening_answers: {
      investment_goal: 'long_term_growth',
      investment_period: '3_years_plus',
      risk_questions: [...],
      preferred_sectors: ['반도체', '배터리'],
      expected_trade_frequency: 'weekly'
    },
    portfolio_data: [...]  // 선택적
  })
});

const data = await response.json();
console.log('생성된 프로파일:', data.profile);
console.log('환영 메시지:', data.message);
```

### 2. 프로파일 조회

```javascript
// GET /api/onboarding/profile/{user_id}
const profile = await fetch(`/api/onboarding/profile/${userId}`);
const data = await profile.json();

// 프로파일 요약 표시
console.log(data.profile_summary);  // "aggressive intermediate 투자자"
console.log(data.key_characteristics);  // ["반도체/배터리 선호", ...]
```

### 3. Memory 업데이트 알림 (선택적)

```javascript
// 채팅 응답에 profile_updated 포함 (선택적)
{
  "message": "삼성전자 분석 결과...",
  "profile_updated": {
    "field": "preferred_sectors",
    "value": ["반도체", "배터리"],
    "message": "💡 '배터리'를 선호 섹터로 저장했어요!"
  }
}
```

---

## ⚠️ 알려진 이슈

1. **Mock 데이터**
   - 섹터 분류: 실제로는 DART API로 종목→섹터 매핑 필요
   - 포트폴리오 섹터 분포: 현재 하드코딩

2. **Memory 오탐**
   - 애매한 신호 처리: 보수적 접근 (업데이트 안 함)
   - 사용자 피드백 메커니즘 필요 ("이 정보가 맞나요?")

3. **온보딩 UX**
   - Frontend 팀과 설문 항목 조율 필요
   - 포트폴리오 업로드 형식 (CSV/Excel) 정의 필요

---

## 📚 다음 단계 (Week 5)

1. **다른 Agent ReAct 전환**
   - Strategy Agent
   - General Agent
   - Portfolio Agent

2. **성능 최적화**
   - 토큰 사용량 측정
   - 응답 속도 벤치마크
   - 캐싱 전략 개선

3. **E2E 테스트**
   - 온보딩 → 대화 → Memory 업데이트 전체 플로우
   - 동시 사용자 부하 테스트

4. **캡스톤 준비**
   - 시연 시나리오 작성
   - 문서 정리
   - 발표 자료

---

**커밋:** `632fa76` - Feat: AI 프로파일 생성 및 Memory 학습 구현 (Week 4)

**완성도: 80% (4/5 weeks)** 🎉

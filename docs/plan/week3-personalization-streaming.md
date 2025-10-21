# Week 3: 답변 개인화 + Thinking 스트리밍 구현 완료

## ✅ 완료 항목

### 1. Aggregator - 답변 개인화 (`src/agents/aggregator.py`)

**핵심 기능:**
```python
async def personalize_response(
    agent_results: Dict[str, Any],
    user_profile: Dict[str, Any],
    routing_decision: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**사용자 수준별 차별화:**

| 수준 | 용어 설명 | 비유 사용 | 지표 수 | 예시 |
|------|----------|----------|---------|------|
| **beginner** | ✅ 포함 | ✅ 사용 | 1-2개 | "PER은 주식의 '가격표'예요" |
| **intermediate** | 간단히만 | ❌ 미사용 | 3-5개 | "PER 8.5 (업종 평균 12 대비 저평가)" |
| **expert** | ❌ 미포함 | ❌ 미사용 | 모든 지표 | "PER: 8.5x (Sector: 12.0x, -29%)" |

**프롬프트 예시 (초보자):**
```
**PER 8.5**란?
→ 주식의 '가격표'예요. 업종 평균(12)보다 낮아서 저렴한 편입니다.

**결론:** 지금 매수를 고려해볼 만해요!
```

**프롬프트 예시 (전문가):**
```
## Valuation
- PER: 8.5x (Sector: 12.0x, -29%)
- PBR: 1.2x (Sector: 1.5x, -20%)
- EV/EBITDA: 5.8x

## DCF
- WACC: 8.0% (rf=3.5%, β=1.2, ERP=5.5%)
- Terminal g: 3.0%
- Intrinsic Value: 85,000원 (+13% upside)
```

---

### 2. Thinking Trace - 사고 과정 추적 (`src/agents/thinking_trace.py`)

**핵심 기능:**
```python
async def collect_thinking_trace(
    agent,
    input_state: Dict[str, Any],
    config: Dict[str, Any]
) -> AsyncGenerator[Dict[str, Any], None]
```

**수집하는 이벤트:**

| 이벤트 타입 | 설명 | 예시 |
|-----------|------|------|
| `thought` | LLM 사고 과정 | "먼저 주가 데이터를 확인하겠습니다..." |
| `tool_call` | 도구 호출 시작 | `get_stock_price("005930")` |
| `tool_result` | 도구 실행 결과 | `{"current_price": 75000}` |
| `answer` | 최종 답변 | "삼성전자 분석 결과..." |
| `error` | 에러 발생 | "API 호출 실패" |

**포맷팅 예시:**
```markdown
## 🧠 AI 사고 과정

**Step 1: get_stock_price 호출**
- 입력: `{"stock_code": "005930", "days": 1}`
- 결과: {"current_price": 75000, "volume": 15000000}

**Step 2: get_basic_ratios 호출**
- 입력: `{"stock_code": "005930", "metrics": ["PER", "PBR"]}`
- 결과: {"PER": 8.5, "PBR": 1.2}

---

## 📝 최종 답변
삼성전자는 현재 75,000원으로, PER 8.5로 저평가 상태입니다.
```

---

### 3. /chat/stream API - 실시간 스트리밍 (`src/api/routes/chat_stream.py`)

**엔드포인트:**
```
POST /api/chat/stream
```

**요청:**
```json
{
  "message": "삼성전자 분석해줘",
  "user_id": "uuid",
  "conversation_id": "uuid",
  "automation_level": 2
}
```

**응답 형식: Server-Sent Events (SSE)**

```
event: user_profile
data: {"profile": {"expertise_level": "intermediate"}}

event: routing
data: {"depth_level": "detailed", "agents_to_call": ["research"]}

event: thought
data: {"content": "먼저 주가 데이터를 확인하겠습니다"}

event: tool_call
data: {"tool": "get_stock_price", "input": {"stock_code": "005930"}}

event: tool_result
data: {"tool": "get_stock_price", "output": {"current_price": 75000}}

event: answer
data: {"content": "삼성전자 분석 결과..."}

event: done
data: {"conversation_id": "uuid"}
```

---

### 4. Frontend 연동 예시 (JavaScript)

```javascript
const eventSource = new EventSource('/api/chat/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: '삼성전자 분석해줘',
    user_id: 'user-123'
  })
});

// 1. 사고 과정 표시
eventSource.addEventListener('thought', (event) => {
  const data = JSON.parse(event.data);
  appendThinkingBubble(data.content);
});

// 2. 도구 호출 표시
eventSource.addEventListener('tool_call', (event) => {
  const data = JSON.parse(event.data);
  showToolCallIndicator(data.tool, data.input);
});

// 3. 최종 답변 표시
eventSource.addEventListener('answer', (event) => {
  const data = JSON.parse(event.data);
  displayFinalAnswer(data.content);
});

// 4. 완료
eventSource.addEventListener('done', (event) => {
  eventSource.close();
  hideLoadingIndicator();
});

// 5. 에러 처리
eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  showError(data.error);
});
```

---

## 🎯 완성된 전체 플로우

### 시나리오: "삼성전자 PER이 어때?" (초보자)

```
1. 사용자 입력
   ↓
2. UserProfile 로드
   expertise_level: beginner
   wants_explanations: true
   wants_analogies: true
   ↓
3. Router 판단
   depth_level: brief
   agents_to_call: ["research"]
   personalization: {"use_analogies": true}
   ↓
4. Research Agent (ReAct)
   Tool: get_stock_price("005930") → 75,000원
   Tool: get_basic_ratios("005930", ["PER"]) → 8.5
   ↓
5. Aggregator (개인화)
   Input: {"PER": 8.5, "price": 75000}
   Output (초보자용):
   "삼성전자는 현재 75,000원입니다.

   **PER 8.5**란?
   → 주식의 '가격표'예요. 업종 평균(12)보다 낮아서 저렴한 편입니다.

   **결론:** 지금 매수를 고려해볼 만해요!"
   ↓
6. /chat/stream으로 실시간 전송
   - event: thought (도구 선택 과정)
   - event: tool_call (get_stock_price)
   - event: tool_result (75,000원)
   - event: answer (개인화된 응답)
```

---

## 📊 비교: 개인화 전 vs 후

### 시나리오: "삼성전자 분석"

**개인화 전 (일률적):**
```
삼성전자 (005930)
- 현재가: 75,000원
- PER: 8.5
- PBR: 1.2
- ROE: 15.3%
투자 의견: 매수
```

**개인화 후 (초보자):**
```
📊 삼성전자 간단 분석

**현재가:** 75,000원

**주요 지표:**
- **PER 8.5**
  이 회사의 "가격표"예요. 업종 평균(12)보다 낮아서 저렴한 편이에요.

- **PBR 1.2**
  회사의 "실제 가치"와 비교한 가격이에요. 1보다 높아서 조금 비싼 편이지만 괜찮은 수준이에요.

**결론:** 저평가 상태로 보여요. 지금 투자를 고려해볼 만해요!

💡 **용어 설명:**
- PER (주가수익비율): 회사가 1년에 버는 돈과 비교한 주가예요.
- PBR (주가순자산비율): 회사가 가진 재산과 비교한 주가예요.
```

**개인화 후 (전문가):**
```
## DCF Valuation - 삼성전자 (005930)

**Valuation Metrics:**
- PER: 8.5x (Sector: 12.0x, -29%)
- PBR: 1.2x (Sector: 1.5x, -20%)
- EV/EBITDA: 5.8x
- P/S: 0.9x

**DCF Analysis:**
- WACC: 8.0%
  - Risk-free rate: 3.5%
  - Beta: 1.2
  - Market risk premium: 5.5%
- Terminal growth: 3.0%
- Intrinsic Value: 85,000원
- Current Price: 75,000원
- Upside: +13.3%

**Sensitivity Analysis:**
```
         g=2%    g=3%    g=4%
WACC 7%  92,000  95,000  98,000
WACC 8%  82,000  85,000  88,000
WACC 9%  75,000  78,000  80,000
```

**Recommendation:** BUY (Target: 85,000원)
```

---

## 🚀 프론트엔드 PRD 요구사항 충족

### US-1.2: AI Thinking process display (P0) ✅

- ✅ `astream_events`로 사고 과정 수집
- ✅ `/chat/stream` SSE로 실시간 전송
- ✅ 도구 호출 과정 투명화
- ✅ Frontend에서 EventSource로 수신 가능

### US-5.1: 사용자 맞춤형 답변 (P1) ✅

- ✅ 초보자/중급자/전문가 수준별 차별화
- ✅ 용어 설명 자동 추가/제거
- ✅ 비유 사용 여부 조절
- ✅ 지표 개수 조절

---

## ⚠️ 알려진 이슈

1. **SSE 연결 안정성**
   - 장시간 연결 시 timeout 가능
   - Nginx 설정 필요 (`proxy_buffering off`)

2. **에러 처리**
   - Agent 실행 실패 시 fallback 필요
   - 네트워크 끊김 시 재연결 로직 필요

3. **성능**
   - Thinking Trace 수집이 응답 속도에 미치는 영향 측정 필요
   - 대량 동시 접속 시 부하 테스트 필요

---

## 🧪 테스트 (TODO)

```python
# tests/test_agents/test_aggregator.py
async def test_personalize_for_beginner():
    """초보자용 개인화 테스트"""
    agent_results = {
        "research": {
            "PER": 8.5,
            "current_price": 75000
        }
    }

    user_profile = {
        "expertise_level": "beginner",
        "wants_explanations": True,
        "wants_analogies": True
    }

    result = await personalize_response(agent_results, user_profile)

    assert "가격표" in result["response"]  # 비유 포함
    assert "용어 설명" in result["response"]  # 설명 포함
    assert len(result["response"]) < 500  # 간결함
```

---

## 📚 다음 단계 (Week 4)

1. **AI 생성 프로파일** (온보딩)
   - 스크리닝 응답 + 포트폴리오 분석
   - LLM이 자연어 프로파일 생성

2. **Memory 기반 학습**
   - 대화 중 선호도 감지
   - 프로파일 자동 업데이트

3. **Frontend 요구사항 API**
   - Artifact 저장 (`POST /artifacts/`)
   - 포트폴리오 미리보기 (`POST /portfolio/preview`)

---

**커밋:** `8d9c7ff` - Feat: 답변 개인화 및 Thinking 스트리밍 구현 (Week 3)

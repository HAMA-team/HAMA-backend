# 멀티 에이전트 실시간 시각화 가이드

> AI 에이전트들의 협업 과정을 프론트엔드에서 실시간으로 확인하는 방법

## 🎯 개요

HAMA 시스템의 **멀티 에이전트 실행 과정**을 프론트엔드에서 실시간으로 시각화할 수 있습니다.

### 시각화할 수 있는 것:

1. **Master Agent의 라우팅 결정**
   - 어떤 에이전트들을 호출할지 결정
   - 실행 순서 결정

2. **각 에이전트의 실행 상태**
   - Research Agent: 데이터 수집 → Bull 분석 → Bear 분석 → 합의
   - Strategy Agent: 전략 생성
   - Risk Agent: 리스크 분석

3. **LLM 호출 과정**
   - AI가 언제 호출되는지
   - 어떤 작업을 수행하는지

4. **최종 결과 집계**
   - Master Agent가 모든 결과를 종합

---

## 🚀 빠른 시작

### 1. 서버 실행

```bash
# 백엔드 서버 시작
cd /Users/elaus/PycharmProjects/HAMA-backend
PYTHONPATH=. uvicorn src.main:app --reload --port 8000
```

### 2. 프론트엔드 데모 열기

```bash
# 브라우저에서 열기
open frontend_demo.html

# 또는 직접 경로 입력
# file:///Users/elaus/PycharmProjects/HAMA-backend/frontend_demo.html
```

### 3. 테스트

1. 입력창에 **"삼성전자 분석해줘"** 입력
2. **"분석 시작"** 버튼 클릭
3. 실시간으로 진행 상황 확인!

---

## 📡 API 엔드포인트

### POST `/api/v1/chat/multi-stream`

멀티 에이전트 실행을 SSE(Server-Sent Events)로 스트리밍

**요청:**
```json
{
  "message": "삼성전자 분석해줘",
  "user_id": "user123",
  "conversation_id": "conv456",
  "automation_level": 2
}
```

**응답 (SSE 이벤트):**

| 이벤트 타입 | 설명 | 데이터 예시 |
|------------|------|------------|
| `master_start` | Master Agent 시작 | `{"message": "분석 시작..."}` |
| `master_routing` | 호출할 에이전트 결정 | `{"agents": ["research", "strategy"]}` |
| `agent_start` | 서브 에이전트 시작 | `{"agent": "research", "message": "..."}` |
| `agent_node` | 노드 실행 상태 | `{"agent": "research", "node": "collect_data", "status": "running"}` |
| `agent_llm_start` | LLM 호출 시작 | `{"agent": "research", "model": "claude"}` |
| `agent_llm_end` | LLM 호출 완료 | `{"agent": "research"}` |
| `agent_complete` | 에이전트 완료 | `{"agent": "research", "result": {...}}` |
| `master_aggregating` | 결과 집계 중 | `{"message": "종합 중..."}` |
| `master_complete` | 전체 완료 | `{"message": "최종 답변"}` |
| `error` | 에러 발생 | `{"error": "에러 메시지"}` |
| `done` | 스트리밍 종료 | `{}` |

---

## 💻 프론트엔드 구현

### React 예시

```javascript
import { useState, useEffect } from 'react';

function MultiAgentVisualization() {
  const [agentStatus, setAgentStatus] = useState({
    master: 'idle',
    research: 'idle',
    strategy: 'idle',
    risk: 'idle'
  });
  const [logs, setLogs] = useState([]);

  const startAnalysis = async (message) => {
    const response = await fetch('http://localhost:8000/api/v1/chat/multi-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: message,
        user_id: 'user123'
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n\n');

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          const eventMatch = line.match(/event: (.+)\ndata: (.+)/s);
          if (eventMatch) {
            const eventType = eventMatch[1];
            const data = JSON.parse(eventMatch[2]);

            handleEvent(eventType, data);
          }
        }
      }
    }
  };

  const handleEvent = (eventType, data) => {
    switch(eventType) {
      case 'master_routing':
        setLogs(prev => [...prev, `호출 에이전트: ${data.agents.join(', ')}`]);
        break;

      case 'agent_start':
        setAgentStatus(prev => ({
          ...prev,
          [data.agent]: 'running'
        }));
        setLogs(prev => [...prev, `${data.agent} 시작`]);
        break;

      case 'agent_node':
        setLogs(prev => [...prev, `[${data.agent}] ${data.node}: ${data.status}`]);
        break;

      case 'agent_complete':
        setAgentStatus(prev => ({
          ...prev,
          [data.agent]: 'complete'
        }));
        setLogs(prev => [...prev, `${data.agent} 완료: ${JSON.stringify(data.result)}`]);
        break;

      case 'master_complete':
        setLogs(prev => [...prev, `최종 답변: ${data.message}`]);
        break;
    }
  };

  return (
    <div>
      <h1>멀티 에이전트 시각화</h1>

      {/* 에이전트 상태 카드 */}
      <div className="agents">
        {Object.entries(agentStatus).map(([agent, status]) => (
          <div key={agent} className={`agent-card ${status}`}>
            <h3>{agent}</h3>
            <span className="status">{status}</span>
          </div>
        ))}
      </div>

      {/* 로그 */}
      <div className="logs">
        {logs.map((log, i) => (
          <div key={i}>{log}</div>
        ))}
      </div>

      {/* 입력 */}
      <input type="text" id="messageInput" />
      <button onClick={() => startAnalysis(document.getElementById('messageInput').value)}>
        분석 시작
      </button>
    </div>
  );
}
```

### Vue 예시

```vue
<template>
  <div class="multi-agent">
    <h1>멀티 에이전트 시각화</h1>

    <!-- 에이전트 상태 -->
    <div class="agents">
      <div v-for="(status, agent) in agentStatus" :key="agent" :class="['agent-card', status]">
        <h3>{{ agent }}</h3>
        <span>{{ status }}</span>
      </div>
    </div>

    <!-- 로그 -->
    <div class="logs">
      <div v-for="(log, i) in logs" :key="i">{{ log }}</div>
    </div>

    <!-- 입력 -->
    <input v-model="message" @keyup.enter="startAnalysis" />
    <button @click="startAnalysis">분석 시작</button>
  </div>
</template>

<script>
export default {
  data() {
    return {
      message: '',
      agentStatus: {
        master: 'idle',
        research: 'idle',
        strategy: 'idle',
        risk: 'idle'
      },
      logs: []
    }
  },

  methods: {
    async startAnalysis() {
      const response = await fetch('http://localhost:8000/api/v1/chat/multi-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: this.message,
          user_id: 'user123'
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventMatch = line.match(/event: (.+)\ndata: (.+)/s);
            if (eventMatch) {
              const eventType = eventMatch[1];
              const data = JSON.parse(eventMatch[2]);
              this.handleEvent(eventType, data);
            }
          }
        }
      }
    },

    handleEvent(eventType, data) {
      switch(eventType) {
        case 'agent_start':
          this.agentStatus[data.agent] = 'running';
          this.logs.push(`${data.agent} 시작`);
          break;

        case 'agent_complete':
          this.agentStatus[data.agent] = 'complete';
          this.logs.push(`${data.agent} 완료`);
          break;
      }
    }
  }
}
</script>
```

---

## 🎨 UI 디자인 예시

### 에이전트 카드 레이아웃

```
┌─────────────────────────────────────────┐
│  🧠 Master Agent              [실행 중] │
│  ├─ 라우팅 결정                      ✅  │
│  └─ 결과 집계 중...                  ⏳  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  📊 Research Agent            [실행 중] │
│  ├─ collect_data                     ✅  │
│  ├─ bull_analysis                    ✅  │
│  ├─ bear_analysis                    ⏳  │
│  └─ consensus                        ⏸️  │
│                                          │
│  결과 미리보기:                           │
│  추천: SELL                              │
│  목표가: 90,000원                        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  🎯 Strategy Agent            [대기 중] │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  ⚠️ Risk Agent                [대기 중] │
└─────────────────────────────────────────┘
```

### 타임라인 뷰

```
0s   Master Start
1s   ├─ Research Agent 시작
2s   │  ├─ collect_data (1.2s)
4s   │  ├─ bull_analysis (2.4s) 🤖 LLM 호출
6s   │  ├─ bear_analysis (2.1s) 🤖 LLM 호출
8s   │  └─ consensus (1.5s) 🤖 LLM 호출
10s  ├─ Strategy Agent 시작
12s  ├─ Risk Agent 시작
15s  └─ Master Aggregating
17s  ✅ Complete
```

---

## 🔧 고급 기능

### 1. 노드별 진행률 표시

```javascript
const [nodeProgress, setNodeProgress] = useState({});

// agent_node 이벤트에서 진행률 업데이트
if (eventType === 'agent_node') {
  const progress = data.status === 'complete' ? 100 :
                   data.status === 'running' ? 50 : 0;

  setNodeProgress(prev => ({
    ...prev,
    [`${data.agent}-${data.node}`]: progress
  }));
}
```

### 2. LLM 응답 스트리밍 (선택적)

```javascript
// 백엔드에서 agent_llm_stream 이벤트 활성화 시:
if (eventType === 'agent_llm_stream') {
  setStreamingText(prev => prev + data.content);
}
```

### 3. 에러 핸들링

```javascript
if (eventType === 'error') {
  setAgentStatus(prev => ({
    ...prev,
    [data.agent || 'master']: 'error'
  }));

  setErrorMessage(data.error);

  // UI에 에러 토스트 표시
  toast.error(data.error);
}
```

---

## 📊 LangSmith와 함께 사용

### LangSmith에서 추가로 볼 수 있는 정보:

1. **비용 분석**
   - 각 LLM 호출의 토큰 사용량
   - API 비용

2. **성능 메트릭**
   - 평균 응답 시간
   - 병목 구간 식별

3. **디버깅**
   - 실패한 호출 재현
   - 입력/출력 검사

**함께 사용하는 방법:**

```
프론트엔드 (실시간)        LangSmith (분석용)
       ↓                        ↓
   실시간 진행 상황          상세 trace 분석
   사용자 피드백            비용/성능 분석
   에러 알림                디버깅 및 최적화
```

---

## 🎯 실전 활용 예시

### 1. 대시보드 통합

```javascript
// 대시보드에서 실시간 분석 진행 상황 표시
<Dashboard>
  <ActiveAnalysis>
    <MultiAgentVisualization />
  </ActiveAnalysis>

  <RecentResults>
    {/* 완료된 분석 결과 */}
  </RecentResults>
</Dashboard>
```

### 2. 모바일 앱

```javascript
// React Native
import { useMultiAgentStream } from './hooks/useMultiAgentStream';

function AnalysisScreen() {
  const { status, logs, startAnalysis } = useMultiAgentStream();

  return (
    <View>
      <AgentStatusCards status={status} />
      <LogsScrollView logs={logs} />
      <TextInput onSubmit={startAnalysis} />
    </View>
  );
}
```

### 3. 채팅 인터페이스

```javascript
// 채팅 UI에 에이전트 실행 상황 표시
<ChatMessage type="system">
  <AgentProgress agent="research" status="running" />
  <span>Research Agent가 삼성전자를 분석하고 있습니다...</span>
</ChatMessage>

<ChatMessage type="ai">
  <AgentProgress agent="research" status="complete" />
  <span>분석 완료: SELL 추천, 목표가 90,000원</span>
</ChatMessage>
```

---

## 📝 체크리스트

### 백엔드 설정

- [x] `multi_agent_stream.py` 구현
- [x] `main.py`에 라우터 추가
- [x] CORS 설정 확인

### 프론트엔드 개발

- [ ] SSE 연결 로직 구현
- [ ] 에이전트 상태 관리
- [ ] UI 컴포넌트 디자인
- [ ] 에러 핸들링
- [ ] 로딩 상태 표시

### 테스트

- [ ] 서버 실행 확인
- [ ] SSE 연결 테스트
- [ ] 다양한 쿼리 테스트
- [ ] 에러 시나리오 테스트
- [ ] 성능 테스트

---

## 🆘 트러블슈팅

### 문제: SSE 연결이 안 됨

**확인:**
```bash
# CORS 설정 확인
curl -H "Origin: http://localhost:3000" http://localhost:8000/api/v1/chat/multi-stream
```

**해결:**
```python
# src/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중에는 * 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### 문제: 이벤트가 중복으로 발생

**원인:** 에이전트가 두 번 실행됨

**해결:**
```python
# 멀티 에이전트 스트림에서 ainvoke 제거
# astream_events만 사용
```

---

**작성일:** 2025-10-26
**최종 업데이트:** 2025-10-26

# Reasoning Event 스트림 사용 가이드

LangGraph 기반 멀티 에이전트 실행 결과를 사용자 친화적으로 시각화하기 위한 프론트엔드 가이드입니다. `POST /chat/multi-stream` SSE에 포함된 `reasoning_event` 메타데이터를 활용하면 에이전트의 사고 과정을 계획 → 데이터 수집 → 분석 → 도구 호출 → 최종 응답으로 자연스럽게 표현할 수 있습니다.

---

## 1. 이벤트 개요

- **Endpoint:** `POST /api/v1/chat/multi-stream`
- **전송 방식:** Server-Sent Events (SSE)
- **핵심 필드:** 모든 이벤트 payload는 기존 데이터 외에 `reasoning_event` 블록을 포함합니다.

```json
{
  "agent": "Research_Agent",
  "node": "planner",
  "reasoning_event": {
    "event_label": "agent_start",
    "phase": "planning",
    "status": "start",
    "actor": "agent",
    "agent": "Research_Agent",
    "node": "Research_Agent__planner",
    "depth": 1,
    "lineage": ["supervisor_node", "Research_Agent", "Research_Agent__planner"],
    "message": "Research_Agent 실행 시작",
    "metadata": {
      "langgraph_node": "Research_Agent__planner",
      "langgraph_step": 1
    }
  }
}
```

### 1.1 ReasoningPhase 값
| Phase | 의미 | 주 사용처 |
| --- | --- | --- |
| `supervision` | 마스터/슈퍼바이저 단계 | `master_start`, HITL, 최종 응답 |
| `planning` | 계획 수립/라우팅 | `agent_start` (planner), `master_routing` |
| `routing` | 에이전트 분기 결정 | `master_routing` |
| `agent_execution` | 일반 워커 실행 | 대부분의 `agent_*` |
| `data_collection` | 데이터/툴 조회 | `*_data_worker`, `tools_*` |
| `tool` | 툴 호출 | `tools_start`, `tools_complete` |
| `llm` | LLM 추론 | `agent_llm_start`, `agent_llm_end`, `agent_thinking` |
| `hitl` | 사용자 승인 루프 | `hitl_interrupt` |
| `finalization` | 응답 마무리 | `master_complete`, `done` |
| `system` | 시스템 상태 | `user_profile`, `error` |

### 1.2 ReasoningStatus 값
- `start`: 단계 진입
- `in_progress`: LLM 스트림 등 지속 이벤트
- `complete`: 정상 종료
- `info`: 정보성 업데이트 (`master_routing` 중간 상태 등)
- `error`: 실패

---

## 2. 프론트엔드 소비 패턴

### 2.1 공통 Hook 예시
```tsx
interface ReasoningEventPayload {
  event: string;              // SSE 이벤트 이름
  data: any;                  // 기존 payload
  reasoning_event: {
    event_label: string;
    phase: string;
    status: string;
    depth: number;
    message?: string;
    lineage: string[];
    metadata: Record<string, any>;
  };
}

function useReasoningStream(request: StreamRequest) {
  const [events, setEvents] = useState<ReasoningEventPayload[]>([]);

  useEffect(() => {
    const es = new EventSource('/api/v1/chat/multi-stream', { withCredentials: true });

    const handler = (event: MessageEvent) => {
      const payload = JSON.parse(event.data);
      setEvents((prev) => [...prev, { event: event.type, data: payload, reasoning_event: payload.reasoning_event }]);
    };

    ['agent_start','agent_complete','agent_llm_start','agent_llm_end','agent_thinking','tools_start','tools_complete','master_routing','master_complete','hitl_interrupt','error','done'].forEach((evt) => {
      es.addEventListener(evt, handler);
    });

    es.addEventListener('done', () => es.close());
    es.onerror = () => es.close();

    return () => es.close();
  }, [request]);

  return events;
}
```

### 2.2 UI 컴포넌트 팁

1. **색상/아이콘 맵핑**  
   - `phase`별 컬러를 지정하면 반복 라벨 없이 흐름이 눈에 들어옵니다.
   - 예: `planning` → 파랑, `data_collection` → 청록, `llm` → 보라, `tool` → 주황, `finalization` → 회색.

2. **계층 표현**  
   - `depth`만큼 들여쓰기하거나 collapsible tree로 구성하면 `lineage` 구조를 그대로 시각화할 수 있습니다.
   - branch depth 계산 로직을 프론트에서 구현할 필요가 없습니다.

3. **요약 헤더**  
   - 동일 `phase`나 `agent`가 연속되는 경우 `reasoning_event.message`와 `status`로 묶어서 “데이터 수집 · 6단계 완료” 같은 헤더를 만들고 세부 항목은 토글로 감춥니다.

4. **스트리밍 텍스트**  
   - `agent_thinking` 이벤트는 `status = in_progress`이며, `message`에 160자 미리보기가 들어가 있으니 먼저 간단한 요약을 보여주고 세부 내용은 hover/expand로 제공할 수 있습니다.

5. **오류/중단 처리**  
   - `status = error` 또는 `event = error` 시 별도 강조 색상과 재시도 버튼을 표시합니다.
   - `phase = hitl` 이벤트를 받으면 HITL 패널을 자동으로 열고, `approval_request`를 `data`에서 직접 파싱하면 됩니다.

---

## 3. Fallback & 히스토리

- SSE 연결이 끊겼을 경우 `reasoning_event.sequence_index`를 저장해 두었다가 REST API(`/chat/{conversation_id}/thinking` 예정)를 호출하면 이어서 렌더링 할 수 있습니다.
- `lineage` 배열의 마지막 값이 실제 LangGraph 노드명이므로, 동일 노드끼리 묶어 “Research_Agent > planner” 같은 계층형 레이블을 구성하면 UX 이해도가 높아집니다.

---

## 4. 체크리스트

| 체크 항목 | 설명 |
| --- | --- |
| Phase/Status 색상 지정 | `phase`별 색상 정의로 반복 텍스트 없이도 상태 파악 가능 |
| Depth 기반 들여쓰기 | `depth`만큼 padding/margin을 주어 트리 구조 표현 |
| 요약/펼치기 | `phase`나 `agent` 단위 그룹화를 제공해 로그 폭주를 방지 |
| HITL 연동 | `event='hitl_interrupt'` 수신 시 승인 패널 노출 |
| 오류 처리 | `status='error'` 수신 시 사용자에게 알림 및 재시도 옵션 제공 |

이 문서는 `reasoning_event` 스키마가 업데이트될 때마다 갱신해야 하며, 컬러 팔레트나 UI 패턴은 디자인팀 가이드에 맞춰 재정의하면 됩니다. 프론트는 더 이상 내부 LangGraph 라벨을 추측할 필요 없이, 서버가 제공하는 구조화된 메타데이터를 그대로 활용해 사고 과정을 시각적으로 전달할 수 있습니다.

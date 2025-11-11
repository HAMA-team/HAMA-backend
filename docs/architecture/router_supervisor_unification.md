# Router → Supervisor 통합 계획

## 1. 배경
- 현행 구조는 Router 기반 오케스트레이션(스트리밍 API)과 LangGraph Supervisor(`src/agents/graph_master.py`)가 공존한다.
- Router는 Structured Output 프롬프트를 통해 **질문 복잡도, 에이전트 목록, 워커 직접 호출, 개인화 설정, 직접 답변 생성**까지 담당하며, Supervisor도 비슷한 라우팅 규칙을 자체 프롬프트에 내장하고 있다.
- 동일한 라우팅 로직이 두 곳에 흩어져 있어 규칙 불일치·테스트·스트리밍 처리 지점이 중복된다.
- `/api/v1/chat`과 `/api/v1/chat/multi-agent-stream`은 동일한 LangGraph를 공유하지만, 전자는 동기 응답·후자는 SSE로 스트리밍한다는 점만 다르다.

## 2. 목표
1. **Supervisor 단일 오케스트레이터화**  
   - Router가 수행하던 판단과 프롬프트를 Supervisor 그래프의 Routing 노드로 편입한다.
2. **Worker 직통/직접 답변 케이스 내재화**  
   - Router의 `worker_action`/`direct_answer` 패턴을 LangGraph state와 노드 흐름으로 표현한다.
3. **스트리밍/HITL 일원화**  
   - `/multi_agent_stream`도 LangGraph `astream_events`에 기반하여 Supervisor 이벤트만 송출되도록 하고, Interrupt/HITL 저장 로직을 `/chat`과 공유한다.

## 3. Supervisor 중심 구조 설계
### 3.1 GraphState 확장 (`src/schemas/graph_state.py`)
- 다음 필드를 추가한다.
  - `routing_decision: Optional[dict]` (Router 프롬프트 전체 결과를 보존)
  - `depth_level: Optional[str]`
  - `personalization: Optional[dict]`
  - `worker_action: Optional[str]`, `worker_params: Optional[dict]`
  - `direct_answer: Optional[str]`
  - `clarification_needed: bool`, `clarification_message: Optional[str]`
- LangGraph reducer 지정이 필요한 항목(`agent_results`, `messages`)은 기존 규칙을 유지한다.

### 3.2 Routing Node
- Router 프롬프트(`src/agents/router/router_agent.py:214-395`)를 Supervisor 노드로 이식한다.
- 노드 입력: `query`, `user_profile`, 최근 `messages`.
- 노드 출력: GraphState의 위 신규 필드.
- Prompt 규칙/예시는 기존 Router 버전을 그대로 사용하여 행동 편차를 최소화한다.

### 3.3 라우팅 분기 로직
1. `worker_action` 존재 시 → `worker_direct_node`
   - `stock_price` / `index_price` 등 기존 워커 호출 패턴을 재현한다.
   - 성공 시 `final_response`에 자연어 응답을 저장하고 그래프 종료.
2. `direct_answer` 존재 시 → `direct_answer_node`
   - Router가 생성한 응답을 state에 기록 후 종료.
3. 그렇지 않으면 → 기존 Supervisor 프롬프트의 에이전트 선택을 Routing 결과 기반으로 대체하여 Research/Strategy/Risk/Trading/Portfolio 서브그래프를 호출한다.

### 3.4 스트리밍 이벤트
- `app.astream_events(..., version="v2")`를 `/multi_agent_stream`에서 호출하여 LangGraph 이벤트를 SSE로 매핑.
- 주요 매핑:
  - `on_chain_start` → `agent_start`
  - `on_chain_end` → `agent_complete`
  - `on_chat_model_start`/`on_chat_model_stream` → `agent_llm_start`/`agent_thinking`
  - Routing/Worker/Direct 답변 노드의 start/end 이벤트는 `master_routing`, `worker_start`, `master_complete`로 변환.
- 기존 Router 전용 SSE 로직은 제거되고, Supervisor 한 곳에서 모든 상태를 방출한다.

### 3.5 HITL/Interrupt 처리
- Trading/Portfolio 노드는 기존 LangGraph Interrupt 패턴을 유지한다.
- `/multi_agent_stream`도 Supervisor 실행 후 `configured_app.aget_state()`를 호출하여 `state.next`를 검사하거나, 이벤트 스트림 중 Interrupt 이벤트를 캐치하여 승인 요청을 곧바로 DB에 저장한다.
- ApprovalRequest 저장/메시지 작성 로직은 `src/services/hitl_interrupt_service.py`의 `handle_hitl_interrupt()`로 공통화하여 `/chat`과 `/multi_agent_stream` 모두 동일한 DB·히스토리 사이드이펙트를 갖도록 한다.

## 4. 단계별 마이그레이션
1. **GraphState/노드 정의 업데이트**
   - 신규 필드 추가, Routing Node/Worker Node/Direct Answer Node를 LangGraph에 추가.
2. **Prompt 이관**
   - Router 프롬프트를 Supervisor 노드로 옮기고, `router_agent.py`에는 Deprecated 안내만 남긴다.
3. **스트리밍 리팩터**
   - `/multi_agent_stream`를 LangGraph 이벤트 기반으로 재작성하고, 기존 Router 호출/워커 처리 코드를 제거.
4. **HITL 통합**
   - `src/services/hitl_interrupt_service.py`에서 ApprovalRequest 저장·세션 기록을 공통 처리하고, Interrupt 핸들링을 Supervisor 이벤트에서 직접 수행.
5. **테스트/문서 갱신**
   - `tests/integration/test_supervisor_routing.py` 갱신.
   - 스트리밍 e2e 테스트(히스토리·clarification·worker 단락) 추가.

## 5. 리스크 & 대응
- **라우팅 결과 불일치**: Router 프롬프트를 그대로 사용하되, LangGraph로 옮긴 뒤에도 A/B 비교 로그를 잠시 남겨 차이를 모니터링한다.
- **SSE 이벤트 회귀**: 이벤트 이름/페이로드를 기존과 동일하게 유지하고, 프런트엔드 소비 로직과 비교표를 문서화한다.
- **HITL 동작 변경**: Interrupt 이벤트 타이밍이 Router 흐름과 다를 수 있으므로 QA 시나리오(매수/매도/리밸런싱 승인)를 집중 검증한다.

## 6. 후속 정리
- `src/agents/router/router_agent.py`는 여전히 LangGraph 진입 노드에서 Structured Output을 제공하고 있으므로, 실제 코드가 라우터 의존성을 끊을 때까지 Deprecated 표기를 보류한다.
- Router 제거가 완료되면 `/src/agents/router` 모듈과 관련 API import를 삭제하고, 릴리스 노트에 반영한다.

## 7. API 소비 채널
- `/api/v1/chat`은 동기 HTTP 응답으로 최종 메시지·승인 여부를 한 번에 반환한다. Slack 봇, QA 스크립트 등 스트리밍이 필요 없는 클라이언트에 적합하다.
- `/api/v1/chat/multi-agent-stream`은 `astream_events(version="v2")`를 SSE로 노출해 노드별 진행 상황(LLM start/end, agent_complete 등)을 실시간 표시한다.
- 두 엔드포인트 모두 `build_graph()`에서 동일한 LangGraph 인스턴스를 가져다 쓰며, HITL Interrupt 역시 같은 state를 검사한다. 차이는 전송 방식·UI 피드백뿐이다.

## 8. 2025-11-11 업데이트
- ApprovalRequest 저장 및 히스토리 기록을 `src/services/hitl_interrupt_service.py::handle_hitl_interrupt`로 공통화해 `/chat`·`/multi_agent_stream` 모두 DB/세션/메시지 사이드 이펙트가 일치한다.
- 스트리밍 경로는 이제 Helper 결과를 SSE `hitl_interrupt` 페이로드로 포함해 프런트엔드가 승인 세부정보(종목, 수량, 비중 변화 등)를 즉시 표현할 수 있다.

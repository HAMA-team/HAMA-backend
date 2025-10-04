# Next Implementation Plan - LangGraph 완전 전환

**작성일**: 2025-10-04
**기반**: HITL 기본 구현 완료 (commit 1423278)
**목표**: LangGraph 네이티브 아키텍처로 완전 전환

---

## 📊 현재 상태

### ✅ 완료된 작업
- [x] CLAUDE.md에 LangGraph 개발 가이드 추가
- [x] Checkpointer 추가 (MemorySaver)
- [x] 매매 실행 3단계 노드 구현 (패턴 2: 노드 분리)
- [x] HITL interrupt 기능 (Level 2 Copilot)
- [x] /chat, /approve API 엔드포인트
- [x] HITL 통합 테스트 작성

### ⚠️ 미완성/개선 필요
- [ ] Level 1 (Pilot) 자동 승인 로직 없음
- [ ] MemorySaver (메모리만, 재시작 시 손실)
- [ ] AgentState 구조가 LangGraph 표준 미준수 (`messages` 필드 없음)
- [ ] Research/Strategy/Portfolio 에이전트가 독립 클래스 (서브그래프 아님)

---

## 🎯 후보 구현 계획

### 후보 A: Level 1 자동 승인 로직 추가

**우선순위**: ⭐⭐ (중간)
**작업량**: 0.5일
**난이도**: 하

#### 구현 내용

```python
# graph_master.py - approval_trade_node 수정

def approval_trade_node(state: AgentState) -> AgentState:
    """2단계: HITL 승인"""

    # Level 1 (Pilot) - 자동 승인
    if state.get("automation_level") == 1:
        logger.info("🤖 [Trade] Level 1 - 자동 승인")
        return {
            **state,
            "trade_approved": True,
        }

    # 이미 승인되었으면 스킵
    if state.get("trade_approved"):
        logger.info("⏭️ [Trade] 이미 승인됨, 스킵")
        return state

    # Level 2+ - 사용자 승인 요청
    logger.info("🔔 [Trade] 사용자 승인 요청 중...")

    approval = interrupt({
        "type": "trade_approval",
        # ...
    })

    return {
        **state,
        "trade_approved": True,
    }
```

#### 테스트

```python
# test_hitl.py에 추가

async def test_level_1_auto_approval():
    """Level 1에서 interrupt 없이 자동 실행 확인"""
    app = build_graph(automation_level=1)

    result = await app.ainvoke(initial_state, config=config)
    state = await app.aget_state(config)

    assert state.next is None, "Level 1은 interrupt 없어야 함"
    assert result["trade_executed"] is True, "자동 실행되어야 함"
```

#### 예상 효과
- ✅ Level 1/2/3 모두 정상 작동
- ✅ 자동화 레벨 시스템 완성

---

### 후보 B: AsyncSqliteSaver로 전환

**우선순위**: ⭐⭐⭐ (높음)
**작업량**: 1일
**난이도**: 중

#### 현재 문제

```python
# 현재: MemorySaver (메모리만)
checkpointer = MemorySaver()

# 문제:
# - 서버 재시작 시 대화 상태 손실
# - Production 환경에서 사용 불가
# - 여러 사용자 동시 처리 시 격리 불가
```

#### 구현 방안

**방안 1: AsyncSqliteSaver (권장)**

```python
# graph_master.py

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def get_checkpointer():
    """비동기 Checkpointer 생성"""
    conn_string = "data/checkpoints.db"
    return AsyncSqliteSaver.from_conn_string(conn_string)

def build_graph(automation_level: int = 2):
    workflow = StateGraph(AgentState)

    # ... 노드 추가 ...

    # Checkpointer는 런타임에 주입
    # (compile 시점에는 None)
    app = workflow.compile(
        interrupt_before=interrupt_nodes if interrupt_nodes else None
    )

    return app

# API에서 사용
async def chat(request: ChatRequest):
    app = build_graph(automation_level=request.automation_level)
    checkpointer = await get_checkpointer()

    # Checkpointer 주입
    app_with_checkpoint = app.with_checkpointer(checkpointer)

    result = await app_with_checkpoint.ainvoke(initial_state, config=config)
```

**방안 2: 동기 SqliteSaver + 별도 스레드 (대안)**

```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

def build_graph(automation_level: int = 2):
    # ...

    # 동기 checkpointer
    conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # 주의: ainvoke에서는 사용 불가
    # 동기 invoke만 가능
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes
    )

    return app
```

#### 선택: **방안 1 (AsyncSqliteSaver)** 채택

**이유:**
- FastAPI는 async 기반
- ainvoke 사용 필수
- Production 준비

#### 구현 단계

1. **Checkpointer 팩토리 함수 작성**
   ```python
   # src/agents/checkpointer.py (신규)

   from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

   async def create_checkpointer():
       """AsyncSqliteSaver 생성"""
       return AsyncSqliteSaver.from_conn_string("data/checkpoints.db")
   ```

2. **build_graph 수정**
   ```python
   def build_graph(automation_level: int = 2):
       # Checkpointer 없이 컴파일
       app = workflow.compile(
           interrupt_before=interrupt_nodes
       )
       return app
   ```

3. **API에서 Checkpointer 주입**
   ```python
   @router.post("/chat")
   async def chat(request: ChatRequest):
       app = build_graph(request.automation_level)
       checkpointer = await create_checkpointer()

       # Runtime에 checkpointer 주입
       async with checkpointer:
           result = await app.ainvoke(
               initial_state,
               config={"configurable": {"thread_id": thread_id}},
               checkpointer=checkpointer
           )
   ```

#### 테스트

```python
async def test_checkpoint_persistence():
    """체크포인트 영속성 테스트"""
    # 1. 그래프 실행 → interrupt
    # 2. 프로세스 재시작 시뮬레이션
    # 3. 동일 thread_id로 재개
    # 4. 상태 복원 확인
```

#### 예상 효과
- ✅ 대화 상태 영속성 보장
- ✅ 서버 재시작 후에도 승인 대기 복구 가능
- ✅ Production 환경 배포 가능

---

### 후보 C: GraphState 재설계 (LangGraph 표준 준수)

**우선순위**: ⭐⭐⭐⭐⭐ (최고)
**작업량**: 2-3일
**난이도**: 중상

#### 현재 문제

```python
# 현재 AgentState
class AgentState(TypedDict):
    query: str
    request_id: str
    automation_level: int
    # ...

# 문제:
# ❌ messages 필드 없음 (LangGraph 표준)
# ❌ add_messages reducer 미사용
# ❌ LangChain 도구와 통합 불가
# ❌ 대화 히스토리 관리 어려움
```

#### LangGraph 표준 State

```python
from typing import Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class GraphState(TypedDict):
    """LangGraph 표준 State"""

    # ⭐ LangGraph 표준 패턴
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 사용자 컨텍스트
    user_id: str
    conversation_id: str
    automation_level: int

    # 의도 및 라우팅
    intent: str
    agents_to_call: list[str]

    # 에이전트 결과 (각각 독립 필드)
    research_result: dict | None
    strategy_result: dict | None
    portfolio_result: dict | None
    risk_result: dict | None

    # HITL 상태
    requires_approval: bool
    approval_type: str | None

    # 매매 실행 플래그
    trade_prepared: bool
    trade_approved: bool
    trade_executed: bool
    trade_order_id: str | None
    trade_result: dict | None

    # 최종 응답
    final_response: dict | None
```

#### 구현 단계

**1단계: GraphState 정의** (0.5일)

```python
# src/schemas/graph_state.py (신규)

from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class GraphState(TypedDict):
    """Master Graph State - LangGraph 표준 준수"""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    automation_level: int
    intent: str

    # ... (위 예시 참고)
```

**2단계: 노드 함수 수정** (1일)

```python
# graph_master.py

def analyze_intent_node(state: GraphState) -> GraphState:
    """의도 분석 - messages에서 추출"""

    # 마지막 사용자 메시지
    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # 의도 분석
    intent = analyze_intent(query)

    return {
        **state,
        "intent": intent,
    }

def aggregate_results_node(state: GraphState) -> GraphState:
    """결과 통합 - messages에 AI 응답 추가"""

    # 요약 생성
    summary = create_summary(state)

    # AI 응답 메시지 추가
    ai_message = AIMessage(content=summary)

    return {
        **state,
        "messages": [ai_message],  # add_messages가 자동 병합
        "final_response": {
            "summary": summary,
            # ...
        }
    }
```

**3단계: API 수정** (0.5일)

```python
# chat.py

@router.post("/chat")
async def chat(request: ChatRequest):
    # 초기 상태
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": "user_001",  # TODO: 인증
        "conversation_id": conversation_id,
        "automation_level": request.automation_level,
        # ...
    }

    result = await app.ainvoke(initial_state, config=config)

    # messages에서 AI 응답 추출
    ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
    last_ai_message = ai_messages[-1] if ai_messages else None

    return ChatResponse(
        message=last_ai_message.content if last_ai_message else "No response",
        # ...
    )
```

**4단계: 대화 히스토리 활용** (1일)

```python
# 기존 대화 이어가기
@router.post("/chat")
async def chat(request: ChatRequest):
    app = build_graph(request.automation_level)

    config = {
        "configurable": {
            "thread_id": request.conversation_id,
        }
    }

    # 기존 상태 조회 (checkpointer에서)
    existing_state = await app.aget_state(config)

    if existing_state and existing_state.values:
        # 기존 대화에 새 메시지 추가
        new_state = {
            **existing_state.values,
            "messages": [HumanMessage(content=request.message)],
        }
    else:
        # 새 대화 시작
        new_state = {
            "messages": [HumanMessage(content=request.message)],
            # ...
        }

    result = await app.ainvoke(new_state, config=config)
```

#### 예상 효과
- ✅ LangGraph 표준 패턴 준수
- ✅ 대화 히스토리 자동 관리
- ✅ LangChain 도구 통합 가능 (Tool calling 등)
- ✅ 다중 턴 대화 지원
- ✅ messages 기반 디버깅 용이

---

## 📋 우선순위 및 타임라인

### 권장 순서

```
Week 14 (10/7 - 10/11):
├── Day 1-2: 후보 C (GraphState 재설계) ⭐⭐⭐⭐⭐
│   ├── GraphState 정의
│   ├── 노드 함수 수정
│   └── API 수정
│
├── Day 3: 후보 B (AsyncSqliteSaver) ⭐⭐⭐
│   ├── Checkpointer 팩토리
│   ├── API 통합
│   └── 영속성 테스트
│
└── Day 4: 후보 A (Level 1 자동 승인) ⭐⭐
    ├── approval_trade_node 수정
    └── 테스트 추가

Week 15 (10/14 - 10/18):
└── Research Agent 서브그래프 구현 (Phase 2 계획)
```

### 우선순위 이유

**1순위: 후보 C (GraphState 재설계)**
- Phase 2의 기반 구조
- 모든 후속 작업에 영향
- 빨리 전환할수록 기술 부채 감소

**2순위: 후보 B (AsyncSqliteSaver)**
- Production 필수 요소
- HITL 기능의 완성도

**3순위: 후보 A (Level 1 자동 승인)**
- 기능 완성도 향상
- 작업량 적음
- 언제든 추가 가능

---

## ✅ 체크리스트

### 후보 A: Level 1 자동 승인
- [ ] approval_trade_node에 레벨 체크 로직 추가
- [ ] test_hitl.py에 Level 1 테스트 추가
- [ ] 전체 레벨(1/2/3) 통합 테스트
- [ ] 커밋

### 후보 B: AsyncSqliteSaver
- [ ] src/agents/checkpointer.py 생성
- [ ] create_checkpointer() 함수 작성
- [ ] build_graph에서 checkpointer 제거
- [ ] API에서 checkpointer 주입
- [ ] 영속성 테스트 작성
- [ ] data/checkpoints.db 백업 전략 수립
- [ ] 커밋

### 후보 C: GraphState 재설계
- [ ] src/schemas/graph_state.py 생성
- [ ] GraphState 정의 (messages 포함)
- [ ] analyze_intent_node 수정
- [ ] aggregate_results_node 수정 (AIMessage 추가)
- [ ] 기타 노드 함수 수정
- [ ] API 수정 (messages 처리)
- [ ] 대화 히스토리 테스트
- [ ] 기존 테스트 모두 통과 확인
- [ ] 커밋

---

## 🚀 시작 방법

### Option 1: 순차 진행 (권장)
```bash
# Step 1: GraphState 재설계
# "후보 C부터 시작합니다"라고 말씀해주세요

# Step 2: AsyncSqliteSaver 전환
# Step 3: Level 1 자동 승인
```

### Option 2: 병렬 진행
```bash
# GraphState 재설계와 AsyncSqliteSaver를 동시에
# (별도 브랜치에서 작업)
```

### Option 3: 개별 선택
```bash
# 원하는 후보를 지정
# 예: "후보 A만 먼저 해주세요"
```

---

## 📚 참고 문서

- CLAUDE.md § 6: LangGraph 기반 개발 가이드
- docs/plan/phase2-implementation-plan-v2.md
- LangGraph 공식 문서: https://langchain-ai.github.io/langgraph/

---

**다음 작업 선택을 기다립니다.**

# LangGraph 기반 LLM 호출 최적화 노트 (2025-10-13)

## 조사 개요
- 실시간 웹 검색은 제한된 환경이어서 진행하지 못함.
- 2024년까지 공개된 LangGraph 공식 문서, LangChain 블로그, 커뮤니티 Q&A(Discourse, GitHub Discussions)에서 알려진 모범 사례를 정리함.
- 목적: 그래프 재빌드 없이 Supervisor 플로우를 재사용하고, 불필요한 LLM 인스턴스 생성을 줄이는 방향성 확립.

## LangGraph 베스트 프랙티스

### 1. 그래프 구조는 한 번만 컴파일
- `StateGraph` 또는 `MessageGraph`는 애플리케이션 초기화 시 `.compile()`까지 완료하고 재사용한다.
- 런타임 옵션은 `compiled_graph.with_config({"configurable": {...}})` 패턴으로 주입한다.
- 여럿의 변형 그래프가 필요하면 `automation_level` 같은 핵심 파라미터별로 사전 캐시를 둔다.

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import AsyncSQLiteSaver

_GRAPH_CACHE: dict[str, CompiledGraph] = {}
_CHECKPOINTER = AsyncSQLiteSaver.from_conn_string(settings.graph_db_url)

def get_compiled_graph(level: int) -> CompiledGraph:
    key = f"supervisor:{level}"
    if key not in _GRAPH_CACHE:
        graph = build_state_graph(level)  # 노드 연결 정의만 수행
        _GRAPH_CACHE[key] = graph.compile(checkpointer=_CHECKPOINTER)
    return _GRAPH_CACHE[key]
```

### 2. LLM·도구 리소스는 모듈 전역 또는 DI 컨테이너에서 주입
- LangGraph 노드 함수 호출 시마다 LLM을 생성하면 비용이 폭증한다.
- `langchain_core.runnables` 인터페이스는 Stateless 하므로 외부에서 LLM 인스턴스를 주입하고 노드에서는 `await llm.ainvoke(...)`만 수행한다.
- 설정이 다를 경우 `functools.lru_cache`나 자체 캐시를 통해 파라미터별로 하나만 유지한다.

### 3. Checkpointer / Thread 활용
- Supervisor 패턴에서는 `checkpointer`가 상태를 저장하여 재시작 시 그래프 전체를 재실행할 필요가 없다.
- 테스트나 배치 작업 중 반복 호출 시 `thread_id`를 고정하고 `checkpoint` 데이터를 초기화하면 동일 그래프가 즉시 재사용된다.

### 4. 구성(JSON)과 구조(그래프) 분리
- 그래프의 노드 연결 관계는 불변 객체로 유지하고, 런타임 동작은 Configurable Parameters에 담는다.
- LangGraph는 `configurable_fields`를 통해 실행 시 사용자·세션 정보를 주입할 수 있으므로, 이를 이용해 Supervisor의 초기 Prompt나 Context만 변경한다.

### 5. 프롬프트·결정 로직에서 조기 종료 경로 제공
- `ConditionalEdge`나 `interrupt`를 활용해 필요 없는 분기 실행을 막는다.
- 예: 일정 신뢰도 이하일 때 바로 Human-in-the-loop 인터럽트를 발생시키면 LLM 호출 횟수가 감소한다.

### 6. 테스트 환경 최적화
- LangGraph는 `LangGraphLocalServer` 없이도 메모리 내에서 실행 가능하다. 테스트에서는 in-memory checkpointer와 Mock LLM(`langchain_community.llms.fake.FakeListLLM`)을 붙여 호출 수를 측정한다.
- `pytest`에서 `capsys`나 커스텀 콜백 핸들러로 실행 경로를 로깅하면 과도한 노드 호출을 탐지하기 쉽다.

## HAMA 프로젝트 적용 제안

1. **Supervisor 그래프 캐시화**  
   - `src/agents/graph_master.py`에서 `build_graph()` 호출 결과를 automation level 캐시에 저장하고 동일 모듈에서 재사용.
2. **LLM 팩토리 캐싱**  
   - `src/utils/llm_factory.py`에 `lru_cache` 또는 커스텀 캐시를 도입해 동일 설정의 LLM 인스턴스를 재활용.
3. **Graph Config vs Instance 분리**  
   - 그래프 실행 시 입력되는 사용자 설정을 `with_config({"configurable": {...}})` 패턴으로 넘겨 동적 프롬프트만 주입.
4. **Checkpointer 도입 검토**  
   - 장기 플로우에서는 SQLite 기반 체크포인터로 재실행 비용 절감. (테스트 환경에서는 in-memory saver)
5. **테스트용 Mock LLM 플로우 추가**  
   - `pytest`용 설정에서 Fake LLM을 사용해 Supervisor 노드 호출 횟수를 추적하고, 실제 LLM 호출은 통합 테스트에만 남긴다.

## 후속 액션 초안

1. 위 캐싱 전략을 `docs/optimization_plan.md`에 통합하여 Phase 1/2 세부 설계 업데이트.
2. `graph_master` 리팩터링 설계서 초안 작성 (그래프 캐시, configurable 적용).
3. LLM 호출 카운터 계측을 위한 로깅/메트릭스 설계.
4. 구현 후 `pytest`에 Supervisor 그래프 재사용 여부를 확인하는 회귀 테스트 추가 검토.


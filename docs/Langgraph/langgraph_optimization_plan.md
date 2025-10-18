# LangGraph 최적화 적용 계획

본 문서는 `docs/optimization_plan.md`의 Phase 1~2를 LangGraph 공식 베스트 프랙티스에 맞춰 구현하기 위한 세부 전략을 정리한다. 모든 내용은 LangGraph/LangChain 최신 레퍼런스와 커뮤니티 권장안을 기반으로 한다.

---

## 1. 그래프 정의와 컴파일 분리

- **목표**: 동일한 그래프 구조를 매 호출마다 새로 빌드하지 않고, 한 번 컴파일한 `Runnable`을 재사용한다.
- **근거**: LangGraph 공식 문서에서 `StateGraph.define → compile()` 결과를 런타임마다 재사용한다고 명시한다. ([LangChain][1])
- **실행 계획**
  - `build_state_graph(automation_level: int)` 함수에서 순수하게 그래프 구조만 정의한다.
  - `compile_graph(automation_level: int, backend_key: str)` 함수에서 `build_state_graph` 호출 후 `.compile(checkpointer=...)`을 실행한다.
  - 결과물은 런타임에서 바로 실행하지 않고 `functools.lru_cache`로 감싸 동일 입력(automation_level, backend_key) 조합에서 재사용한다.

## 2. 런타임 설정 전달

- **목표**: `thread_id`, `request_id` 등 실행 시점 의존성은 `config={"configurable": {...}}`로 주입하고 그래프 재생성을 막는다.
- **근거**: persistence 가이드가 `invoke(..., config={"configurable": {"thread_id": ...}})` 패턴을 제시한다. ([LangChain][2])
- **실행 계획**
  - `run_graph()`에서 `compiled_app.with_config(...)`를 사용하거나 `compiled_app.ainvoke(..., config=config)`를 호출한다.
  - `thread_id`는 항상 `config["configurable"]["thread_id"]`에 실어 체크포인터와 연동한다.

## 3. 체크포인터 환경 스위칭

- **목표**: 테스트/개발에서는 인메모리, 운영에서는 SQLite 또는 Redis 기반 체크포인터를 사용한다.
- **근거**: LangGraph 체크포인터 패키지들이 정식으로 제공되며 환경별 전환을 권장한다. ([PyPI][3])
- **실행 계획**
  - `settings.graph_checkpoint_backend` 값을 `"memory" | "sqlite" | "redis"`로 제한하고, 이에 따라 적절한 Saver를 생성한다.
  - `compile_graph`에서 문자열 키(`backend_key`)만 `lru_cache`의 인자로 사용해 캐시 충돌을 피한다.
  - 서브그래프에는 별도 체크포인터를 지정하지 않고 상위 Supervisor의 설정을 그대로 활용한다. ([LangChain][6])

## 4. LLM 팩토리 캐싱

- **목표**: 노드와 Supervisor에서 LLM 인스턴스를 매번 새로 만들지 않고 공유한다.
- **근거**: 모델 캐싱은 LangChain에서 1급 기능으로 소개되며 팩토리 함수에 `lru_cache`를 적용하는 패턴이 합리적이다. ([LangChain][4])
- **실행 계획**
  - `src/utils/llm_factory.get_llm`에 `@lru_cache(maxsize=8)`를 적용하고 키를 `(provider, model_name, temperature, max_tokens)`로 구성한다.
  - Supervisor 및 서브그래프 노드에서는 가능하면 상위에서 주입받은 LLM을 재사용하고, 부득이한 경우 동일 파라미터로 팩토리를 호출한다.
  - 기존 `get_claude_llm`, `get_gemini_llm`도 동일 방식으로 캐싱하거나 기본 `get_llm` 경유하도록 정리한다.

## 5. 모니터링 및 캐시 검증

- **목표**: 최적화 이후 실제 호출 감소와 성능 개선을 관측한다.
- **근거**: LangChain 콜백 시스템은 실행 시간과 코스트 로깅을 지원하며, LangSmith 등 외부 트레이서 연동도 권장된다. ([LangChain][5])
- **실행 계획**
  - 그래프 실행 시점에 콜백을 등록해 캐시 히트율, LLM 호출 횟수, 실행 시간을 로깅한다.
  - 필요 시 metrics client(statsd 등)로 전송해 대시보드에서 추적한다.

---

## 적용 순서

1. `get_llm` 캐싱 도입 및 Supervisor/노드 의존성 정리  
2. `build_state_graph`/`compile_graph` 분리와 `lru_cache` 기반 재사용  
3. 체크포인터 선택 로직 구현 및 환경 변수 연동  
4. `run_graph()`에서 `with_config` 패턴으로 런타임 설정 전달  
5. 콜백/메트릭 로깅 추가 후 E2E 테스트로 개선 효과 측정  

---

## 참고 문헌

- [LangGraph Graphs 참조 문서][1]  
- [LangGraph Persistence 개념 문서][2]  
- [langgraph-checkpoint-sqlite 패키지][3]  
- [LangChain Model Cache 문서][4]  
- [LangChain Callbacks 개념 문서][5]  
- [LangGraph Memory 활용 가이드][6]  
- [LangGraph Supervisor 튜토리얼][7]

[1]: https://langchain-ai.github.io/langgraph/reference/graphs/?utm_source=chatgpt.com
[2]: https://langchain-ai.github.io/langgraph/concepts/persistence/?utm_source=chatgpt.com
[3]: https://pypi.org/project/langgraph-checkpoint-sqlite/?utm_source=chatgpt.com
[4]: https://python.langchain.com/docs/integrations/llm_caching/?utm_source=chatgpt.com
[5]: https://python.langchain.com/docs/concepts/callbacks/?utm_source=chatgpt.com
[6]: https://langchain-ai.github.io/langgraph/how-tos/memory/add-memory/?utm_source=chatgpt.com
[7]: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/?utm_source=chatgpt.com

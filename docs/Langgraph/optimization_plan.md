# API 최적화 계획

## 현황 분석 (2025-10-13)

### 문제점
1. **LLM 인스턴스 중복 생성**: 매 노드 실행마다 `get_llm()` 호출
2. **그래프 재생성**: `run_graph()`마다 새 그래프 빌드
3. **테스트 과부하**: E2E 테스트에서 50~100회 LLM API 호출

### API 호출 핫스팟
```
src/agents/graph_master.py:199         - run_graph()마다 build_graph()
src/agents/graph_master.py:53          - Supervisor마다 새 LLM
src/agents/research/nodes.py:178,260   - Bull/Bear마다 새 LLM
tests/test_random_scenario.py          - 한 번에 8+ 외부 API 호출
tests/test_agents/test_end_to_end.py   - 20+ run_graph() 호출
```

---

## 최적화 전략

### Phase 1: LLM 인스턴스 캐싱 (우선순위 ⭐⭐⭐)

**목표**: 같은 설정의 LLM은 재사용

**변경 파일**: `src/utils/llm_factory.py`

```python
from functools import lru_cache

# 현재 (매번 새 인스턴스)
def get_llm(temperature=0, max_tokens=4000):
    return ChatGoogleGenerativeAI(...)

# 개선 (캐싱)
@lru_cache(maxsize=8)
def get_llm(temperature: float = 0, max_tokens: int = 4000):
    """캐싱된 LLM 인스턴스 반환"""
    key = f"{settings.llm_provider}_{temperature}_{max_tokens}"
    # 같은 설정이면 캐시에서 반환
    ...
```

**예상 효과**:
- LLM API 초기화 오버헤드 **90% 감소**
- 테스트 실행 시간 **30~40% 단축**

---

### Phase 2: 그래프 인스턴스 캐싱 (우선순위 ⭐⭐⭐)

**목표**: automation_level별 그래프 재사용

**변경 파일**: `src/agents/graph_master.py`

```python
# 현재
async def run_graph(...):
    app = build_graph(automation_level)  # ❌ 매번 새로 빌드

# 개선 1: 글로벌 캐시
_graph_cache = {}

async def run_graph(...):
    cache_key = f"graph_{automation_level}"
    if cache_key not in _graph_cache:
        _graph_cache[cache_key] = build_graph(automation_level)

    app = _graph_cache[cache_key]
    ...

# 개선 2: functools.lru_cache 활용
@lru_cache(maxsize=3)  # 3개 레벨만
def build_graph(automation_level: int):
    ...
```

**예상 효과**:
- 그래프 빌드 오버헤드 **100% 제거** (2회차부터)
- Supervisor LLM 생성 횟수 **95% 감소**

#### LangGraph 모범 사례 반영 설계
- **컴파일 재사용**: `StateGraph` 정의는 `build_state_graph(automation_level)`로 분리하고, `graph.compile(checkpointer=...)` 결과만 캐시에 저장한다. (참고: `docs/langgraph_best_practices.md`)
- **Configurable 주입**: `run_graph()` 호출 시 `app.with_config({"configurable": {"request_meta": request.meta}})` 패턴으로 런타임 변수를 전달하여 그래프 구조 재빌드를 방지한다.
- **체크포인터 옵션화**: 현재는 인메모리 saver만 지원하며, 추후 외부 스토리지를 도입할 때 구성 옵션을 다시 검토한다.
- **LLM 리소스 재사용**: Supervisor 노드에서 사용할 LLM은 `get_llm()` 호출을 함수 외부에서 주입하거나 `lru_cache`로 감싼다. Phase 1과 연계해 Supervisor용 LLM을 한 번만 초기화한다.
- **메트릭 수집**: 캐시 적중률과 그래프 실행 횟수를 `statsd` 혹은 `settings.metrics_client`로 수집해 최적화 효과를 검증한다.

---

### Phase 5: 테스트 최적화 (우선순위 ⭐)

#### 5.1. Mock 기반 단위 테스트 분리

**목표**: 실제 API 호출 없는 빠른 테스트

```python
# tests/test_services/test_dart_service_unit.py (신규)
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_dart_service():
    service = dart_service
    service.api_client = AsyncMock()
    return service

async def test_search_corp_code_mock(mock_dart_service):
    """Mock 기반 빠른 테스트"""
    mock_dart_service.api_client.get.return_value = {...}
    result = await mock_dart_service.search_corp_code("삼성전자")
    assert result == "00126380"
```

#### 5.2. 통합 테스트 선택적 실행

```bash
# 빠른 테스트 (Mock)
pytest tests/ -m "not integration"

# 느린 테스트 (실제 API)
pytest tests/ -m "integration"
```

**마킹**:
```python
@pytest.mark.integration  # 실제 API 호출
async def test_full_flow():
    ...
```

#### 5.3. Random scenario 축소

`test_random_scenario.py`:
- 기본 시나리오 1개로 축소
- 다중 시나리오는 수동 실행만 (`python test_random_scenario.py 3`)

---

## 구현 우선순위

| Phase | 작업 | 예상 시간 | 효과 | 우선순위 |
|-------|------|----------|------|---------|
| 1 | LLM 캐싱 | 30분 | ⭐⭐⭐ | 1 |
| 2 | 그래프 캐싱 | 20분 | ⭐⭐⭐ | 1 |
| 3 | LLM 응답 캐싱 | 1시간 | ⭐⭐ | 2 |
| 4 | 외부 API TTL | 20분 | ⭐ | 3 |
| 5 | 테스트 분리 | 2시간 | ⭐ | 3 |

**권장**: Phase 1, 2를 먼저 구현 → **즉시 50% 이상 개선**

---

## 예상 개선 효과

### Before (현재)
```
E2E 테스트 실행 시간: ~5분
LLM API 호출: 80~100회
외부 API 호출: 30~40회
비용: $$$$
```

### After (Phase 1+2 완료)
```
E2E 테스트 실행 시간: ~2분 (-60%)
LLM API 호출: 20~30회 (-70%)
외부 API 호출: 30~40회 (동일)
비용: $$ (-50%)
```

### After (All Phases 완료)
```
E2E 테스트 실행 시간: ~1분 (-80%)
LLM API 호출: 5~10회 (-90%)
외부 API 호출: 5~10회 (-75%)
비용: $ (-80%)
```

---

## 다음 단계

1. ✅ 현황 분석 완료
2. ⏳ Phase 1, 2 구현 (권장)
3. ⏳ 효과 측정
4. ⏳ Phase 3~5 순차 구현

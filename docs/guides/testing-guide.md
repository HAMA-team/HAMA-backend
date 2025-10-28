# 테스트 작성 가이드라인

## 테스트 파일 구조 원칙

```
tests/
├── test_services/       # 서비스 레이어 단위 테스트
├── test_agents/         # Agent 레이어 테스트
├── test_api/            # API 엔드포인트 테스트 (선택)
└── test_*.py            # 통합/특수 테스트 (최소화)
```

## 새 테스트 작성 시 의사결정 프로세스

### 1단계: 테스트 대상 파악
- 서비스 로직 → `tests/test_services/`
- Agent 로직 → `tests/test_agents/`
- API 엔드포인트 → `tests/test_api/` 또는 루트
- 통합/E2E → 루트 (`test_integration.py` 등)

### 2단계: 기존 파일 vs 새 파일 결정

#### 기존 파일에 추가하는 경우 (우선):
- ✅ 같은 클래스/모듈의 다른 메서드 테스트
- ✅ 기존 테스트와 관련된 엣지 케이스
- ✅ 같은 카테고리의 테스트 (예: DART service의 다른 API)

#### 새 파일을 만드는 경우:
- ✅ 완전히 새로운 서비스/모듈
- ✅ 독립적인 기능 영역 (예: KIS vs DART)
- ✅ 기존 파일이 너무 커짐 (200줄 초과 시 고려)

### 3단계: 파일명 규칙

```python
# 서비스 테스트
test_services/test_{service_name}_service.py

# Agent 테스트
test_agents/test_{agent_name}_agent.py

# 통합 테스트
test_{feature}_integration.py
```

## 의사결정 예시

### 예시 1: DART 서비스에 새 API 메서드 추가
```
상황: dart_service.py에 get_disclosure() 메서드 추가
결정: ✅ test_services/test_dart_service.py에 test_get_disclosure() 추가
이유: 같은 서비스의 다른 메서드, 기존 파일에 통합
```

### 예시 2: 완전히 새로운 뉴스 서비스
```
상황: news_service.py 신규 생성
결정: ✅ test_services/test_news_service.py 신규 생성
이유: 독립적인 새 서비스, 별도 파일 필요
```

### 예시 3: Research Agent에 새 노드 추가
```
상황: research/nodes.py에 sentiment_analysis_node 추가
결정: ✅ test_agents/test_research_agent.py에 test_sentiment_analysis_node() 추가
이유: 같은 Agent 내 노드, 기존 파일에 통합
```

### 예시 4: 새로운 Agent 추가
```
상황: monitoring_agent/ 디렉토리 신규 생성
결정: ✅ test_agents/test_monitoring_agent.py 신규 생성
이유: 완전히 새로운 Agent, 별도 파일 필요
```

## 테스트 작성 체크리스트

### 테스트 작성 전:
- [ ] 테스트 대상이 services인지 agents인지 API인지 확인
- [ ] 해당 카테고리에 기존 테스트 파일이 있는지 검색
- [ ] 기존 파일에 추가할 수 있는지 검토 (라인 수, 관련성)
- [ ] 새 파일이 필요하다면 명확한 이유가 있는지 확인

### 테스트 작성 후:
- [ ] `if __name__ == "__main__":` 블록 추가 (독립 실행 가능)
- [ ] pytest와 직접 실행 모두 테스트
- [ ] 테스트 문서화 (docstring)
- [ ] tests/README.md 업데이트 (필요시)

## 안티패턴 (피해야 할 것)

### ❌ 임시 테스트 파일 남발
```
test_feature_temp.py        # 작업 후 정리 안 함
test_feature_v2.py          # 버전별로 파일 생성
test_feature_backup.py      # 백업 파일 생성
```

### ❌ 과도한 파일 분리
```
test_dart_service_search.py       # 메서드 하나당 파일
test_dart_service_financial.py    # → 하나로 통합해야 함
test_dart_service_company.py
```

### ❌ 애매한 파일명
```
test_improvements.py        # 무엇을 개선했는지 불명확
test_temp.py                # 임시 파일 명시
test_new_feature.py         # 기능명이 구체적이지 않음
```

## 베스트 프랙티스

### ✅ 명확한 구조
```
tests/
├── test_services/
│   ├── test_dart_service.py      # DART 관련 모든 테스트
│   ├── test_kis_service.py       # KIS 관련 모든 테스트
│   └── test_stock_data_service.py
├── test_agents/
│   ├── test_research_agent.py    # Research Agent 모든 노드
│   └── test_strategy_agent.py    # Strategy Agent 모든 노드
└── test_integration.py            # 전체 통합 테스트
```

### ✅ 테스트 클래스로 그룹화
```python
# test_services/test_dart_service.py
class TestDARTService:
    """DART Service 전체 테스트"""

    async def test_search_corp_code(self):
        """종목코드 검색"""
        pass

    async def test_get_financial_statement(self):
        """재무제표 조회"""
        pass

    async def test_cache_mechanism(self):
        """캐싱 검증"""
        pass
```

### ✅ 독립 실행 가능
```python
if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        tester = TestDARTService()
        await tester.test_search_corp_code()
        await tester.test_get_financial_statement()

    asyncio.run(main())
```

## 테스트 및 API 키 사용 원칙

### ❌ 절대 하지 말 것

1. **테스트에서 API 키가 없다고 skip 처리하지 말 것**
   - `@pytest.mark.skipif(no api key)` 같은 패턴 절대 금지
   - API 키가 필요한 테스트는 실패하도록 두어야 함

2. **LLM 호출 실패 시 mock 데이터로 대체하지 말 것**
   - "API 키 없으면 mock 응답" 같은 fallback 로직 금지
   - 실패는 실패로 명확히 드러나야 함

3. **테스트 환경에서 가짜 API 키 사용 금지**
   - `os.environ["OPENAI_API_KEY"] = "test-key-not-used"` 같은 코드 금지
   - 실제 키가 없으면 테스트가 실패해야 정상

### ✅ 올바른 방법

1. **모든 환경에서 실제 API 키 사용**
   - 테스트 환경에서도 `.env` 파일의 실제 키 사용
   - `src.config.settings.settings.OPENAI_API_KEY` 사용

2. **실패는 명확하게**
   - API 키가 없으면 → 테스트 실패
   - LLM 호출 실패하면 → 에러 발생
   - 네트워크 문제 있으면 → 테스트 실패

3. **환경 변수 의존성 명시**
   - README나 문서에 필수 환경 변수 명시
   - 개발자가 직접 `.env` 파일 설정하도록 안내

### 예시

#### ❌ 잘못된 예:
```python
# 테스트 skip
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No API key")
def test_llm():
    ...

# Mock fallback
try:
    response = llm.invoke(query)
except:
    return {"answer": "mock response"}  # ❌ 절대 안 됨
```

#### ✅ 올바른 예:
```python
# API 키는 settings에서 가져오기
from src.config.settings import settings

def call_llm(query: str):
    llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY)  # 실제 키
    response = llm.invoke(query)  # 실패하면 에러 발생
    return response

# 테스트도 실제 키 사용
def test_llm():
    result = call_llm("test")
    assert result is not None  # 키 없으면 여기서 실패
```

## 요약

1. **기존 파일 우선**: 같은 카테고리면 기존 파일에 추가
2. **새 파일 최소화**: 독립적인 모듈/서비스만 새 파일
3. **임시 파일 금지**: 작업 완료 후 반드시 정리
4. **명확한 구조**: services/agents/api로 분류
5. **문서화 필수**: 변경 시 README 업데이트
6. **실제 API 키 사용**: Mock/Skip 없이 실제 환경 테스트

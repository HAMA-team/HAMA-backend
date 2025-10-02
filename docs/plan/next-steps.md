# HAMA Backend - 추후 진행 계획

**작성일**: 2025-10-02
**Phase**: Phase 1 → Phase 2 전환

---

## 📊 현재 상태 요약

### ✅ 완료된 작업 (Phase 1: Week 1-8)

**진행률: 80%**

- ✅ 프로젝트 기반 구조 (100%)
- ✅ FastAPI 백엔드 (100%)
- ✅ PostgreSQL DB + 19개 테이블 (100%)
- ✅ 9개 에이전트 Mock 구현 (100%)
- ✅ LangGraph 오케스트레이션 (100%)
- ✅ Chat API 통합 (100%)
- ✅ HITL 트리거 로직 (100%)

### ⏭️ 남은 작업

- ⏸️ E2E 테스트 (0%)
- ⏸️ 성능 측정 (0%)
- ⏸️ 실제 데이터 연동 (Phase 2)

---

## 🎯 즉시 실행 (Week 9-10)

### 1. E2E 테스트 환경 구축 (1-2시간)

**목표**: pytest 기반 테스트 환경 완성

**작업 항목**:
- [ ] `pytest.ini` 작성
  ```ini
  [pytest]
  testpaths = tests
  python_files = test_*.py
  python_classes = Test*
  python_functions = test_*
  asyncio_mode = auto
  ```

- [ ] `tests/conftest.py` 작성 (fixtures)
  ```python
  # DB fixture
  @pytest.fixture
  async def test_db():
      # 테스트 DB 설정

  # API client fixture
  @pytest.fixture
  def client():
      return TestClient(app)
  ```

- [ ] 테스트용 환경 변수 설정
  ```bash
  # .env.test
  DATABASE_URL=postgresql://test:test@localhost:5432/hama_test
  ```

**산출물**:
- pytest.ini
- tests/conftest.py
- .env.test

---

### 2. 3가지 핵심 시나리오 테스트 (2-3시간)

#### 시나리오 1: 종목 분석
**테스트 파일**: `tests/test_e2e_stock_analysis.py`

```python
async def test_stock_analysis_flow():
    """
    시나리오: "삼성전자 분석해줘"

    검증 항목:
    1. 의도 분석: stock_analysis
    2. 호출 에이전트: research_agent, strategy_agent, risk_agent
    3. 응답 포맷 확인
    4. HITL 트리거: False
    """
    response = await client.post("/v1/chat/", json={
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    })

    assert response.status_code == 200
    data = response.json()

    # 의도 확인
    assert data["metadata"]["intent"] == "stock_analysis"

    # 에이전트 호출 확인
    agents = data["metadata"]["agents_called"]
    assert "research_agent" in agents
    assert "strategy_agent" in agents
    assert "risk_agent" in agents

    # HITL 미발동
    assert data["requires_approval"] == False
```

#### 시나리오 2: 매매 실행 + HITL
**테스트 파일**: `tests/test_e2e_trade_execution.py`

```python
@pytest.mark.parametrize("automation_level,expected_hitl", [
    (1, False),  # Pilot: HITL 미발동
    (2, True),   # Copilot: HITL 발동
    (3, True),   # Advisor: HITL 발동
])
async def test_trade_execution_hitl(automation_level, expected_hitl):
    """
    시나리오: "삼성전자 1000만원 매수"

    검증 항목:
    1. 의도 분석: trade_execution
    2. HITL 트리거: 자동화 레벨별로 다름
    3. approval_request 구조 확인
    """
    response = await client.post("/v1/chat/", json={
        "message": "삼성전자 1000만원 매수",
        "automation_level": automation_level
    })

    data = response.json()

    # 의도 확인
    assert data["metadata"]["intent"] == "trade_execution"

    # HITL 확인
    assert data["requires_approval"] == expected_hitl

    if expected_hitl:
        # approval_request 구조 검증
        assert data["approval_request"] is not None
        assert "type" in data["approval_request"]
        assert "risk_level" in data["approval_request"]
```

#### 시나리오 3: 포트폴리오 리밸런싱
**테스트 파일**: `tests/test_e2e_rebalancing.py`

```python
async def test_portfolio_rebalancing():
    """
    시나리오: "포트폴리오 리밸런싱"

    검증 항목:
    1. 의도 분석: rebalancing
    2. 호출 에이전트: portfolio_agent, strategy_agent
    3. 자동화 레벨 2에서 HITL 트리거
    """
    response = await client.post("/v1/chat/", json={
        "message": "포트폴리오 리밸런싱해줘",
        "automation_level": 2
    })

    data = response.json()

    assert data["metadata"]["intent"] == "rebalancing"
    assert "portfolio_agent" in data["metadata"]["agents_called"]
    assert data["requires_approval"] == True
```

**산출물**:
- tests/test_e2e_stock_analysis.py
- tests/test_e2e_trade_execution.py
- tests/test_e2e_rebalancing.py

---

### 3. 통합 테스트 (1-2시간)

**테스트 파일**: `tests/test_integration.py`

**검증 항목**:
- [ ] LangGraph StateGraph 플로우
  ```python
  async def test_langgraph_flow():
      # 각 노드 순차 실행 확인
      # 상태 전달 확인
  ```

- [ ] 에이전트 간 상태 전달
  ```python
  async def test_agent_state_passing():
      # context 전달 확인
      # 결과 누적 확인
  ```

- [ ] 에러 핸들링
  ```python
  async def test_error_handling():
      # 에이전트 실패 시 처리
      # 부분 실패 시 동작
  ```

**산출물**:
- tests/test_integration.py

---

### 4. 문서 업데이트 (30분)

- [ ] `docs/progress.md` 최신화
  - Week 9-10 체크리스트 업데이트
  - 진행률 갱신

- [ ] `README.md` 테스트 섹션 추가
  ```markdown
  ## Testing

  ### Run E2E Tests
  pytest tests/test_e2e_*.py

  ### Run All Tests
  pytest
  ```

- [ ] `docs/testing-guide.md` 작성 (새로 생성)
  - 테스트 실행 방법
  - 테스트 작성 가이드
  - CI/CD 준비

**산출물**:
- docs/progress.md (업데이트)
- README.md (업데이트)
- docs/testing-guide.md (신규)

---

## 🚀 다음 세션 (Phase 2 준비)

### 5. 성능 측정 및 최적화 (2-3시간)

**목표**: 평균 응답 속도 < 3초

- [ ] 응답 속도 측정
  ```python
  # tests/test_performance.py
  async def test_response_time():
      # 10회 측정 평균
      # 목표: < 3초
  ```

- [ ] 병렬 처리 최적화
  - asyncio.gather 최적화
  - 에이전트 호출 병렬화 확인

- [ ] 캐싱 전략 검토
  - Redis 캐싱 설계 (Phase 2)
  - 에이전트 결과 캐싱 전략

**산출물**:
- tests/test_performance.py
- docs/performance-report.md

---

### 6. 데모 준비 (1-2시간)

**목표**: 캡스톤 발표 준비

- [ ] Mock 데이터 보강
  - 더 현실적인 시나리오
  - 다양한 종목 데이터

- [ ] 데모 시나리오 스크립트
  ```markdown
  # 데모 시나리오
  1. 종목 분석 (삼성전자)
  2. 매매 지시 + HITL
  3. 포트폴리오 현황
  4. 리밸런싱 제안
  ```

- [ ] 발표 자료 작성
  - 아키텍처 다이어그램
  - 플로우 차트
  - 데모 영상

**산출물**:
- scripts/demo_scenarios.py
- docs/demo-guide.md
- 발표 자료 (PPT/PDF)

---

## 📅 Phase 2: 실제 구현 (Week 11-16)

### 7. 데이터 소스 연동

**우선순위 순서**:

1. **pykrx (1주)** - 주가 데이터
   ```python
   # src/services/pykrx_service.py
   - 일별 주가 조회
   - 시가총액 조회
   - 거래량 분석
   ```

2. **DART API (1주)** - 재무제표, 공시
   ```python
   # src/services/dart_service.py
   - 재무제표 조회
   - 공시 검색
   - 공시 요약 (LLM)
   ```

3. **뉴스 크롤링 (1주)** - 네이버 금융
   ```python
   # src/services/news_scraper.py
   - 뉴스 크롤링
   - 감정 분석
   - 종목별 분류
   ```

4. **한국투자증권 API (Phase 3)** - 실시간
   - Phase 2에서는 제외
   - Phase 3에서 실제 매매 시 필요

---

### 8. AI 에이전트 실제 구현

**Mock → Real 전환 우선순위**:

#### 1. 데이터 수집 에이전트 (1-2주)
```python
# src/agents/data_collection.py

# Phase 1: Mock
def _get_mock_response():
    return mock_data

# Phase 2: Real
async def process(self, input_data):
    # pykrx 호출
    price_data = await pykrx_service.get_price(stock_code)

    # DART 호출
    financial_data = await dart_service.get_financials(stock_code)

    # 뉴스 크롤링
    news_data = await news_scraper.get_news(stock_code)

    return AgentOutput(...)
```

#### 2. 리서치 에이전트 (2주)
```python
# src/agents/research.py

async def process(self, input_data):
    # 1. 데이터 수집 에이전트 호출
    data = await data_collection_agent.execute(input_data)

    # 2. 재무비율 계산
    ratios = calculate_financial_ratios(data)

    # 3. 기술적 지표 (TA-Lib)
    technical = calculate_technical_indicators(data)

    # 4. LLM 기반 분석
    analysis = await llm_analyze(ratios, technical, news)

    return AgentOutput(...)
```

#### 3. 전략 에이전트 (3주)
```python
# src/agents/strategy.py

# Bull/Bear 서브에이전트 구현
class BullAgent:
    async def analyze(self, data):
        # LLM 기반 상승 근거 분석

class BearAgent:
    async def analyze(self, data):
        # LLM 기반 하락 근거 분석

# 메인 전략 에이전트
async def process(self, input_data):
    # 리서치 결과 가져오기
    research = await research_agent.execute(input_data)

    # Bull/Bear 분석
    bull_result = await bull_agent.analyze(research)
    bear_result = await bear_agent.analyze(research)

    # Consensus 계산
    consensus = calculate_consensus(bull_result, bear_result)

    # 매매 시그널 생성
    signal = generate_trading_signal(consensus)

    return AgentOutput(...)
```

#### 4. 포트폴리오 에이전트 (3주)
```python
# src/agents/portfolio.py

async def process(self, input_data):
    # 1. 현재 포트폴리오 조회
    current = get_current_portfolio()

    # 2. 최적화 알고리즘 (Mean-Variance)
    optimal = optimize_portfolio(current, constraints)

    # 3. 리밸런싱 필요성 판단
    if needs_rebalancing(current, optimal):
        # 4. 거래 계획 생성
        trades = generate_trade_plan(current, optimal)

    return AgentOutput(...)
```

#### 5. 리스크 에이전트 (2주)
```python
# src/agents/risk.py

async def process(self, input_data):
    # 1. VaR (Value at Risk) 계산
    var = calculate_var(portfolio, confidence=0.95)

    # 2. 집중도 리스크
    concentration = calculate_concentration_risk(portfolio)

    # 3. 시뮬레이션 (Monte Carlo)
    scenarios = run_monte_carlo(portfolio, iterations=10000)

    # 4. 경고 생성
    warnings = generate_warnings(var, concentration, scenarios)

    return AgentOutput(...)
```

---

## 📊 예상 일정

| 기간 | 작업 | 소요 시간 |
|------|------|-----------|
| **이번 주** | E2E 테스트 + 문서화 | 4-6시간 |
| **다음 주** | 성능 측정 + 데모 준비 | 2-3시간 |
| **Week 11-12** | 데이터 소스 연동 | 2주 |
| **Week 13-14** | 리서치 + 데이터 수집 에이전트 | 2주 |
| **Week 15-17** | 전략 에이전트 (Bull/Bear) | 3주 |
| **Week 18-20** | 포트폴리오 에이전트 | 3주 |
| **Week 21-22** | 리스크 에이전트 | 2주 |
| **Week 23-24** | 통합 테스트 + 최적화 | 2주 |

**총 예상 기간**: 약 14주

---

## 🎯 MVP 완성 조건 체크리스트

### Phase 1 (현재)
- [x] 프로젝트 구조 완성
- [x] 9개 에이전트 Mock 구현
- [x] LangGraph 오케스트레이션
- [x] Chat API 통합
- [ ] E2E 테스트 3개 통과
- [ ] 평균 응답 속도 < 3초
- [ ] HITL 정확도 > 95%

### Phase 2 (예정)
- [ ] 5개 데이터 소스 연동
- [ ] 5개 에이전트 실제 구현
- [ ] 백테스팅
- [ ] 베타 테스트 (5명 이상)
- [ ] 만족도 80% 이상

---

## 📝 참고 문서

**현재 문서**:
- docs/PRD.md - 제품 요구사항
- docs/progress.md - 진행 상황
- docs/plan/agent-implementation-details.md - 에이전트 구현 상세
- docs/plan/data-sources-integration.md - 데이터 소스 연동

**생성 예정**:
- docs/testing-guide.md - 테스트 가이드
- docs/performance-report.md - 성능 리포트
- docs/demo-guide.md - 데모 가이드

---

## ⚠️ 주의사항

1. **Mock 데이터 의존성**
   - Phase 2 전환 시 Mock과 Real 구현 병행
   - 테스트는 계속 Mock 데이터 사용

2. **API 레이트 리밋**
   - DART API: 10,000 requests/day
   - pykrx: 제한 없음
   - 캐싱 전략 필수

3. **LLM 비용 관리**
   - GPT-4: $0.03/1K tokens (input)
   - 에이전트당 평균 2K tokens 예상
   - 월 예산: ~$100

4. **캡스톤 데모 준비**
   - 실제 데이터 없이도 데모 가능
   - Mock 데이터로 완전한 플로우 시연
   - 실제 구현은 추가 점수

---

**문서 끝**
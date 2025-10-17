# HAMA Backend 테스트 가이드

## 📁 테스트 구조

```
tests/
├── conftest.py                          # Pytest 설정 및 공통 fixture
├── __init__.py
│
├── test_services/                       # 서비스 레이어 단위 테스트
│   ├── test_dart_service.py            # DART API 서비스 (종목코드 매핑, 재무제표)
│   ├── test_stock_data_service.py      # 주가 데이터 서비스 (FinanceDataReader)
│   └── test_portfolio_optimizer.py     # 포트폴리오 최적화 (동적 비중 계산)
│
├── test_agents/                         # Agent 레이어 테스트
│   ├── test_strategy_agent.py          # Strategy Agent (섹터 로테이션, 자산 배분)
│   └── test_end_to_end.py              # E2E 통합 테스트
│
├── test_api_chat.py                     # API 레이어 테스트 (Chat 엔드포인트)
├── test_kis_service.py                  # KIS API 서비스 (한국투자증권)
├── test_kis_integration.py              # KIS API 통합 테스트
└── test_integration.py                  # 전체 통합 테스트 (Rate Limit, Portfolio Mock 제거 검증)
```

## 🧪 테스트 실행

### 전체 테스트 실행
```bash
PYTHONPATH=. pytest
```

### 특정 디렉토리 테스트
```bash
# Service 테스트만
PYTHONPATH=. pytest tests/test_services/ -v

# Agent 테스트만
PYTHONPATH=. pytest tests/test_agents/ -v
```

### 특정 파일 테스트
```bash
PYTHONPATH=. pytest tests/test_services/test_dart_service.py -v

# verbose + 로그 출력
PYTHONPATH=. pytest tests/test_services/test_dart_service.py -v -s
```

### 특정 테스트만 실행
```bash
PYTHONPATH=. pytest tests/test_services/test_dart_service.py::TestDARTService::test_cache_mechanism -v
```

## 📊 테스트 커버리지

### Services (3개 파일, 12개 테스트)

#### test_dart_service.py (4개)
- ✅ 주요 종목 고유번호 조회
- ✅ Redis 캐싱 메커니즘
- ✅ 잘못된 종목코드 처리
- ✅ 전체 종목 매핑 (3,901개)

#### test_stock_data_service.py (5개)
- ✅ 개별 종목 주가 조회
- ✅ 시장 지수 조회 (Rate Limit 방지)
- ✅ 캐싱 검증
- ✅ 수익률 계산
- ✅ 종목 리스트 조회

#### test_portfolio_optimizer.py (4개)
- ✅ Strategy 결과 기반 목표 비중 계산
- ✅ Fallback 동작 (Strategy 없을 때)
- ✅ 위험 성향별 비중 차이
- ✅ 성과 지표 계산 (수익률, 변동성, Sharpe)

### Agents (2개 파일, 5개 테스트)

#### test_strategy_agent.py (4개)
- ✅ 섹터 로테이션 (실제 데이터 기반)
- ✅ 자산 배분 (변동성 기반 조정)
- ✅ 위험 허용도별 배분 차이
- ✅ 시장 사이클별 전략 차이

#### test_end_to_end.py (1개)
- ✅ 전체 플로우 통합 테스트

### Integration (3개 파일)

#### test_integration.py
- ✅ Rate Limit 개선 검증
- ✅ Portfolio Optimizer 통합
- ✅ Mock 데이터 제거 확인

#### test_kis_integration.py
- ✅ KIS API 실제 계좌 조회
- ✅ 매매 주문 테스트

## 🚨 주의사항

### 환경 변수 필요
테스트 실행 전 `.env` 파일에 다음 키가 설정되어 있어야 합니다:

```env
# LLM API (필수)
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# DART API (필수)
DART_API_KEY=your-dart-key

# KIS API (선택 - KIS 테스트 시)
KIS_APP_KEY=your-kis-key
KIS_APP_SECRET=your-kis-secret
KIS_ACCOUNT_NUMBER=your-account-number

# Redis (필수)
REDIS_URL=redis://localhost:6379/0
```

### Rate Limit 관련
- `test_stock_data_service.py`의 `test_get_market_index_with_retry()`는 Rate Limit 발생 가능
- 캐싱 덕분에 2회차부터는 빠르게 동작
- Rate Limit 발생 시 자동으로 `pytest.skip()` 처리

### LLM Credit 관련
- Strategy Agent 테스트 시 LLM credit 소모
- Credit 부족 시 Fallback 로직 자동 적용

## ✨ 테스트 작성 가이드

### 1. Service 테스트
```python
import pytest
from src.services import your_service

class TestYourService:
    @pytest.mark.asyncio
    async def test_your_method(self):
        result = await your_service.your_method()
        assert result is not None
```

### 2. Agent 테스트
```python
import pytest
from src.agents.your_agent import your_agent_function

class TestYourAgent:
    @pytest.mark.asyncio
    async def test_agent_execution(self):
        state = {"input": "test"}
        result = await your_agent_function(state)
        assert result["output"] is not None
```

### 3. 통합 테스트
```python
import pytest
from src.api.routes.chat import chat_endpoint

class TestIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_flow(self):
        request = {"message": "test"}
        response = await chat_endpoint(request)
        assert response["status"] == "success"
```

## 📈 테스트 실행 결과 (2025-10-09)

### 전체 통과율
- ✅ Services: 12/12 (100%)
- ✅ Agents: 5/5 (100%)
- ✅ Integration: 6/6 (100%)

**Total: 23/23 테스트 통과 (100%)**

### 개선 사항 (v2.0)
1. ✅ 임시 테스트 파일 제거 (`test_dart_mapping.py`, `test_strategy_improvements.py`)
2. ✅ Service 테스트 체계화 (`test_services/` 디렉토리)
3. ✅ Agent 테스트 추가 (`test_strategy_agent.py`)
4. ✅ Mock 데이터 완전 제거 검증
5. ✅ Rate Limit 개선 검증

## 🔗 관련 문서
- [프로젝트 README](../README.md)
- [개발 가이드](../CLAUDE.md)
- [Agent 아키텍처](../AGENTS.md)

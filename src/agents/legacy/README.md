# Legacy Agents

이 디렉토리는 LangGraph 서브그래프로 전환되지 않은 Legacy 에이전트들을 포함합니다.

## 📊 현재 상태 (2025-10-28)

### ✅ 마이그레이션 완료 (LangGraph 서브그래프)
- **ResearchAgent** - ~~삭제됨~~ (2025-10-28)
  - `src/agents/research/graph.py` - LangGraph 서브그래프로 전환
  - 노드: collect_data → [bull_analysis, bear_analysis] → consensus

- **StrategyAgent** - ~~삭제됨~~ (2025-10-28)
  - `src/agents/strategy/graph.py` - LangGraph 서브그래프로 전환
  - 노드: market_analysis → sector_rotation → asset_allocation → blueprint

- **RiskAgent** - `src/agents/risk/graph.py` ✅
- **TradingAgent** - `src/agents/trading/graph.py` ✅
- **PortfolioAgent** - `src/agents/portfolio/graph.py` ✅
- **GeneralAgent** - `src/agents/general/graph.py` ✅

- **DataCollectionAgent** - ~~삭제됨~~ (2025-10-06)
  - Research Agent의 `collect_data_node`로 통합
  - 서비스 직접 호출 (`stock_data_service`, `dart_service`)

### ⚠️ Mock 구현 (사용 안 됨)
- **MonitoringAgent** (`monitoring.py`)
  - Mock 구현만 있음
  - Supervisor에 등록되지 않음
  - Phase 2에서 서브그래프로 전환 예정

- **PersonalizationAgent** (`personalization.py`)
  - Mock 구현만 있음
  - Supervisor에 등록되지 않음
  - 요구사항 재정의 필요

### 🗂️ Base Classes
- `base.py` - Legacy 모듈 공통 사용
- `base_agent.py` - LegacyAgent 추상 클래스

## 🔄 마이그레이션 히스토리

### 2025-10-28: ResearchAgent & StrategyAgent 중복 제거
- `research_agent.py` (201줄) 삭제 - LangGraph 서브그래프만 사용
- `strategy_agent.py` (174줄) 삭제 - LangGraph 서브그래프만 사용
- **효과**: 375줄 중복 코드 제거, 아키텍처 단순화
- **영향**: 없음 (모든 외부 코드가 이미 서브그래프 사용 중)

### 2025-10-06: DataCollectionAgent 제거
- Research Agent에서 `data_collection_agent` 의존성 제거
- `collect_data_node`에서 서비스 직접 호출로 변경
  ```python
  # Before
  await data_collection_agent.process(input_data)

  # After
  await stock_data_service.get_stock_price(stock_code)
  await dart_service.get_financial_statement(corp_code)
  ```
- **결과**: 실제 데이터 연동 성공 (FinanceDataReader + DART API)

## 📋 다음 작업 (Phase 2)

### MonitoringAgent 서브그래프화
**우선순위**: 낮음 (실시간 모니터링은 Phase 3)

**계획**:
1. State 정의: `MonitoringState`
2. 노드 분해:
   - `detect_price_events` - 가격 변동 감지
   - `monitor_news` - 뉴스 모니터링
   - `generate_alerts` - 알림 생성
3. Supervisor 등록

### PersonalizationAgent 재정의
**우선순위**: 중간

**검토 사항**:
- 사용자 프로필 관리가 별도 에이전트로 필요한가?
- Portfolio Agent나 Strategy Agent에 통합 가능한가?
- 데이터베이스 직접 접근으로 충분한가?

**옵션**:
1. 서브그래프로 전환
2. 다른 Agent에 통합
3. 완전 제거 (DB 직접 접근)

## 🚫 삭제 금지 사항

- `base.py`, `base_agent.py`는 다른 모듈에서 참조할 수 있으므로 유지
- Monitoring, Personalization은 Mock이지만 향후 전환을 위해 유지

## 📝 참고 문서

- `docs/plan/legacy-agent-migration.md` - 마이그레이션 계획
- `docs/langgraph-supervisor-architecture.md` - 아키텍처 문서
- `tests/test_research_data_collection.py` - 마이그레이션 검증 테스트

---

**최종 업데이트**: 2025-10-28
**브랜치**: `feat/frontend-integration-phase2-p2`

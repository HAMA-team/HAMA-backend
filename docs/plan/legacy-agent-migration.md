# Legacy Agent Migration Plan

이 문서는 `LegacyAgent` 기반 모듈을 LangGraph 서브그래프로 전환하기 위한
단계별 계획을 정리합니다. 기준 문서는 `docs/langgraph-supervisor-architecture.md`
이며, 아래 항목들은 해당 문서의 TODO 목록을 세분화한 것입니다.

## 1. 공통 준비
- [x] 각 에이전트별 `State` TypedDict 정의 (`PortfolioState`, `MonitoringState`, `GeneralState`)
- [x] 기존 `LegacyAgent` 사용 모듈에서 입출력 스키마(`AgentInput/AgentOutput`) 의존 제거
- [x] 서비스 계층 호출부 정리 (예: 데이터 수집 서비스, 사용자 프로필 서비스)

## 2. Portfolio Agent 전환
- [x] 상태 정의: 현재 포트폴리오, 제약조건, 사용자 목표
- [x] 노드 분해: `collect_portfolio`, `optimize_allocation`, `rebalance_plan`, `summary`
- [x] 그래프 빌드: `StateGraph(PortfolioState)` → `portfolio_agent` 재컴파일
- [x] Supervisor 등록 복귀 (`graph_master.py`의 주석된 항목 활성화)

## 3. Monitoring Agent 전환
- [ ] 상태 정의: 모니터링 대상 종목, 이벤트 규칙, 결과 캐시
- [ ] 노드 분해: `detect_price_events`, `monitor_news`, `generate_alerts`
- [ ] 외부 데이터 파이프 정리 (서비스 계층 의존성 문서화)
- [ ] 완성 후 Supervisor 등록 및 스케줄링 정책 검토
- **상태**: Phase 2로 연기 (실시간 모니터링은 Phase 3 기능)

## 4. General Agent (Education) 신설
- [x] 상태 정의: 질문 텍스트, 검색 결과, 응답 메타데이터
- [x] 노드 구성: `answer_question`
- [x] LLM 프롬프트 설계 및 소스 반환 구조 확정
- [x] Supervisor 등록

## 5. Personalization & Risk Legacy Wrapper 정리
- [ ] Personalization: 기능 요구사항 재정의 → 서브그래프 필요 여부 결정
- [x] Risk(Legacy) 모듈: 신규 서브그래프로 완전 대체 완료

## 6. 데이터 수집 레거시 제거 ✅
- [x] `data_collection_agent` 호출부를 서비스 레이어 직접 호출로 대체 (`research` 서브그래프 노드)
- [x] Research Agent에서 `stock_data_service`, `dart_service` 직접 호출
- [x] 마이그레이션 완료 후 `data_collection_agent` 삭제
- **완료일**: 2025-10-06
- **검증**: `tests/test_research_data_collection.py` 통과

### 6.1 마이그레이션 상세

**Before (Legacy):**
```python
from src.agents.legacy.data_collection import data_collection_agent

price_result = await data_collection_agent.process(input_data)
financial_result = await data_collection_agent.process(input_data)
```

**After (Direct Service Call):**
```python
from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service

price_df = await stock_data_service.get_stock_price(stock_code, days=30)
financial_statements = await dart_service.get_financial_statement(corp_code, "2023")
```

**결과**:
- ✅ 실제 데이터 연동 성공 (FinanceDataReader + DART API)
- ✅ Redis 캐싱 정상 작동
- ✅ 삼성전자 (005930) 주가: 89,000원 조회 성공
- ✅ DART 고유번호 (00126380) 변환 성공
- ✅ 재무제표 176개 항목 조회 성공

## 7. 종료 조건
- [x] `data_collection_agent` 제거 (1/3 완료)
- [ ] `monitoring_agent` 처리 (Phase 2)
- [ ] `personalization_agent` 처리 (요구사항 재정의 후)
- [ ] Supervisor 등록 에이전트 전부 LangGraph 서브그래프 기반
- [ ] 문서 TODO 체크 (Phase 1: 서브그래프 전환) 전부 완료

## 📊 진행 상황

| 에이전트 | 상태 | 완료일 |
|---------|------|--------|
| DataCollection | ✅ 제거 완료 | 2025-10-06 |
| Monitoring | ⏸️ Phase 2 연기 | - |
| Personalization | 🔍 검토 중 | - |

---

**작성일**: 2025-10-05
**최종 업데이트**: 2025-10-06
**브랜치**: `feat/legacy-migration`

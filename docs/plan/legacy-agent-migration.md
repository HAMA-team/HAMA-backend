# Legacy Agent Migration Plan

이 문서는 `LegacyAgent` 기반 모듈을 LangGraph 서브그래프로 전환하기 위한
단계별 계획을 정리합니다. 기준 문서는 `docs/langgraph-supervisor-architecture.md`
이며, 아래 항목들은 해당 문서의 TODO 목록을 세분화한 것입니다.

## 1. 공통 준비
- [ ] 각 에이전트별 `State` TypedDict 정의 (`PortfolioState`, `MonitoringState`, `GeneralState`)
- [ ] 기존 `LegacyAgent` 사용 모듈에서 입출력 스키마(`AgentInput/AgentOutput`) 의존 제거
- [ ] 서비스 계층 호출부 정리 (예: 데이터 수집 서비스, 사용자 프로필 서비스)

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

## 4. General Agent (Education) 신설
- [ ] 상태 정의: 질문 텍스트, 검색 결과, 응답 메타데이터
- [ ] 노드 구성: `retrieve_context`(선택), `answer_question`, `format_response`
- [ ] LLM 프롬프트 설계 및 소스 반환 구조 확정
- [ ] Supervisor 등록, 기존 `education_agent` 완전 제거

## 5. Personalization & Risk Legacy Wrapper 정리
- [ ] Personalization: 기능 요구사항 재정의 → 서브그래프 필요 여부 결정
- [ ] Risk(Legacy) 모듈: 신규 서브그래프와 중복되는 기능 정리 후 제거 일정 수립

## 6. 데이터 수집 레거시 제거
- [ ] `data_collection_agent` 호출부를 서비스 레이어 직접 호출로 대체 (`research` 서브그래프 노드)
- [ ] 필요 시 async 서비스 팩토리 도입하여 중복 로직 제거
- [ ] 마이그레이션 완료 후 `data_collection_agent` 삭제

## 7. 종료 조건
- [ ] `src/agents/legacy` 내 `LegacyAgent` 기반 모듈 0개화
- [ ] Supervisor 등록 에이전트 전부 LangGraph 서브그래프 기반
- [ ] 문서 TODO 체크 (Phase 1: 서브그래프 전환) 전부 완료

작성일: 2025-10-05

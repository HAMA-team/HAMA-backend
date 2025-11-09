# Phase 2 후속 구현 체크리스트

Phase 2 통합 사항을 검토한 결과, 현재 코드베이스는 KIS 주문 실행과 BOK 거시 지표 수집이 기본적으로 연결되어 있습니다. 다만 실거래 안정성, 거시 데이터 활용도, 관측성 측면에서 보완이 필요한 항목이 남아 있어 아래와 같이 정리합니다.

## 1. KIS API 연동 보완
- [ ] `src/services/kis_service.py`의 `place_order` 이후 체결 확인(`/uapi/domestic-stock/v1/trading/inquire-ccnl`) 및 취소/정정 API를 추가해 최종 체결 상태를 기록
- [ ] 모의/실전 환경 전환 시 필요한 계좌 유형, 종목코드 포맷 검증 로직을 `KISService` 초기화 단계에 명시
- [ ] 주문 실패 시 현재는 DB 시뮬레이션으로 강제 체결 처리되므로(`trading_service.execute_order`) KIS 실패 분기에서 재시도 또는 `order_status=rejected` 처리가 되도록 분리
- [ ] 웹소켓 기반 실시간 호가/체결 채널(풍선 알림)을 추가하여 Celery 캐시(`realtime_cache_service`)와 통합
- [ ] 테스트: `tests/test_services/test_kis_service.py`(현재 미구현)을 생성하고 아래 시나리오를 커버
  - [ ] 토큰 발급 API(`/oauth2/tokenP`) 성공/실패 분기
  - [ ] 잔고 조회(`/uapi/domestic-stock/v1/trading/inquire-balance`) 응답 파싱
  - [ ] 주문 실행(`/uapi/domestic-stock/v1/trading/order-cash`) 정상/에러 응답 및 Rate Limit 대응

## 2. 매매 파이프라인 & HITL 강화
- [ ] `trading_service.execute_order`가 체결가를 직접 받아야 하므로 실행 전 `stock_data_service` 또는 KIS 시세 API에서 최신 호가를 조회하도록 자동화
- [ ] 부분 체결, 다중 체결 대응을 위해 `Order.filled_quantity` 갱신 로직을 반복 호출 구조로 개선하고 거래 로그(`Transaction`)에 체결 단위를 남김
- [ ] 승인(Interrupt) 후 장 마감/가격 급변 등 리스크 경고를 추가하기 위해, 승인 시점과 실행 시점 사이에 리밸런싱 검증 노드를 삽입
- [ ] Celery 비동기 태스크 도입을 검토해 주문 실행과 포트폴리오 재계산을 분리하고 Latency를 감시

## 3. BOK API 및 거시 지표 활용
- [ ] `src/services/bok_service.py`가 하드코딩한 API 키를 `settings.BOK_API_KEY`로 대체하고 `.env` 로딩 경고 추가
- [ ] BOK 응답 포맷을 표준화(`pydantic` 모델)하여 LangGraph 노드 사이에서 일관된 데이터 구조로 사용
- [ ] 거시 지표 스냅샷을 DB/캐시에 주기적으로 적재하여 Agent 호출 시 API 부하를 줄이고 히스토리를 생성
- [ ] 기준금리/환율 등 지표를 시각화하여 `docs/cache/` 또는 대시보드 API에서 재사용할 수 있도록 유틸 생성
- [ ] 테스트: BOK API가 없는 환경을 고려해 `tests/test_services/test_bok_service.py`에 VCR 또는 로컬 샘플 응답 검증 추가

## 4. 관측성 · 문서화
- [ ] 주문 흐름(생성 → 승인 → 실행)을 추적할 수 있도록 구조화된 로그 및 메트릭(예: Prometheus 라벨) 추가
- [ ] FastAPI 라우터(`src/api/routes/portfolio.py`)에서 KIS 싱크 실패 시 사용자 메시지를 표준화하고, 프런트 알림 규격을 문서화
- [ ] `docs/architecture/overall-architecture.md` 갱신분과 연동해 데이터 소스/흐름 다이어그램을 최신 상태로 유지
- [ ] Phase 2 배포 준비 시 요구되는 비밀 키 목록과 권한(모의투자/실전)을 `docs/deployment/` 쪽 체크리스트로 연결

위 리스트는 우선순위 순으로 정렬되어 있습니다. 각 항목은 구현 후 `docs/plan/completed/` 아래에 완료 리포트를 이동시키는 흐름을 유지해주세요.

---

## 참고 자료 (KIS Open Trading API)
- 공식 깃허브: https://github.com/koreainvestment/open-trading-api  
  - 인증: `/oauth2/tokenP` (POST, appkey/appsecret)  
  - 계좌 잔고: `/uapi/domestic-stock/v1/trading/inquire-balance` (`tr_id` 예: `VTTC8434R`)  
  - 주문: `/uapi/domestic-stock/v1/trading/order-cash` (`VTTC0012U`, `VTTC0011U` 등)  
  - 웹소켓: `/oauth2/Approval` → 실시간 시세/체결 스트림  
- API 제한: 초당 1회, 분당 20회 기본. RateLimiter(`src/services/kis_service.py:50`)와 일치하도록 문서 확인 필요.

# 실시간 주가 데이터 캐싱 시스템

## 개요

코스피/코스닥 전체 종목(약 2,500개)의 실시간 주가를 **프로세스 단위 인메모리 캐시**에 저장하여 API 요청을 최소화하고 응답 지연을 줄입니다. 장중에는 Celery 워커가 60초마다 캐시를 갱신하고, 에이전트는 항상 캐시를 먼저 조회한 뒤 데이터가 없을 때만 KIS API를 호출합니다.

### 핵심 기능

- **전체 종목 캐싱**: 코스피/코스닥 종목 리스트를 가져와 일괄 업데이트
- **주기적 갱신**: Celery Beat → Worker가 60초마다 자동 실행
- **장중 시간 관리**: 평일 09:00~15:30에만 수집 루프 동작
- **Fallback 전략**: 캐시 미스 시 즉시 KIS API 호출 후 캐시에 저장

## 아키텍처

```
┌─────────────────────────────────────┐
│ Celery Beat (Scheduler)            │
│ - 60초마다 update_task 트리거       │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ Celery Worker                       │
│ - 장중 시간 체크                     │
│ - 종목 리스트 조회                   │
│ - 배치 처리 (Rate Limit 관리)       │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ KIS API                             │
│ - 실시간 주가 조회                   │
│ - Rate Limit: 초당 1회              │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ In-Memory Cache                     │
│ - realtime:price:{code}             │
│ - TTL: 120초                        │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ Agents / API                        │
│ - 캐시 우선 조회                    │
│ - 미스 시 API Fallback              │
└─────────────────────────────────────┘
```

## 구현 파일

### 서비스 계층
- `src/services/realtime_cache_service.py`
  - `get_all_stock_codes()`: 코스피·코스닥 종목 리스트 수집
  - `cache_stock_price()`: 단일 종목 캐싱
  - `cache_stock_batch()`: 배치 캐싱 (Rate Limit 준수)
  - `get_cached_price()`: 캐시 조회
  - `is_market_open()`: 장중 여부 판별
- `src/services/stock_data_service.py`
  - `get_realtime_price()`: 캐시 우선 조회 + Fallback

### 워커 계층
- `src/workers/celery_app.py`: Celery 설정 및 Beat 스케줄 정의
- `src/workers/tasks.py`: 주기/수동 태스크
  - `update_realtime_market_data()`: 60초마다 전체 갱신
  - `update_stock_batch()`: 지정 종목 배치 갱신
  - `cache_single_stock()`: 단일 종목 수동 갱신

## Celery 구성

| 항목 | 값 | 비고 |
| --- | --- | --- |
| Broker | `memory://` | 기본값 (환경 변수로 오버라이드 가능) |
| Result Backend | `cache+memory://` | 개발/테스트 용도 |
| Beat 스케줄 | 60초 | 장중 여부에 따라 자동 스킵 |
| Worker Prefetch | 1 | Rate Limit 보호 |

필요 시 `.env`에서 `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`를 다른 브로커로 변경할 수 있습니다.

## 캐시 키 & 데이터 포맷

| 키 | 설명 | TTL |
| --- | --- | --- |
| `realtime:stock_list:{market}` | 종목 코드 리스트 (`ALL`, `KOSPI`, `KOSDAQ`) | 3600초 |
| `realtime:price:{stock_code}` | 실시간 주가 스냅샷 | 120초 |

```json
{
  "stock_code": "005930",
  "stock_name": "삼성전자",
  "price": 71100,
  "change": 1000,
  "change_rate": 1.41,
  "volume": 15234567,
  "timestamp": "2025-10-27T14:30:00"
}
```

## 사용 예시

```python
from src.services.stock_data_service import stock_data_service

price = await stock_data_service.get_realtime_price("005930")

if price:
    print(f"{price['stock_name']}: {price['price']:,}원 ({price['change_rate']}%)")
else:
    print("주가 데이터가 없습니다.")
```

## 모니터링

- Celery 로그: `tail -f logs/celery_worker.log`
- Beat 로그: `tail -f logs/celery_beat.log`
- Flower (선택): `celery -A src.workers.celery_app flower`
- 캐시 통계: `src/services/cache_manager.py` 의 `get_stats()` 활용

## 트러블슈팅

| 증상 | 점검 항목 |
| --- | --- |
| Worker 미실행 | 장중 여부(`is_market_open`), Celery 로그 |
| 데이터 미갱신 | `CELERY_BATCH_SIZE`, Rate Limit 초과 여부 |
| 캐시 미스 잦음 | TTL 조정, 워커 주기 확인 |
| API 호출 실패 | KIS 토큰 만료 여부, 네트워크 상태 |

## 향후 개선

1. **지수 캐싱**: KOSPI/KOSDAQ/KOSPI200 데이터 추가
2. **관심 종목 우선순위**: 사용자 지정 리스트 선처리
3. **WebSocket 알림**: 캐시 갱신 결과 푸시
4. **외부 캐시 옵션**: 필요 시 관리형 캐시(예: Elasticache) 연결
5. **모니터링 강화**: Prometheus + Grafana 통합

## 참고 자료

- [Celery 공식 문서](https://docs.celeryproject.org/)
- [한국투자증권 API 포털](https://apiportal.koreainvestment.com/)

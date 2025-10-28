# 실시간 주가 데이터 Redis 캐싱 시스템

## 개요

코스피/코스닥 전체 종목(약 2,500개)의 실시간 주가를 Redis에 캐싱하여 빠른 응답 속도를 제공하는 시스템입니다.

### 핵심 기능

- **전체 종목 캐싱**: 코스피/코스닥 약 2,500개 종목 자동 수집
- **주기적 업데이트**: Celery Beat를 통해 60초마다 자동 갱신
- **장중 시간 관리**: 평일 09:00-15:30만 동작
- **Fallback 전략**: Redis 캐시 미스 시 KIS API 즉시 호출

## 아키텍처

```
┌─────────────────────────────────────┐
│   Celery Beat (Scheduler)          │
│   - 60초마다 update_task 트리거     │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Celery Worker                     │
│   - 장중 시간 체크                   │
│   - 종목 리스트 조회                 │
│   - 배치 처리 (Rate Limit 관리)     │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   KIS API                           │
│   - 실시간 주가 조회                 │
│   - Rate Limit: 초당 1회            │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Redis Cache                       │
│   - realtime:price:{code}           │
│   - TTL: 120초                      │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Agent (Research/Strategy)         │
│   - Redis 우선 조회                 │
│   - 캐시 미스 시 API Fallback       │
└─────────────────────────────────────┘
```

## 구현 파일

### 1. 서비스 계층
- **src/services/realtime_cache_service.py**
  - `get_all_stock_codes()`: 코스피/코스닥 종목 리스트 조회
  - `cache_stock_price()`: 개별 종목 캐싱
  - `cache_stock_batch()`: 배치 캐싱 (Rate Limit 관리)
  - `get_cached_price()`: 캐시된 데이터 조회
  - `is_market_open()`: 장중 시간 체크

- **src/services/stock_data_service.py**
  - `get_realtime_price()`: Redis 우선 조회 + KIS API Fallback

### 2. Worker 계층
- **src/workers/celery_app.py**: Celery 앱 설정 및 Beat 스케줄
- **src/workers/tasks.py**: 주기적 태스크 구현
  - `update_realtime_market_data()`: 60초마다 전체 시장 데이터 업데이트
  - `update_stock_batch()`: 배치 업데이트 (수동 호출용)
  - `cache_single_stock()`: 단일 종목 캐싱 (수동 호출용)

### 3. 설정
- **src/config/settings.py**
  - `CELERY_BROKER_URL`: Redis DB 1
  - `CELERY_RESULT_BACKEND`: Redis DB 2
  - `CELERY_REALTIME_UPDATE_INTERVAL`: 60초
  - `CELERY_BATCH_SIZE`: 50개
  - `CACHE_TTL_REALTIME_PRICE`: 120초

### 4. 실행 스크립트
- **scripts/start_celery_worker.sh**: Worker 실행
- **scripts/start_celery_beat.sh**: Beat 스케줄러 실행

## 실행 방법

### 1. 의존성 설치

```bash
pip install celery==5.3.4
```

### 2. Redis 실행

```bash
redis-server
```

### 3. Celery Worker 실행 (터미널 1)

```bash
./scripts/start_celery_worker.sh

# 또는 직접 실행
celery -A src.workers.celery_app worker --loglevel=info
```

### 4. Celery Beat 실행 (터미널 2)

```bash
./scripts/start_celery_beat.sh

# 또는 직접 실행
celery -A src.workers.celery_app beat --loglevel=info
```

### 5. FastAPI 서버 실행 (터미널 3)

```bash
uvicorn src.main:app --reload
```

## 데이터 구조

### Redis 키 구조

```
realtime:price:{stock_code}
```

### 데이터 포맷

```json
{
  "stock_code": "005930",
  "stock_name": "삼성전자",
  "price": 72000,
  "change": 1000,
  "change_rate": 1.41,
  "volume": 15234567,
  "timestamp": "2025-10-27T14:30:00"
}
```

## 성능 특성

### 업데이트 주기
- **60초마다** Celery Beat가 트리거
- **장중만** 동작 (평일 09:00-15:30)
- **장외/주말**: 자동 스킵

### Rate Limit 관리
- KIS API: **초당 1회** 제한
- 배치 크기: **50개**
- 배치 간 대기: **2초**
- **전체 종목 갱신 시간**: 약 **42분** (2,500개 ÷ 60개/분)

### TTL 설정
- **120초**: 워커 실패 시 2회 주기까지 대기 가능
- 다음 워커 실행 전(60초) 자동 갱신

## 사용 예시

### Agent에서 실시간 주가 조회

```python
from src.services.stock_data_service import stock_data_service

# 실시간 주가 조회 (Redis 우선)
price_data = await stock_data_service.get_realtime_price("005930")

if price_data:
    print(f"{price_data['stock_name']}: {price_data['price']:,}원")
    print(f"등락률: {price_data['change_rate']}%")
else:
    print("주가 데이터 없음 (캐시 미스 + API 실패)")
```

### 수동 배치 업데이트

```python
from src.workers.tasks import update_stock_batch

# 특정 종목만 업데이트
stock_codes = ["005930", "000660", "035420"]
result = update_stock_batch.delay(stock_codes)

print(result.get())  # 결과 대기
```

## 모니터링

### Celery Flower (선택)

```bash
pip install flower
celery -A src.workers.celery_app flower
```

브라우저: http://localhost:5555

### 로그 확인

```bash
tail -f logs/celery_worker.log
tail -f logs/celery_beat.log
```

### Redis 키 확인

```bash
redis-cli

# 캐시된 종목 수 확인
> KEYS realtime:price:*
> GET realtime:price:005930
```

## 트러블슈팅

### 1. Worker가 실행되지 않음

```bash
# Redis 연결 확인
redis-cli ping

# 환경 변수 확인
echo $CELERY_BROKER_URL
```

### 2. Task가 실행되지 않음

```bash
# Beat 스케줄 확인
celery -A src.workers.celery_app inspect scheduled

# Worker 상태 확인
celery -A src.workers.celery_app inspect active
```

### 3. Rate Limit 에러

- KIS API 초당 1회 제한 초과
- → 배치 크기 줄이기 (`CELERY_BATCH_SIZE` 감소)
- → 배치 간 대기 시간 증가

### 4. 종목 리스트 조회 실패

- FinanceDataReader API 일시적 장애
- → 캐시된 리스트 사용
- → 재시도 로직 추가 (Phase 2)

## 향후 개선 사항 (Phase 2)

1. **지수 캐싱**: KOSPI, KOSDAQ, KOSPI200 지수 추가
2. **동적 종목 리스트**: 사용자 관심 종목만 우선 캐싱
3. **WebSocket**: 실시간 Push 알림
4. **Fallback 개선**: FinanceDataReader → KIS API 자동 전환
5. **모니터링**: Prometheus + Grafana 대시보드

## 참고 자료

- [Celery 공식 문서](https://docs.celeryproject.org/)
- [한국투자증권 API 문서](https://apiportal.koreainvestment.com/)
- [Redis 공식 문서](https://redis.io/docs/)

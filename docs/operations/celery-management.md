# Celery 운영 가이드

## 구성 요소
- **Worker**: 태스크 실행 (`celery -A src.workers.celery_app worker`)
- **Beat**: 주기 스케줄러 (`celery -A src.workers.celery_app beat`)
- **Broker/Backend**: `.env`에서 `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`로 설정 (기본 Redis)

## 실행 명령
```bash
# 가상환경 활성화 후
celery -A src.workers.celery_app worker --loglevel=info
celery -A src.workers.celery_app beat --loglevel=info
```

실시간/정기 업데이트를 모두 사용하려면 **worker**와 **beat**를 각각 별도 프로세스로 운영합니다.

## 주기 태스크(Beat 스케줄)
| 태스크 | 주기 | 설명 |
|--------|------|------|
| `update_realtime_market_data` | 60초 | Redis 실시간 캐시 갱신 |
| `refresh_price_history_daily` | 평일 16:20 | Close 후 과거 가격/기술지표 DB 갱신 |
| `refresh_macro_indicators` | 매일 06:30 | BOK 거시지표 적재 |

시간대는 `Asia/Seoul` 기준이며 필요에 따라 `src/workers/celery_app.py`에서 수정할 수 있습니다.

## 배포 권장 사항
- **프로세스 관리자**: systemd, Supervisor, pm2 등으로 worker/beat를 관리하고 장애시 자동 재시작
- **로그 수집**: `--logfile` 옵션 또는 중앙 로깅 시스템으로 수집
- **고가용성**: Worker를 여러 대 띄워 병렬 실행 가능 (단, pykrx 호출 시 Rate Limit 고려)
- **브로커/백엔드**: 운영 환경에서는 Redis 클러스터 또는 AWS Elasticache 등 관리형 서비스 추천

## 운영 팁
- **Graceful Shutdown**: `celery control shutdown` 또는 `SIGTERM`으로 종료하여 현재 작업을 마무리하도록 함
- **모니터링**: `flower` (`celery -A src.workers.celery_app flower`)로 태스크 현황 모니터링 가능
- **스케줄 변경**: Beat 스케줄은 코드 수정 후 재배포, 혹은 `celery beat` 재시작 필요

## 초기 적재 시 참고
- 종목/시세: `python scripts/seed_market_data.py --market ALL --days 90`
- 거시 지표: `python scripts/seed_macro_data.py`

적재 후 Worker/Beat를 실행하면 정기 증분 업데이트가 자동으로 진행됩니다.

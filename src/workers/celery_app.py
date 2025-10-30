"""
Celery App 설정

실시간 주가 데이터 수집을 위한 Celery 워커 설정
"""

from celery import Celery
from celery.schedules import crontab
from src.config.settings import settings

# Celery 앱 초기화
app = Celery(
    "hama_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.workers.tasks"],  # Tasks 모듈
)

# Celery 설정
app.conf.update(
    # Timezone 설정 (한국 시간)
    timezone="Asia/Seoul",
    enable_utc=False,
    # Task 결과 만료 시간 (1시간)
    result_expires=3600,
    # Task 직렬화 (JSON)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Worker 설정
    worker_prefetch_multiplier=1,  # 한 번에 하나씩 처리
    worker_max_tasks_per_child=1000,  # 메모리 누수 방지
    # Broker 설정
    broker_connection_retry_on_startup=True,
    # Task 재시도 설정
    task_acks_late=True,  # Task 완료 후 ACK
    task_reject_on_worker_lost=True,
)

# Celery Beat 스케줄 설정
app.conf.beat_schedule = {
    # 실시간 데이터 업데이트 (60초마다)
    "update-realtime-market-data": {
        "task": "src.workers.tasks.update_realtime_market_data",
        "schedule": 60.0,  # 60초
        "options": {
            "expires": 55,  # 55초 후 만료 (다음 실행 전)
        },
    },
    # 장 마감 후 주가 히스토리 갱신 (평일 16:20)
    "refresh-price-history-daily": {
        "task": "src.workers.tasks.refresh_price_history_daily",
        "schedule": crontab(hour=16, minute=20, day_of_week="mon-fri"),
        "args": ("ALL", 5, None),
    },
    # 매일 아침 거시 지표 갱신 (06:30)
    "refresh-macro-indicators": {
        "task": "src.workers.tasks.refresh_macro_indicators",
        "schedule": crontab(hour=6, minute=30),
    },
}


if __name__ == "__main__":
    # Celery Worker 실행 (디버깅용)
    # 실제로는 터미널에서 celery 명령어로 실행
    app.start()

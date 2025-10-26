#!/bin/bash

# Celery Beat 스케줄러 실행 스크립트

echo "⏰ Starting Celery Beat Scheduler for HAMA Real-time Data..."

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.." || exit

# 환경 변수 로드
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Celery Beat 실행
celery -A src.workers.celery_app beat \
    --loglevel=info \
    --logfile=logs/celery_beat.log

echo "✅ Celery Beat stopped"

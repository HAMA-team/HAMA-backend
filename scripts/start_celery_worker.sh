#!/bin/bash

# Celery Worker 실행 스크립트

echo "🚀 Starting Celery Worker for HAMA Real-time Data Collection..."

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.." || exit

# 환경 변수 로드
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Celery Worker 실행
celery -A src.workers.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=1000 \
    --logfile=logs/celery_worker.log

echo "✅ Celery Worker stopped"

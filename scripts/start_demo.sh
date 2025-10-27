#!/bin/bash

# HAMA 캡스톤 시연용 실행 스크립트
# Docker Compose + ngrok으로 외부 접속 가능한 환경 구성

set -e  # 에러 발생 시 중단

echo "======================================"
echo "🚀 HAMA 캡스톤 시연 환경 시작"
echo "======================================"
echo ""

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.." || exit

# 1. Docker Compose 서비스 시작
echo "📦 1/3: Docker Compose 서비스 시작 중..."
docker-compose up -d

echo ""
echo "⏳ 서비스 준비 중... (30초 대기)"
sleep 30

# 2. 서비스 상태 확인
echo ""
echo "🔍 2/3: 서비스 상태 확인..."
docker-compose ps

# 3. FastAPI 헬스 체크
echo ""
echo "💚 3/3: FastAPI 헬스 체크..."
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ FastAPI 서버 정상 동작 중!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "⏳ FastAPI 준비 중... ($RETRY_COUNT/$MAX_RETRIES)"
        sleep 3
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ FastAPI 서버 시작 실패. docker-compose logs fastapi 로 확인하세요."
    exit 1
fi

echo ""
echo "======================================"
echo "✅ 모든 서비스 시작 완료!"
echo "======================================"
echo ""
echo "📍 로컬 접속:"
echo "   - FastAPI: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - PostgreSQL: localhost:5432"
echo "   - Redis: localhost:6379"
echo ""
echo "======================================"
echo "🌐 ngrok으로 외부 접속 설정"
echo "======================================"
echo ""
echo "다른 터미널에서 다음 명령어를 실행하세요:"
echo ""
echo "  ./scripts/ngrok_tunnel.sh"
echo ""
echo "또는 직접 실행:"
echo ""
echo "  ngrok http 8000"
echo ""
echo "======================================"
echo "📝 서비스 중지 방법:"
echo "======================================"
echo ""
echo "  ./scripts/stop_demo.sh"
echo ""
echo "또는:"
echo ""
echo "  docker-compose down"
echo ""

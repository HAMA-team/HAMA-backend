#!/bin/bash

# HAMA 캡스톤 시연 환경 중지 스크립트

set -e

echo "======================================"
echo "🛑 HAMA 캡스톤 시연 환경 중지"
echo "======================================"
echo ""

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.." || exit

# Docker Compose 서비스 중지
echo "📦 Docker Compose 서비스 중지 중..."
docker-compose down

echo ""
echo "✅ 모든 서비스가 중지되었습니다."
echo ""
echo "데이터를 완전히 삭제하려면:"
echo "  docker-compose down -v"
echo ""

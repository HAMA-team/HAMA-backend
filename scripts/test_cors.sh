#!/bin/bash

# CORS 설정 테스트 스크립트
# Vercel 프리뷰 도메인에서의 OPTIONS 프리플라이트 요청 검증

set -e

echo "======================================"
echo "🔍 CORS 설정 테스트"
echo "======================================"
echo ""

# 테스트할 도메인
VERCEL_PREVIEW="https://hama-frontend-v2-git-develop-seongmin-hwangs-projects.vercel.app"
NGROK_URL="${1:-https://gifted-michiko-auric.ngrok-free.dev}"
API_ENDPOINT="$NGROK_URL/api/v1/chat/"

echo "📍 테스트 대상:"
echo "   - ngrok URL: $NGROK_URL"
echo "   - API 엔드포인트: $API_ENDPOINT"
echo "   - Origin: $VERCEL_PREVIEW"
echo ""

# OPTIONS 프리플라이트 요청 테스트
echo "======================================"
echo "1️⃣ OPTIONS 프리플라이트 요청 테스트"
echo "======================================"
echo ""

RESPONSE=$(curl -s -i -X OPTIONS "$API_ENDPOINT" \
  -H "Origin: $VERCEL_PREVIEW" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,accept,authorization")

echo "$RESPONSE"
echo ""

# 상태 코드 추출
STATUS_CODE=$(echo "$RESPONSE" | head -n 1 | awk '{print $2}')

echo "======================================"
echo "2️⃣ 결과 분석"
echo "======================================"
echo ""

if [ "$STATUS_CODE" == "200" ] || [ "$STATUS_CODE" == "204" ]; then
    echo "✅ Status Code: $STATUS_CODE (정상)"

    # CORS 헤더 확인
    if echo "$RESPONSE" | grep -i "access-control-allow-origin" > /dev/null; then
        echo "✅ access-control-allow-origin 헤더 존재"
        ALLOW_ORIGIN=$(echo "$RESPONSE" | grep -i "access-control-allow-origin" | cut -d: -f2-)
        echo "   값:$ALLOW_ORIGIN"
    else
        echo "❌ access-control-allow-origin 헤더 없음"
    fi

    if echo "$RESPONSE" | grep -i "access-control-allow-methods" > /dev/null; then
        echo "✅ access-control-allow-methods 헤더 존재"
        ALLOW_METHODS=$(echo "$RESPONSE" | grep -i "access-control-allow-methods" | cut -d: -f2-)
        echo "   값:$ALLOW_METHODS"
    else
        echo "❌ access-control-allow-methods 헤더 없음"
    fi

    if echo "$RESPONSE" | grep -i "access-control-allow-headers" > /dev/null; then
        echo "✅ access-control-allow-headers 헤더 존재"
        ALLOW_HEADERS=$(echo "$RESPONSE" | grep -i "access-control-allow-headers" | cut -d: -f2-)
        echo "   값:$ALLOW_HEADERS"
    else
        echo "❌ access-control-allow-headers 헤더 없음"
    fi

    echo ""
    echo "======================================"
    echo "✅ CORS 설정 정상!"
    echo "======================================"
    echo ""
    echo "Vercel 프리뷰에서 API 요청이 가능합니다."

else
    echo "❌ Status Code: $STATUS_CODE (실패)"
    echo ""
    echo "======================================"
    echo "⚠️  CORS 설정 문제 발견"
    echo "======================================"
    echo ""
    echo "다음을 확인하세요:"
    echo "1. FastAPI 서버가 실행 중인지 확인"
    echo "2. .env 파일의 CORS_ORIGINS 설정 확인"
    echo "3. src/main.py의 CORS middleware 설정 확인"
    echo "4. 서버 재시작 필요"
    echo ""
    exit 1
fi

echo ""
echo "======================================"
echo "3️⃣ 추가 도메인 테스트"
echo "======================================"
echo ""

# 다른 Vercel 도메인 패턴 테스트
TEST_DOMAINS=(
    "https://hama-frontend-v2.vercel.app"
    "https://hama-frontend-v2-test.vercel.app"
)

for DOMAIN in "${TEST_DOMAINS[@]}"; do
    echo "테스트: $DOMAIN"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$API_ENDPOINT" \
        -H "Origin: $DOMAIN" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: content-type")

    if [ "$STATUS" == "200" ] || [ "$STATUS" == "204" ]; then
        echo "   ✅ Status: $STATUS (정상)"
    else
        echo "   ❌ Status: $STATUS (실패)"
    fi
done

echo ""
echo "======================================"
echo "✅ 테스트 완료!"
echo "======================================"
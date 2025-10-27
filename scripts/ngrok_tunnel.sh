#!/bin/bash

# ngrok 터널 실행 스크립트
# FastAPI 서버를 외부에 노출

set -e

echo "======================================"
echo "🌐 ngrok 터널 시작"
echo "======================================"
echo ""

# ngrok 설치 확인
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok이 설치되어 있지 않습니다."
    echo ""
    echo "설치 방법:"
    echo ""
    echo "macOS (Homebrew):"
    echo "  brew install ngrok/ngrok/ngrok"
    echo ""
    echo "Linux:"
    echo "  curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
    echo "  echo \"deb https://ngrok-agent.s3.amazonaws.com buster main\" | sudo tee /etc/apt/sources.list.d/ngrok.list"
    echo "  sudo apt update && sudo apt install ngrok"
    echo ""
    echo "또는 https://ngrok.com/download 에서 직접 다운로드"
    exit 1
fi

# FastAPI 서버 확인
echo "🔍 FastAPI 서버 확인 중..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ FastAPI 서버가 실행 중이 아닙니다."
    echo ""
    echo "먼저 다음 명령어로 서비스를 시작하세요:"
    echo "  ./scripts/start_demo.sh"
    exit 1
fi

echo "✅ FastAPI 서버 정상 동작 중"
echo ""

# ngrok authtoken 확인 (선택)
if [ ! -f ~/.ngrok2/ngrok.yml ]; then
    echo "⚠️  ngrok authtoken이 설정되지 않았습니다."
    echo ""
    echo "무료 계정 생성 및 authtoken 설정:"
    echo "  1. https://dashboard.ngrok.com/signup 에서 회원가입"
    echo "  2. https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 복사"
    echo "  3. 다음 명령어 실행:"
    echo "     ngrok authtoken YOUR_TOKEN_HERE"
    echo ""
    echo "authtoken 없이도 사용 가능하지만, 시간 제한이 있습니다."
    echo ""
    read -p "계속 진행하시겠습니까? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "======================================"
echo "🚀 ngrok 터널 실행 중..."
echo "======================================"
echo ""
echo "터미널 창을 닫지 마세요!"
echo "외부 URL은 아래에 표시됩니다."
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo ""
echo "--------------------------------------"

# ngrok 실행
ngrok http 8000

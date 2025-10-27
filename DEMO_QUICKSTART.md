# 🚀 HAMA 캡스톤 시연 빠른 시작

## 5분 안에 시작하기

### 1. 사전 준비 (한 번만)

```bash
# Docker 설치 확인
docker --version

# ngrok 설치
brew install ngrok/ngrok/ngrok  # macOS
# 또는 https://ngrok.com/download

# ngrok 계정 생성 (무료)
# https://dashboard.ngrok.com/signup
# authtoken 설정
ngrok authtoken YOUR_TOKEN_HERE
```

### 2. 시연 환경 실행

#### 터미널 1: 백엔드 서비스 시작

```bash
./scripts/start_demo.sh
```

**대기 시간:** 약 30-60초

**완료 메시지:**
```
✅ 모든 서비스 시작 완료!
📍 로컬 접속:
   - FastAPI: http://localhost:8000
   - API Docs: http://localhost:8000/docs
```

#### 터미널 2: 외부 접속 URL 생성

```bash
./scripts/ngrok_tunnel.sh
```

**결과:**
```
Forwarding   https://abc123.ngrok.io -> http://localhost:8000
```

**이 URL을 시연에 사용하세요!** 📱

---

## 시연 시나리오

### API 문서 시연

브라우저에서 열기:
```
https://abc123.ngrok.io/docs
```

### 실시간 주가 조회 시연

```bash
curl https://abc123.ngrok.io/api/v1/stocks/005930
```

### 채팅 기반 분석 시연

```bash
curl -X POST https://abc123.ngrok.io/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "message": "삼성전자 분석해줘"
  }'
```

---

## 시연 종료

```bash
# ngrok 중지: Ctrl+C (터미널 2)

# 백엔드 서비스 중지
./scripts/stop_demo.sh
```

---

## 문제 해결

### FastAPI가 시작되지 않음

```bash
# 로그 확인
docker-compose logs fastapi

# .env 파일 확인 (API 키)
cat .env
```

### ngrok이 연결되지 않음

```bash
# authtoken 재설정
ngrok authtoken YOUR_TOKEN_HERE

# 직접 실행
ngrok http 8000
```

---

## 추가 정보

상세 가이드: [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md)

---

**캡스톤 발표 화이팅! 🎓**

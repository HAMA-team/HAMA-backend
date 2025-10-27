# HAMA 캡스톤 시연 가이드

## 개요

Docker Compose + ngrok을 활용한 캡스톤 시연 환경 구성 가이드입니다.

### 시연 환경 구성

```
Docker Compose
├── PostgreSQL (DB)
├── Redis (캐싱 + Celery)
├── FastAPI (백엔드 API)
├── Celery Worker (실시간 데이터 수집)
└── Celery Beat (스케줄러)
          ↓
     [ngrok 터널]
          ↓
  외부 접속 가능한 HTTPS URL
```

---

## 사전 준비

### 1. Docker 설치

**macOS:**
```bash
brew install --cask docker
# Docker Desktop 실행
```

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. ngrok 설치

**macOS:**
```bash
brew install ngrok/ngrok/ngrok
```

**Linux:**
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

**직접 다운로드:**
- https://ngrok.com/download

### 3. ngrok 계정 생성 (선택, 권장)

1. https://dashboard.ngrok.com/signup 에서 회원가입
2. https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 복사
3. 터미널에서 설정:
   ```bash
   ngrok authtoken YOUR_TOKEN_HERE
   ```

**authtoken 장점:**
- 세션 시간 제한 없음
- 더 안정적인 터널
- 통계 확인 가능

---

## 시연 환경 실행

### 방법 1: 자동 스크립트 (권장 ⭐)

#### 1단계: 모든 서비스 시작

```bash
./scripts/start_demo.sh
```

**실행 내용:**
- Docker Compose 서비스 시작 (PostgreSQL, Redis, FastAPI, Celery)
- 서비스 헬스 체크
- 상태 확인

**예상 소요 시간:** 약 30-60초

#### 2단계: ngrok 터널 실행 (별도 터미널)

```bash
./scripts/ngrok_tunnel.sh
```

**결과:**
```
Session Status                online
Account                       your@email.com (Plan: Free)
Forwarding                    https://abc123.ngrok.io -> http://localhost:8000
```

**외부 접속 URL:** `https://abc123.ngrok.io`

---

### 방법 2: 수동 실행

#### 1단계: Docker Compose 실행

```bash
# 서비스 시작
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f fastapi
```

#### 2단계: ngrok 실행 (별도 터미널)

```bash
ngrok http 8000
```

---

## 시연 중 확인 사항

### 1. 로컬 접속 (개발자용)

```bash
# API 헬스 체크
curl http://localhost:8000/health

# API 문서
open http://localhost:8000/docs
```

### 2. 외부 접속 (시연용)

```bash
# ngrok URL 확인 (터미널에 표시됨)
https://abc123.ngrok.io

# API 문서 (외부)
https://abc123.ngrok.io/docs

# 헬스 체크 (외부)
curl https://abc123.ngrok.io/health
```

### 3. 서비스 상태 모니터링

```bash
# 전체 서비스 상태
docker-compose ps

# FastAPI 로그
docker-compose logs -f fastapi

# Celery Worker 로그
docker-compose logs -f celery-worker

# Celery Beat 로그
docker-compose logs -f celery-beat

# Redis 상태
docker-compose exec redis redis-cli ping

# PostgreSQL 상태
docker-compose exec postgres pg_isready
```

---

## 시연 시나리오

### 시나리오 1: 실시간 주가 조회

```bash
# 외부 URL을 통해 API 호출
curl https://abc123.ngrok.io/api/v1/stocks/005930

# 또는 브라우저에서
# https://abc123.ngrok.io/docs
# → /api/v1/stocks/{stock_code} 엔드포인트 테스트
```

### 시나리오 2: 채팅 기반 분석

```bash
# POST /api/v1/chat
curl -X POST https://abc123.ngrok.io/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "message": "삼성전자 현재가는?"
  }'
```

### 시나리오 3: 실시간 캐싱 동작 확인

```bash
# Redis 캐시 확인
docker-compose exec redis redis-cli

# Redis CLI에서
> KEYS realtime:price:*
> GET realtime:price:005930
```

---

## 시연 종료

### 방법 1: 스크립트 사용

```bash
./scripts/stop_demo.sh
```

### 방법 2: 수동 종료

```bash
# ngrok 중지
# Ctrl+C (ngrok 실행 터미널에서)

# Docker Compose 중지
docker-compose down

# 데이터까지 삭제 (선택)
docker-compose down -v
```

---

## 트러블슈팅

### 1. Docker Compose 시작 실패

```bash
# 로그 확인
docker-compose logs

# 특정 서비스 로그
docker-compose logs fastapi

# 컨테이너 재시작
docker-compose restart fastapi
```

### 2. FastAPI가 시작되지 않음

```bash
# 환경 변수 확인
cat .env

# 필수 환경 변수:
# - OPENAI_API_KEY
# - ANTHROPIC_API_KEY
# - DART_API_KEY
# - KIS_APP_KEY
# - KIS_APP_SECRET

# 데이터베이스 초기화
docker-compose exec fastapi alembic upgrade head
```

### 3. ngrok이 연결되지 않음

```bash
# ngrok 버전 확인
ngrok version

# authtoken 재설정
ngrok authtoken YOUR_TOKEN_HERE

# 직접 실행 테스트
ngrok http 8000
```

### 4. Celery가 동작하지 않음

```bash
# Redis 연결 확인
docker-compose exec redis redis-cli ping

# Celery Worker 로그
docker-compose logs -f celery-worker

# Celery 재시작
docker-compose restart celery-worker celery-beat
```

### 5. 포트 충돌

```bash
# 사용 중인 포트 확인
lsof -i :8000
lsof -i :5432
lsof -i :6379

# 프로세스 종료
kill -9 <PID>

# 또는 docker-compose.yml에서 포트 변경
ports:
  - "8001:8000"  # 호스트:컨테이너
```

---

## 시연 체크리스트

### 시연 전날

- [ ] Docker Desktop 실행 확인
- [ ] `.env` 파일 모든 API 키 설정
- [ ] `./scripts/start_demo.sh` 테스트
- [ ] ngrok authtoken 설정
- [ ] 외부 URL 접속 테스트
- [ ] API 문서 확인 (`/docs`)

### 시연 1시간 전

- [ ] 인터넷 연결 확인
- [ ] Docker 서비스 시작
- [ ] ngrok 터널 실행
- [ ] 외부 URL 복사/저장
- [ ] 모든 API 엔드포인트 테스트

### 시연 중

- [ ] ngrok URL 공유
- [ ] API 문서 시연
- [ ] 실시간 데이터 캐싱 설명
- [ ] Celery 동작 모니터링
- [ ] Q&A 준비

### 시연 후

- [ ] ngrok 터널 중지
- [ ] Docker 서비스 중지 (선택)
- [ ] 로그 백업 (선택)

---

## 고급 설정

### ngrok 커스텀 도메인 (유료)

```yaml
# ngrok.yml
version: "2"
tunnels:
  hama:
    addr: 8000
    proto: http
    domain: hama.ngrok.io
```

```bash
ngrok start hama
```

### ngrok 로그 저장

```bash
ngrok http 8000 --log=stdout > ngrok.log 2>&1 &
```

### Docker Compose 프로덕션 모드

```bash
# 프로덕션 환경 변수 사용
docker-compose --env-file .env.production up -d
```

---

## 참고 자료

- [ngrok 공식 문서](https://ngrok.com/docs)
- [Docker Compose 공식 문서](https://docs.docker.com/compose/)
- [FastAPI 배포 가이드](https://fastapi.tiangolo.com/deployment/)

---

## 문의

시연 환경 구성 중 문제 발생 시:
1. 로그 확인: `docker-compose logs`
2. 이슈 등록: GitHub Issues
3. 팀원에게 문의

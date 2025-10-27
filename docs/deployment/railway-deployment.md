# Railway 배포 가이드

Railway로 HAMA 백엔드를 배포하는 단계별 가이드입니다.

## 사전 준비

- ✅ GitHub 계정
- ✅ Railway 계정 (https://railway.app)
- ✅ 이 저장소가 GitHub에 push되어 있을 것

---

## 1단계: Railway 프로젝트 생성

### 1.1 Railway 회원가입
1. https://railway.app 접속
2. "Start a New Project" 클릭
3. GitHub 계정으로 로그인

### 1.2 새 프로젝트 생성
1. 대시보드에서 "New Project" 클릭
2. "Deploy from GitHub repo" 선택
3. `HAMA-backend` 저장소 선택

---

## 2단계: 서비스 추가

Railway는 여러 서비스를 하나의 프로젝트로 관리할 수 있습니다.

### 2.1 PostgreSQL 추가
1. 프로젝트 대시보드에서 "+ New" 클릭
2. "Database" → "PostgreSQL" 선택
3. 자동으로 `DATABASE_URL` 환경 변수 생성됨

### 2.2 Redis 추가
1. 프로젝트 대시보드에서 "+ New" 클릭
2. "Database" → "Redis" 선택
3. 자동으로 `REDIS_URL` 환경 변수 생성됨

---

## 3단계: FastAPI 서비스 배포

### 3.1 GitHub 저장소 연결
1. 프로젝트 대시보드에서 "+ New" 클릭
2. "GitHub Repo" 선택
3. `HAMA-backend` 선택
4. 서비스 이름: `hama-fastapi`

### 3.2 환경 변수 설정

Railway 대시보드 → `hama-fastapi` 서비스 → "Variables" 탭

**필수 환경 변수:**
```bash
# Application
ENV=production
DEBUG=False

# Database (자동 생성됨)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (자동 생성됨)
REDIS_URL=${{Redis.REDIS_URL}}

# Celery
CELERY_BROKER_URL=${{Redis.REDIS_URL}}/1
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}/2

# LLM APIs (실제 값 입력)
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
GEMINI_API_KEY=your-key
LLM_MODE=production

# 금융 APIs (실제 값 입력)
DART_API_KEY=your-key
KIS_APP_KEY=your-key
KIS_APP_SECRET=your-key
KIS_ACCOUNT_NUMBER=your-account

# CORS (프론트엔드 URL로 수정)
CORS_ORIGINS=https://your-frontend-url.vercel.app,https://hama-backend.up.railway.app
```

**참고:** `${{Postgres.DATABASE_URL}}` 형식은 Railway의 서비스 간 변수 참조입니다.

### 3.3 시작 명령어 설정

Railway 대시보드 → `hama-fastapi` → "Settings" 탭

**Start Command:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port $PORT
```

**참고:** Railway는 자동으로 `$PORT` 환경 변수를 제공합니다.

### 3.4 빌드 설정

Railway 대시보드 → `hama-fastapi` → "Settings" 탭

**Build Command:** (선택사항, 기본값 사용)
```bash
pip install -r requirements.txt
```

### 3.5 Health Check 설정

Railway 대시보드 → `hama-fastapi` → "Settings" 탭 → "Healthcheck"

**Path:**
```
/health
```

**Timeout:** 60초

---

## 4단계: Celery Worker 배포

### 4.1 새 서비스 추가
1. 프로젝트 대시보드에서 "+ New" 클릭
2. "GitHub Repo" 선택
3. **같은** `HAMA-backend` 저장소 선택
4. 서비스 이름: `hama-celery-worker`

### 4.2 환경 변수 설정

**FastAPI 서비스와 동일한 환경 변수 복사** (Variables 탭)

또는 Railway의 "Shared Variables" 기능 사용:
1. 프로젝트 설정 → "Shared Variables"
2. 공통 환경 변수 등록

### 4.3 시작 명령어 설정

Railway 대시보드 → `hama-celery-worker` → "Settings" 탭

**Start Command:**
```bash
celery -A src.workers.celery_app worker --loglevel=info --concurrency=2
```

---

## 5단계: Celery Beat 배포

### 5.1 새 서비스 추가
1. 프로젝트 대시보드에서 "+ New" 클릭
2. "GitHub Repo" 선택
3. **같은** `HAMA-backend` 저장소 선택
4. 서비스 이름: `hama-celery-beat`

### 5.2 환경 변수 설정

**FastAPI/Worker와 동일한 환경 변수 사용**

### 5.3 시작 명령어 설정

Railway 대시보드 → `hama-celery-beat` → "Settings" 탭

**Start Command:**
```bash
celery -A src.workers.celery_app beat --loglevel=info
```

---

## 6단계: 데이터베이스 마이그레이션

### 6.1 Railway CLI 설치 (선택)

```bash
# macOS
brew install railway

# 또는 npm
npm install -g @railway/cli
```

### 6.2 마이그레이션 실행

**방법 1: Railway 대시보드에서 직접 실행**

1. `hama-fastapi` 서비스 → "Deployments" 탭
2. 최신 배포 클릭 → "View Logs"
3. Railway Shell 열기
4. 명령어 실행:
```bash
alembic upgrade head
```

**방법 2: 로컬에서 Railway DB 연결**

```bash
# Railway CLI로 환경 변수 가져오기
railway variables

# DATABASE_URL 복사 후
DATABASE_URL=postgresql://... alembic upgrade head
```

---

## 7단계: 배포 확인

### 7.1 서비스 URL 확인

Railway 대시보드 → `hama-fastapi` → "Settings" 탭 → "Domains"

**기본 URL:** `https://hama-backend-production.up.railway.app`

### 7.2 Health Check

브라우저 또는 curl로 확인:
```bash
curl https://your-url.railway.app/health
```

**응답 예시:**
```json
{
  "status": "healthy",
  "database": "connected",
  "agents": "ready",
  "app": "HAMA"
}
```

### 7.3 API 문서 확인

브라우저에서:
```
https://your-url.railway.app/docs
```

Swagger UI가 열리면 성공!

---

## 8단계: 로그 모니터링

### 8.1 실시간 로그

Railway 대시보드 → 각 서비스 → "Deployments" → "View Logs"

### 8.2 Celery 작동 확인

**Celery Worker 로그:**
```
[worker] celery@... ready
[worker] Task update_realtime_market_data received
```

**Celery Beat 로그:**
```
[beat] Scheduler: Sending due task update-realtime-market-data
```

---

## 트러블슈팅

### 문제 1: 서비스가 시작되지 않음

**해결:**
1. 로그 확인 (`View Logs`)
2. 환경 변수 누락 확인
3. `requirements.txt` 의존성 확인

### 문제 2: DB 연결 실패

**해결:**
1. PostgreSQL 서비스가 Running 상태인지 확인
2. `DATABASE_URL` 환경 변수 확인
3. Railway 대시보드에서 PostgreSQL 재시작

### 문제 3: Celery가 작동하지 않음

**해결:**
1. Redis 서비스 확인
2. `CELERY_BROKER_URL` 환경 변수 확인
3. Worker 로그에서 에러 확인

### 문제 4: API 키 에러

**해결:**
1. 환경 변수에 실제 API 키 입력했는지 확인
2. 따옴표 없이 입력했는지 확인
3. 서비스 재배포 (`Redeploy`)

---

## 비용 관리

### Railway 무료 티어

- **$5/월 크레딧** 제공 (Trial)
- **충분한 리소스** (CPU, RAM, Bandwidth)

### 무료 티어 초과 시

- **Pro Plan**: $20/월 (월 $20 크레딧 포함)
- **추가 사용량**: 사용한 만큼만 청구

### 비용 절약 팁

1. **개발 중**: 사용하지 않을 때 서비스 일시 중지
2. **테스트**: 로컬 Docker Compose 사용
3. **프로덕션**: Railway 사용

---

## 자동 배포 (CI/CD)

### GitHub 연동 자동 배포

Railway는 GitHub Push 시 **자동 배포**됩니다:

```bash
# 코드 수정
git add .
git commit -m "Feat: 새 기능 추가"
git push origin main

# Railway가 자동으로:
# 1. GitHub Push 감지
# 2. Docker 빌드
# 3. 배포
# 4. Health Check
```

### 배포 브랜치 설정

Railway 대시보드 → 서비스 → "Settings" → "Source"

**Branch:** `main` (또는 원하는 브랜치)

---

## 커스텀 도메인 (선택)

### 도메인 연결

1. Railway 대시보드 → `hama-fastapi` → "Settings" → "Domains"
2. "Custom Domain" 클릭
3. 도메인 입력 (예: `api.hama.io`)
4. DNS 설정 (CNAME 레코드 추가)

**DNS 예시:**
```
Type: CNAME
Name: api
Value: hama-backend-production.up.railway.app
```

---

## 다음 단계

1. ✅ Railway 배포 완료
2. 🔄 프론트엔드 배포 (Vercel)
3. 🔗 프론트엔드 - 백엔드 연결
4. 📊 모니터링 설정 (선택)

---

## 참고 자료

- [Railway 공식 문서](https://docs.railway.app/)
- [FastAPI 배포 가이드](https://fastapi.tiangolo.com/deployment/)
- [Celery 배포](https://docs.celeryq.dev/en/stable/userguide/deployment.html)

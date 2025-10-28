# CORS 설정 수정 완료 가이드

## 변경 사항 요약

### 1. `.env` 파일 업데이트
Vercel 프리뷰 도메인을 CORS 허용 목록에 추가했습니다:
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:5173,https://hama-frontend-v2-git-develop-seongmin-hwangs-projects.vercel.app
```

### 2. `src/main.py` - CORS Middleware 강화
모든 Vercel 프리뷰 도메인을 허용하도록 정규식 패턴 추가:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app$",  # 모든 Vercel 프리뷰 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,  # Preflight 캐싱 (10분)
)
```

### 3. `docker-compose.yml` 업데이트
FastAPI 컨테이너에 CORS_ORIGINS 환경변수 전달 추가

### 4. CORS 테스트 스크립트 생성
`scripts/test_cors.sh` - OPTIONS 프리플라이트 검증 도구

---

## 서버 재시작 방법

### 방법 1: Docker Compose 사용 (권장)

```bash
# 1. 기존 컨테이너 중지 및 제거
docker-compose down

# 2. 새로운 설정으로 재시작
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f fastapi
```

### 방법 2: 로컬 개발 서버 사용

```bash
# 1. 실행 중인 서버 중지 (Ctrl+C)

# 2. 재시작
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 방법 3: 스크립트 사용

```bash
# 1. 기존 서비스 중지
./scripts/stop_demo.sh

# 2. 재시작
./scripts/start_demo.sh
```

---

## ngrok 재시작

```bash
# 1. 기존 ngrok 중지 (Ctrl+C)

# 2. 재시작
ngrok http 8000

# 또는 스크립트 사용
./scripts/ngrok_tunnel.sh
```

**중요:** ngrok URL이 변경되면 프론트엔드 설정도 업데이트해야 합니다!

---

## CORS 설정 검증

### 1. 테스트 스크립트 실행

```bash
# ngrok URL을 인자로 전달
./scripts/test_cors.sh https://your-ngrok-url.ngrok-free.dev
```

### 2. 수동 검증 (PowerShell)

```powershell
$origin = 'https://hama-frontend-v2-git-develop-seongmin-hwangs-projects.vercel.app'
$base = 'https://gifted-michiko-auric.ngrok-free.dev'  # 현재 ngrok URL

Invoke-WebRequest -Method Options -Uri "$base/api/v1/chat/" `
  -Headers @{
    Origin=$origin
    "Access-Control-Request-Method"="POST"
    "Access-Control-Request-Headers"="content-type,accept,authorization"
  } | Select-Object StatusCode,Headers
```

**기대 결과:**
- `StatusCode`: 200 또는 204
- `Headers`에 다음 항목 포함:
  - `access-control-allow-origin`: Vercel 도메인
  - `access-control-allow-methods`: POST 포함
  - `access-control-allow-headers`: content-type, accept, authorization 포함

### 3. curl로 검증 (Linux/Mac)

```bash
curl -i -X OPTIONS \
  https://your-ngrok-url.ngrok-free.dev/api/v1/chat/ \
  -H "Origin: https://hama-frontend-v2-git-develop-seongmin-hwangs-projects.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,accept,authorization"
```

---

## 문제 해결

### ❌ 여전히 400 에러가 발생하는 경우

**1. 환경변수 확인**
```bash
# Docker 사용 시
docker exec hama-fastapi env | grep CORS_ORIGINS

# 로컬 서버 사용 시
echo $CORS_ORIGINS
```

**2. FastAPI 로그 확인**
```bash
# Docker 사용 시
docker-compose logs -f fastapi

# 에러 메시지에서 "Disallowed CORS origin" 검색
```

**3. 브라우저 개발자 도구 확인**
- Network 탭에서 OPTIONS 요청 확인
- Response Headers에 CORS 헤더가 있는지 확인

**4. 캐시 문제**
- 브라우저 캐시 클리어
- Vercel 프리뷰 재배포
- ngrok 재시작 (URL 변경 가능)

### ⚠️ LLM API 크레딧 부족

현재 Claude API 크레딧이 부족한 상태입니다. CORS 문제가 해결되면:

1. `.env` 파일에서 다른 LLM 사용:
```env
LLM_MODE=google  # Gemini 사용
# 또는
LLM_MODE=openai  # GPT 사용
```

2. API 크레딧 충전

---

## 체크리스트

- [ ] `.env` 파일 업데이트 확인
- [ ] `src/main.py` CORS middleware 설정 확인
- [ ] 서버 재시작
- [ ] ngrok 재시작 (필요 시)
- [ ] CORS 테스트 스크립트 실행
- [ ] OPTIONS 요청 200/204 확인
- [ ] 브라우저에서 실제 POST 요청 테스트
- [ ] Vercel 프리뷰에서 API 연동 확인

---

## 추가 도움말

### Vercel 프리뷰 URL이 자주 바뀌는 경우

현재 설정은 정규식(`r"https://.*\.vercel\.app$"`)으로 모든 Vercel 도메인을 허용하므로,
브랜치별 프리뷰 URL이 바뀌어도 추가 설정 없이 작동합니다.

### 프로덕션 배포 시

프로덕션 환경에서는 CORS를 더 엄격하게 설정하세요:
```python
# 개발 환경
if settings.ENV == "development":
    allow_origin_regex = r"https://.*\.vercel\.app$"
else:
    # 프로덕션: 정확한 도메인만 허용
    allow_origins = ["https://hama.yourdomain.com"]
```

---

## 참고 문서

- [FastAPI CORS 설정](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN - CORS](https://developer.mozilla.org/ko/docs/Web/HTTP/CORS)
- [Vercel Deployment URLs](https://vercel.com/docs/concepts/deployments/preview-deployments)

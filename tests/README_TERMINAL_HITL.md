# 터미널 HITL 테스트 가이드

## 개요

HAMA 시스템의 전체 프로세스를 터미널에서 대화형으로 테스트할 수 있는 도구입니다.

실제 API 라우터를 호출하여 다음 플로우를 검증합니다:
1. **사용자 요구사항 입력** → Master Agent 라우팅
2. **HITL 승인 요청** → 터미널에서 승인/거부 입력
3. **최종 결과 출력** → 실행 결과 확인

## 파일 구성

```
tests/
├── test_terminal_hitl.py          # 대화형 테스트 (사용자 입력 필요)
├── test_terminal_hitl_auto.py     # 자동 테스트 (데모용)
└── README_TERMINAL_HITL.md        # 이 문서
```

## 사용법

### 1. 대화형 테스트 (권장)

터미널에서 직접 입력하며 전체 프로세스를 테스트합니다.

```bash
# 실행
PYTHONPATH=. python tests/test_terminal_hitl.py
```

**실행 화면:**

```
HAMA HITL 터미널 테스트 시작

자동화 레벨을 선택하세요:
  1. Pilot - AI가 거의 모든 것을 처리 (월 1회 확인)
  2. Copilot - AI가 제안, 큰 결정만 승인 (기본값)
  3. Advisor - AI는 정보만 제공, 사용자가 결정

선택 [1/2/3] (2): 2

━━━ Step 1: 사용자 요구사항 입력 ━━━

예시:
  - 삼성전자 분석해줘
  - 삼성전자 100주 매수해줘
  - 내 포트폴리오 리밸런싱해줘
  - 반도체 관련 종목 추천해줘

>>> 요청사항을 입력하세요: 삼성전자 100주 매수해줘

━━━ Step 2: Master Agent 실행 ━━━

AI가 분석 중입니다...

━━━ Step 3: 사용자 승인 요청 ━━━

⚠️  승인이 필요합니다

유형: trade_approval
메시지: 매매 주문을 승인하시겠습니까?

결정을 선택하세요:
  1. 승인 (approved) - 제안대로 실행
  2. 거부 (rejected) - 실행 취소
  3. 수정 (modified) - 수정 후 실행

선택 [1/2/3] (1): 1

━━━ Step 4: 최종 결과 ━━━

상태: APPROVED
승인 완료 - 매매가 실행되었습니다.
```

### 2. 자동 테스트 (데모용)

미리 정의된 시나리오를 자동으로 실행합니다.

```bash
# 실행
PYTHONPATH=. python tests/test_terminal_hitl_auto.py
```

**테스트 시나리오:**
1. 종목 분석 (승인 불필요) - "삼성전자 분석해줘"
2. 매매 요청 (승인) - "삼성전자 100주 매수해줘"
3. 매매 요청 (거부) - "SK하이닉스 50주 매도해줘"

## 테스트 커버리지

### ✅ 검증되는 기능

1. **Master Agent 라우팅**
   - 사용자 의도 분석 (LLM)
   - 적절한 에이전트 선택 및 실행

2. **HITL 승인 프로세스**
   - interrupt() 기반 중단
   - 승인/거부/수정 결정 처리
   - Command(resume) 재개

3. **실제 API 호출**
   - `POST /chat` 엔드포인트
   - `POST /chat/approve` 엔드포인트
   - LangGraph 상태 관리

4. **자동화 레벨별 동작**
   - Level 2 (Copilot): 매매/리밸런싱만 승인
   - Level 3 (Advisor): 모든 주요 결정 승인

5. **데이터 연동**
   - FinanceDataReader (주가 데이터)
   - DART API (재무제표)
   - Redis 캐싱

### ⚠️ 현재 제한사항

- **실제 매매 미실행**: Mock 거래만 수행 (Phase 2 예정)
- **단일 사용자**: 고정 UUID 사용
- **WebSocket 미지원**: HTTP 요청/응답만

## 주요 기능

### 1. 자동화 레벨 선택

```python
# Level 2 (Copilot) - 기본값
tester = TerminalHITLTester(automation_level=2)

# Level 3 (Advisor) - 모든 결정에 승인 필요
tester = TerminalHITLTester(automation_level=3)
```

### 2. 대화 이어가기

같은 `conversation_id`로 여러 요청을 처리할 수 있습니다.

```
>>> 삼성전자 분석해줘
(AI 응답)

다른 요청을 테스트하시겠습니까? [Y/n]: y

>>> 100주 매수해줘
(같은 대화 컨텍스트에서 처리)
```

### 3. 승인 옵션

**승인 (approved):**
- 제안대로 실행
- 메모 추가 가능

**거부 (rejected):**
- 실행 취소
- 거부 사유 입력 가능

**수정 (modified):**
- 일부 파라미터 수정 후 실행
- JSON 형식으로 수정사항 입력
  ```json
  {"quantity": 50, "price": 60000}
  ```

## 출력 스타일

Rich 라이브러리를 사용하여 보기 좋은 터미널 UI를 제공합니다:

- **Panel**: 주요 메시지 강조
- **Markdown**: AI 응답 포맷팅
- **Table**: 메타데이터 정리
- **Color**: 상태별 색상 (승인=green, 거부=red, 수정=yellow)
- **Spinner**: 진행 상황 표시

## 트러블슈팅

### 1. Redis 연결 오류

```bash
# Redis 서버 시작
brew services start redis

# 연결 확인
redis-cli ping
```

### 2. LLM API 오류

```bash
# .env 파일 확인
cat .env | grep API_KEY

# 환경 변수 로드 확인
python -c "from src.config.settings import settings; print(settings.ANTHROPIC_API_KEY)"
```

### 3. 대화형 입력 오류 (EOFError)

백그라운드 실행 시 발생합니다. 반드시 **포그라운드**에서 실행하세요:

```bash
# ❌ 백그라운드 실행 (오류)
nohup python tests/test_terminal_hitl.py &

# ✅ 포그라운드 실행 (정상)
python tests/test_terminal_hitl.py
```

## 의존성

테스트 실행에 필요한 패키지:

```toml
[dependencies]
rich = ">=14.0.0"  # 터미널 UI
fastapi = ">=0.118.0"
langgraph = "0.6.8"
redis = ">=5.0.0"
```

설치:
```bash
pip install rich
```

## 예제 시나리오

### 시나리오 1: 종목 분석

```
>>> 삼성전자 최근 실적 분석해줘
```

**예상 결과:**
- Research Agent 실행
- 재무제표, 주가 데이터 수집
- Bull/Bear 분석 종합
- 승인 없이 결과 반환

### 시나리오 2: 매매 실행

```
>>> 삼성전자 100주 시장가로 매수해줘
```

**예상 결과:**
1. Research → Strategy → Risk Agent 순차 실행
2. Trading Agent에서 interrupt 발생
3. 사용자 승인 요청
4. 승인 시 → Mock 거래 실행
5. 결과 반환

### 시나리오 3: 포트폴리오 리밸런싱

```
>>> 내 포트폴리오 리밸런싱해줘
```

**예상 결과:**
1. Portfolio Agent 실행
2. 현재 포트폴리오 분석
3. 목표 비중 계산
4. 변경안 제시 + 승인 요청
5. 승인 시 → 여러 거래 실행

## 개발자 노트

### 코드 구조

```python
class TerminalHITLTester:
    def __init__(self, automation_level: int = 2)

    async def get_user_input(self) -> str
        # 터미널 입력

    async def call_chat_api(self, message: str) -> ChatResponse
        # POST /chat 호출

    async def handle_approval(self, approval_request: dict) -> ApprovalResponse
        # 승인 처리 + POST /chat/approve 호출

    async def run_test(self)
        # 전체 플로우 실행
```

### 커스터마이징

자동 시나리오 추가:

```python
# test_terminal_hitl_auto.py
await tester.test_scenario(
    scenario_name="커스텀 시나리오",
    message="원하는 요청 메시지",
    auto_approve=True  # or False
)
```

## 다음 단계

Phase 2에서 추가될 기능:
- [ ] 한국투자증권 API 연동 (실제 매매)
- [ ] WebSocket 실시간 알림
- [ ] 여러 사용자 동시 테스트
- [ ] 시나리오 스크립트 파일 지원

## 참고 문서

- [PRD.md](../docs/PRD.md) - 제품 요구사항
- [CLAUDE.md](../CLAUDE.md) - LangGraph HITL 구현 가이드
- [chat.py](../src/api/routes/chat.py) - API 라우터 구현

---

**문의**: 테스트 관련 문제는 GitHub Issues에 등록해주세요.

# HAMA 아키텍처 개요 (2025-11-09 업데이트)

Router Agent 기반 3-Tier 라우팅 시스템을 중심으로 한국투자증권(KIS)·한국은행(BOK) 연계를 포함한 현재 백엔드 구조를 요약합니다. 팀이 신규 기능을 설계하거나 장애를 분석할 때 참조할 수 있는 최신 구조 문서입니다.

> **주요 변경사항 (2025-11-09):**
> - ❌ Supervisor 패턴 제거 (Router와 중복)
> - ❌ `/chat` 엔드포인트 제거 (레거시)
> - ✅ Router Agent 강화 (단일 진입점)
> - ✅ Trading Agent 단순화 (9→3 노드)

---

## 1. 시스템 오버뷰

```
┌──────────────┐      ┌───────────────────────┐      ┌─────────────────────────┐
│    사용자    │ ───▶ │ FastAPI (src/main.py) │ ───▶ │  Router Agent ⭐        │
│  (Chat/Web)  │      │  · SSE Streaming       │      │ (src/agents/router)     │
└──────────────┘      │  · HITL 승인 엔드포인트 │      │  단일 진입점            │
                      │  · /multi-stream       │      └────────────┬───────────┘
                      └──────────────┬────────┘                   ▼
                                     │                 ┌─────────────────────────┐
                                     │                 │ 3-Tier 라우팅 우선순위:  │
                                     │                 │ 1) Worker 직접 호출     │
                                     │                 │ 2) 직접 답변            │
                                     │                 │ 3) Agent 호출           │
                                     │                 └────────────┬───────────┘
                                     │                              ▼
                                     │                 ┌─────────────────────────┐
                                     │                 │ Research / Strategy /   │
                                     │                 │ Risk / Trading /        │
                                     │                 │ Portfolio / Monitoring  │
                                     │                 │ (LangGraph Subgraphs)   │
                                     │                 └────────────┬───────────┘
                                     │                              ▼
                                     │                 ┌─────────────────────────┐
                                     │                 │ Service Layer            │
                                     │                 │  · KISService            │
                                     │                 │  · PortfolioService      │
                                     │                 │  · BOKService            │
                                     │                 │  · StockDataService 등   │
                                     │                 └────────────┬───────────┘
                                     │                              ▼
                                     │                 ┌─────────────────────────┐
                                     │                 │ External APIs & Storage │
                                     │                 │  · KIS Open Trading     │
                                     │                 │  · BOK ECOS             │
                                     │                 │  · DART, pykrx          │
                                     │                 │  · PostgreSQL, 메모리 캐시 │
                                     │                 └─────────────────────────┘
```

- **API 계층** – FastAPI 라우터(`src/api/routes/*`)가 SSE 스트리밍, HITL 승인, 아티팩트 관리 엔드포인트를 제공한다.
- **Router Agent** – `src/agents/router/router_agent.py`가 Claude Sonnet 4.5 기반 Pydantic Structured Output으로 쿼리를 분석하고 필요한 에이전트/워커를 동적으로 선택한다.
- **Service 레이어** – 외부 API 호출(KIS, BOK, DART, pykrx)과 SQLAlchemy 기반 DB 동기화를 담당하는 동기/비동기 혼합 구조다.

---

## 2. Router Agent & 3-Tier 라우팅 시스템

### 2.1 Router Agent 아키텍처

`src/agents/router/router_agent.py`는 Claude Sonnet 4.5를 사용한 고성능 라우팅 시스템으로, 다음 3가지 우선순위로 쿼리를 처리한다:

**우선순위 1: Worker 직접 호출 (초고속)**
- 간단한 조회성 쿼리는 Worker를 직접 호출하여 LLM 비용 절감
- 예: "삼성전자 현재가?" → `stock_price` Worker 직접 호출
- 지원 Worker: `stock_price`, `index_price`

**우선순위 2: 직접 답변**
- 일반적인 질문은 LLM이 즉시 답변
- 예: "HAMA가 뭐야?", "포트폴리오 조회 방법은?"

**우선순위 3: 에이전트 호출**
- 복잡한 분석/매매는 전문 에이전트 서브그래프로 라우팅
- 예: "삼성전자 분석해줘" → `research_agent`
- 예: "리밸런싱해줘" → `portfolio_agent`

### 2.2 RoutingDecision 스키마

```python
class RoutingDecision(BaseModel):
    query_complexity: str  # simple | moderate | expert
    user_intent: str  # quick_info | stock_analysis | trading | etc
    stock_names: Optional[list[str]]  # 추출된 종목명
    agents_to_call: list[str]  # research, strategy, risk, trading, portfolio
    depth_level: str  # brief | detailed | comprehensive
    personalization: PersonalizationSettings
    reasoning: str
    worker_action: Optional[str]  # stock_price or index_price
    worker_params: Optional[WorkerParams]
    direct_answer: Optional[str]  # 간단한 질문 즉시 답변
```

### 2.3 에이전트 서브그래프

각 에이전트는 독립적인 LangGraph 서브그래프로 구현되며, HITL이 필요한 노드에서 `interrupt()`를 사용한다:

| 에이전트 | 노드 수 | 주요 기능 | 외부 의존성 |
|----------|---------|----------|-------------|
| `research_agent` | 8 workers | 재무·기술·거래량 분석 | DART, pykrx |
| `strategy_agent` | 6 specialists | 매수/매도 전략, 시장 분석 | BOK, 섹터 데이터 |
| `risk_agent` | 단일 노드 | 포트폴리오 리스크 측정 | 포트폴리오 스냅샷, 인메모리 캐시 |
| `trading_agent` | 3 노드 | 주문 준비→승인→실행 | `trading_service`, `kis_service` |
| `portfolio_agent` | 3 노드 | 리밸런싱, 최적화 | `portfolio_optimizer` |
| `monitoring_agent` | 배경 전용 | 실시간 알림 (미구현) | WebSocket (예정) |

**공통 설계 원칙:**
- `messages`를 통한 대화 맥락 공유
- `{action}_prepared/approved/executed` 플래그로 멱등성 보장
- 재실행 시 부작용 방지를 위한 상태 체크

---

## 3. Trading Agent: 단순화된 3-노드 매매 흐름

Trading Agent는 기존 9-노드 ReAct 패턴에서 **3-노드 선형 플로우**로 단순화되었다 (58% 코드 감소, 80% LLM 호출 감소):

### 3.1 노드 구성

**1. prepare_trade_node** (LLM 기반 주문 준비)
- 사용자 쿼리에서 `order_type`, `stock_code`, `quantity`, `order_price` 추출
- `trading_service.create_pending_order`로 주문 생성 (pending 상태)
- State: `trade_prepared=True`, `trade_summary` 저장

**2. approval_trade_node** (HITL Interrupt)
- Automation Level에 따라 승인 여부 결정:
  - Level 1 (Pilot): 자동 승인 (`skip_hitl=True`)
  - Level 2+ (Copilot/Advisor): `interrupt()` 호출, 사용자 승인 대기
- 승인 시: `trade_approved=True`
- 거부 시: `rejection_reason` 저장, END로 분기

**3. execute_trade_node** (주문 실행)
- `trading_service.execute_order` 호출
  - `kis_service.place_order`로 실제 주문 전송
  - DB에 체결 내역 기록 (filled)
  - 포트폴리오 업데이트
- State: `trade_executed=True`, `trade_order_id`, `trade_result` 저장

### 3.2 플로우 다이어그램

```
prepare_trade → approval_trade → execute_trade → END
                       ↓
                   (거부 시)
                       ↓
                     END
```

### 3.3 제거된 노드 및 이유

| 제거된 노드 | 제거 이유 |
|------------|----------|
| `query_intent_classifier` | prepare_trade에서 LLM이 직접 처리 |
| `planner` | 선형 플로우에 불필요 |
| `task_router` | 단순 큐 관리, 제거 가능 |
| `buy_specialist` | Strategy Agent로 이동 예정 |
| `sell_specialist` | Strategy Agent로 이동 예정 |
| `risk_reward_calculator` | Strategy Agent로 이동 예정 |

> ⚠️ 체결 확인·취소 API는 미구현이며, KIS 실패 시에도 시뮬레이션 체결이 기록된다. 후속 개선 항목은 `docs/plan/phase2-followups.md` 참고.

---

## 4. 데이터 소스 및 통합 상태

- **KIS Open Trading API**  
  - 앱 기동 시 `init_kis_service`가 토큰 발급을 수행하며 환경에 따라 실전/모의 URL을 자동 선택 (`src/main.py:41`).  
  - 잔고 조회(`get_account_balance`), 일중 시세(`get_stock_price`), 주문 실행(`place_order`)이 구현되어 있고 캐시 매니저를 통해 토큰과 시세를 보존.
- **한국은행 BOK ECOS API**  
  - `bok_service.get_macro_indicators`가 기준금리·CPI·환율을 묶어 반환하고, 전략 에이전트의 `MarketAnalyzer`가 시장 사이클 판단에 활용 (`src/services/bok_service.py:20`, `src/agents/strategy/market_analyzer.py:35`).  
  - 현재는 동기 `requests` 호출과 간단한 캐시만 적용되어 있어 주기 호출 시 타임아웃 관리가 필요하다.
- **기타 데이터 소스**  
  - DART, pykrx를 통한 재무·시세 데이터 수집이 Research 에이전트 도구에서 사용된다.  
  - 인메모리 캐시는 토큰과 실시간 시세·거시 데이터 캐싱, PostgreSQL은 포트폴리오·주문·사용자 프로필 영속화를 담당한다.

---

## 5. 운영 고려 사항

- FastAPI `lifespan` 훅이 워커별로 KIS 토큰을 발급하므로 멀티 프로세스 배포 시 호출 빈도와 rate limit을 감안해야 한다.
- BOK API 키가 현재 서비스 객체에 기본값으로 존재하므로 `.env` 설정과 보안 검토가 필요하다(후속 작업 문서 참고).
- 거래 실행은 현재 동기 플로우이므로 주문 지연/장애 시 Supervisor의 재시도 정책과 조합해 모니터링을 강화해야 한다.

---

## 6. 참조 문서

- 상세 LangGraph 패턴: `docs/guides/langgraph-patterns.md`
- 테스트 전략: `docs/guides/testing-guide.md`
- Phase 2 후속 과제: `docs/plan/phase2-followups.md`

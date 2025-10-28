# HAMA Phase 2 아키텍처 개요

LangGraph Supervisor 패턴을 중심으로 Phase 2에서 통합된 한국투자증권(KIS)·한국은행(BOK) 연계를 포함한 현재 백엔드 구조를 요약합니다. 팀이 신규 기능을 설계하거나 장애를 분석할 때 참조할 수 있는 최신 구조 문서입니다.

---

## 1. 시스템 오버뷰

```
┌──────────────┐      ┌───────────────────────┐      ┌─────────────────────────┐
│    사용자    │ ───▶ │ FastAPI (src/main.py) │ ───▶ │ LangGraph Supervisor    │
│  (Chat/Web)  │      │  · REST / Streaming    │      │ (src/agents/graph_master)│
└──────────────┘      │  · HITL 승인 엔드포인트 │      └────────────┬───────────┘
                      └──────────────┬────────┘                   ▼
                                     │                 ┌─────────────────────────┐
                                     │                 │ Research / Strategy /   │
                                     │                 │ Risk / Trading /        │
                                     │                 │ Portfolio / General     │
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
                                     │                 │  · PostgreSQL, Redis    │
                                     │                 └─────────────────────────┘
```

- **API 계층** – FastAPI 라우터(`src/api/routes/*`)가 채팅, 승인, 대시보드, 아티팩트 관리 엔드포인트를 제공한다.
- **LangGraph Supervisor** – `src/agents/graph_master.py`가 LLM 프롬프트 기반 Supervisor를 빌드하여 필요한 서브그래프를 병렬로 실행한다.
- **Service 레이어** – 외부 API 호출(KIS, BOK, DART, pykrx)과 SQLAlchemy 기반 DB 동기화를 담당하는 동기/비동기 혼합 구조다.

---

## 2. LangGraph Supervisor & 에이전트

- `build_supervisor`는 Research·Strategy·Risk·Trading·Portfolio·General 에이전트를 등록하고, 병렬 tool 호출 규칙을 프롬프트로 강제한다 (`src/agents/graph_master.py:47`).
- 각 에이전트는 LangGraph 서브그래프로 정의되어 있으며, HITL이 필요한 노드에서 `langgraph.types.interrupt`를 사용해 승인 대기 지점을 노출한다.
- 공통 상태 설계  
  - `messages`를 통해 대화 맥락을 공유하고, `{action}_prepared/approved/executed` 플래그로 멱등성을 보장한다.  
  - 재실행 시 부수효과를 피하기 위해 상태 체크 후 조기 반환을 수행한다.

대표 에이전트 요약:

| 에이전트 | 주요 노드 | 외부 의존성 |
|----------|-----------|-------------|
| `research_agent` | 재무·기술 분석 | DART, pykrx |
| `strategy_agent` | `market_analyzer` | `bok_service`, 섹터 데이터 |
| `risk_agent` | 포트폴리오 리스크 측정 | 포트폴리오 스냅샷, Redis 캐시 |
| `trading_agent` | 주문 준비·승인·실행 | `trading_service` → `kis_service` |
| `portfolio_agent` | 리밸런싱, 최적화 | `portfolio_service`, `portfolio_optimizer` |

---

## 3. HITL 매매 실행 흐름

1. **주문 생성** – `trading_service.create_pending_order`가 주문 엔티티를 `pending` 상태로 저장 (`src/services/trading_service.py:37`).  
2. **사용자 승인** – `prepare_trade_node` 이후 `approval_trade_node`에서 `trade_approval` interrupt를 발생시켜 프런트 승인 UI를 호출 (`src/agents/trading/nodes.py:62`).  
3. **주문 실행** – `trading_service.execute_order`가 승인된 주문을 처리:  
   - `kis_service.place_order`로 실 주문 전송 (`src/services/kis_service.py:464`)  
   - KIS 성공 여부와 관계없이 DB에 `filled` 체결 내역을 기록하고 포트폴리오 반영 (`src/services/trading_service.py:180`)  
4. **사후 동기화** – 필요 시 `portfolio_service.sync_with_kis`가 계좌 잔고를 재조회하여 DB와 맞춘다 (`src/services/portfolio_service.py:151`).

> ⚠️ 체결 확인·취소 API가 아직 미구현이며, KIS 실패 시에도 시뮬레이션 체결이 기록된다. 후속 개선 항목은 `docs/plan/phase2-followups.md` 참고.

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
  - Redis는 토큰과 실시간 시세·거시 데이터 캐싱, PostgreSQL은 포트폴리오·주문·사용자 프로필 영속화를 담당한다.

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

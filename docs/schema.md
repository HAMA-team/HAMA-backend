# HAMA Agent State 스키마 문서

## 개요

HAMA 시스템은 LangGraph 기반 멀티 에이전트 아키텍처를 사용하며, 각 에이전트는 TypedDict로 정의된 State를 사용합니다.

---

## GraphState (Master Agent)

Master Agent가 사용하는 전체 그래프 공유 상태입니다.

```python
from typing import TypedDict, Annotated, Sequence, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class GraphState(TypedDict, total=False):
    """Master Agent 전체 그래프 상태"""

    # LangGraph 표준 필드
    messages: Annotated[Sequence[BaseMessage], add_messages]
    """대화 메시지 히스토리 (LangGraph 표준)"""

    # 사용자 컨텍스트
    user_id: str
    """사용자 ID"""

    conversation_id: str
    """대화 세션 ID"""

    intervention_required: int
    """개입 필요 여부 (1: Pilot, 2: Copilot, 3: Advisor)"""

    user_profile: Optional[dict]
    """사용자 프로필 (투자 성향, 위험 허용도 등)"""

    # 의도 및 라우팅
    intent: Optional[str]
    """사용자 질의 의도 (analysis/trading/portfolio/general 등)"""

    agents_to_call: Optional[list[str]]
    """호출할 에이전트 목록"""

    # 에이전트 결과
    research_result: Optional[dict]
    """Research Agent 분석 결과"""

    strategy_result: Optional[dict]
    """Strategy Agent 결과"""

    portfolio_result: Optional[dict]
    """Portfolio Agent 결과"""

    risk_result: Optional[dict]
    """Risk Agent 결과"""

    trading_result: Optional[dict]
    """Trading Agent 결과"""

    # HITL 상태
    requires_approval: bool
    """승인 필요 여부"""

    approval_type: Optional[str]
    """승인 유형 (trade/rebalance/strategy 등)"""

    # 최종 응답
    final_response: Optional[dict]
    """사용자에게 반환할 최종 응답"""
```

---

## ResearchState (Research Agent)

Research Agent 서브그래프가 사용하는 상태입니다.

### 기본 필드

```python
class ResearchState(TypedDict, total=False):
    """Research Agent 서브그래프 상태"""

    # LangGraph 표준
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 기본 정보
    stock_code: str
    """종목 코드 (예: 005930)"""

    request_id: Optional[str]
    """요청 ID"""

    # 동적 Worker 선택 시스템 (v1.2 신규)
    analysis_depth: Optional[str]
    """분석 깊이 레벨 ("quick" | "standard" | "comprehensive")

    - quick: 빠른 분석 (1-3 workers, 10-20초)
    - standard: 표준 분석 (4-5 workers, 30-45초) - 기본값
    - comprehensive: 종합 분석 (7-8 workers, 60-90초)
    """

    focus_areas: Optional[list[str]]
    """집중 분석 영역 (예: ["technical", "trading_flow"])

    쿼리에서 특정 분석 영역을 요청한 경우 우선적으로 포함:
    - technical: 기술적 분석
    - trading_flow: 거래 동향 분석
    - information: 정보 분석
    - macro: 거시경제 분석
    """

    depth_reason: Optional[str]
    """분석 깊이 선택 이유 (디버깅/로깅용)"""

    user_profile: Optional[dict]
    """사용자 프로파일

    포함 정보:
    - preferred_depth: 선호 분석 깊이 ("brief" | "detailed" | "comprehensive")
    - expertise_level: 전문성 수준 ("beginner" | "intermediate" | "expert")
    - technical_level: 기술적 분석 이해도 ("basic" | "intermediate" | "advanced")
    - trading_style: 투자 스타일 ("short_term" | "long_term")
    """

    # 데이터 수집 결과
    price_data: Optional[dict]
    """가격 데이터 (현재가, 거래량, 일봉/주봉)"""

    company_data: Optional[dict]
    """기업 정보 (DART API)"""

    fundamental_data: Optional[dict]
    """재무 데이터 (PER, PBR, ROE 등)"""

    technical_indicators: Optional[dict]
    """기술적 지표 (RSI, MACD, 이평선 등)"""

    investor_trading_data: Optional[dict]
    """투자자별 거래 데이터 (외국인/기관/개인)"""

    market_index_data: Optional[dict]
    """시장 지수 데이터 (KOSPI, KOSDAQ)"""

    market_cap_data: Optional[dict]
    """시가총액 및 유동주식 정보"""
```

### Specialist 분석 결과 필드

```python
    # === Specialist Worker 분석 결과 ===

    technical_analysis: Optional[dict]
    """기술적 분석 결과 (Technical Analyst Worker)

    포함 정보:
    - trend: 추세 (상승추세/하락추세/횡보)
    - trend_strength: 추세 강도 (1-5)
    - technical_signals: RSI/MACD 신호
    - moving_average_analysis: 이평선 분석 (골든크로스/데드크로스)
    - support_resistance: 지지선/저항선
    - short_term_outlook: 단기 전망
    """

    trading_flow_analysis: Optional[dict]
    """거래 동향 분석 결과 (Trading Flow Analyst Worker)

    포함 정보:
    - foreign_investor: 외국인 투자자 동향 (순매수/순매도/보합)
    - institutional_investor: 기관 투자자 동향
    - individual_investor: 개인 투자자 동향
    - supply_demand_analysis: 수급 분석 (긍정적/부정적/중립)
    - leading_investor: 주도 투자자
    """

    information_analysis: Optional[dict]
    """정보 분석 결과 (Information Analyst Worker)

    포함 정보:
    - market_sentiment: 시장 센티먼트 (긍정적/부정적/중립)
    - risk_level: 리스크 레벨 (높음/중간/낮음)
    - positive_factors: 호재 요인 리스트
    - negative_factors: 악재 요인 리스트
    - news_summary: 뉴스 요약
    """
```

### 기존 분석 결과 필드

```python
    # === Bull/Bear Analyst 결과 ===

    bull_analysis: Optional[dict]
    """상승 시나리오 분석 (Bull Analyst)"""

    bear_analysis: Optional[dict]
    """하락 시나리오 분석 (Bear Analyst)"""

    # === 최종 통합 결과 ===

    consensus: Optional[dict]
    """최종 합의 분석 결과 (Synthesis Node)

    포함 정보:
    - recommendation: 추천 (BUY/SELL/HOLD)
    - confidence: 신뢰도 (1-5)
    - target_price: 목표가
    - current_price: 현재가
    - upside_potential: 상승 여력
    - technical_summary: 기술적 분석 요약
    - trading_flow_summary: 거래 동향 요약
    - information_summary: 정보 분석 요약
    - fundamental_summary: 펀더멘털 요약
    """
```

### Deep Agent 패턴 필드

```python
    # === Planner & Router ===

    current_task: Optional[dict]
    """현재 실행 중인 작업

    구조:
    {
        "id": "task_1",
        "worker": "technical",  # data/bull/bear/technical/trading_flow/information/macro/insight
        "description": "기술적 분석 수행",
        "dependencies": []
    }
    """

    task_results: Optional[dict]
    """Worker별 작업 결과

    구조:
    {
        "technical": {...},
        "trading_flow": {...},
        "information": {...}
    }
    """
```

---

## TradingState (Trading Agent)

Trading Agent 서브그래프가 사용하는 상태입니다.

```python
class TradingState(TypedDict, total=False):
    """Trading Agent 서브그래프 상태"""

    # LangGraph 표준
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 기본 정보
    request_id: str
    user_id: str
    portfolio_id: str
    query: str
    intervention_required: int

    # 주문 정보
    stock_code: str
    """종목 코드"""

    quantity: Optional[int]
    """주문 수량"""

    order_type: str
    """주문 유형 (BUY/SELL)"""

    order_price: Optional[float]
    """주문 가격"""

    # === Research Agent 결과 ===
    research_result: Optional[dict]
    """Research Agent의 consensus 결과"""

    # === Buy/Sell Specialist 결과 ===

    buy_score: Optional[int]
    """매수 점수 (1-10점)

    점수 해석:
    - 8-10점: 강력 매수 추천
    - 7점: 매수 고려
    - 6점 이하: 매수 부적합

    평가 요소:
    - 기술적 분석 (Technical)
    - 거래 동향 (Trading Flow)
    - 정보 분석 (Information)
    - 펀더멘털 (Fundamental)
    """

    buy_rationale: Optional[str]
    """매수 근거 및 전략"""

    sell_rationale: Optional[str]
    """매도 근거 및 전략"""

    investment_period: Optional[str]
    """투자 기간 (단기/중기/장기)

    - 단기: 1-3개월
    - 중기: 3-12개월
    - 장기: 12개월 이상
    """

    # === Risk/Reward Calculator 결과 ===

    target_price: Optional[float]
    """목표가 (원)

    투자 기간별 목표 수익률:
    - 단기: 5%
    - 중기: 10%
    - 장기: 20%

    매수 점수 8점 이상 시 20% 상향 조정
    """

    stop_loss: Optional[float]
    """손절가 (원)

    투자 기간별 손절 비율:
    - 단기: -3%
    - 중기: -5%
    - 장기: -7%
    """

    risk_reward_ratio: Optional[float]
    """Risk/Reward 비율

    최소 1.5:1 이상 보장
    계산식: (목표가 - 현재가) / (현재가 - 손절가)
    """

    # === HITL 진행 상태 ===

    trade_prepared: bool
    """거래 준비 완료 여부"""

    trade_approved: bool
    """거래 승인 여부"""

    trade_executed: bool
    """거래 실행 완료 여부"""

    # 최종 결과
    execution_result: Optional[dict]
    """거래 실행 결과"""
```

---

## PortfolioState (Portfolio Agent)

Portfolio Agent 서브그래프가 사용하는 상태입니다.

```python
class PortfolioHolding(TypedDict):
    """포트폴리오 보유 종목"""
    stock_code: str
    stock_name: str
    weight: float  # 비중 (0.0 ~ 1.0)
    value: float   # 평가액

class PortfolioState(TypedDict, total=False):
    """Portfolio Agent 서브그래프 상태"""

    # LangGraph 표준
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 기본 정보
    portfolio_id: str
    user_id: str

    # === 현재 포트폴리오 ===

    portfolio_snapshot: Optional[dict]
    """현재 포트폴리오 스냅샷

    구조:
    {
        "total_value": 10000000,
        "holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.30, "value": 3000000},
            ...
        ],
        "cash": 2000000,
        "market_data": {
            "kospi": 2500,
            "kospi_change_rate": 0.02
        }
    }
    """

    # === Market Condition 분석 결과 ===

    market_condition: Optional[str]
    """시장 상황 (강세장/중립장/약세장)

    판단 기준 (KOSPI 변화율):
    - 강세장: +5% 이상
    - 중립장: -5% ~ +5%
    - 약세장: -5% 이하
    """

    max_slots: Optional[int]
    """최대 보유 종목 수

    시장 상황별 조정:
    - 강세장: 10개
    - 중립장: 7개
    - 약세장: 5개 (리스크 관리)
    """

    # === Optimization 결과 ===

    proposed_allocation: Optional[list[PortfolioHolding]]
    """제안된 포트폴리오 구성"""

    optimization_metrics: Optional[dict]
    """최적화 지표 (샤프 비율, 변동성 등)"""

    # === Constraint Validation ===

    max_sector_concentration: Optional[float]
    """섹터 집중도 제한 (기본 0.30 = 30%)"""

    max_same_industry_count: Optional[int]
    """동일 산업군 최대 종목 수 (기본 3개)"""

    constraint_violations: Optional[list[dict]]
    """제약 조건 위반 내역

    위반 유형:
    - max_slots: 최대 슬롯 수 초과 (severity: high)
    - sector_concentration: 섹터 집중도 초과 (severity: medium)
    - industry_count: 산업군 종목 수 초과 (severity: low)

    구조:
    {
        "type": "max_slots",
        "message": "최대 보유 종목 수(10개) 초과: 12개",
        "severity": "high",
        "current": 12,
        "limit": 10
    }
    """

    # === Rebalancing ===

    rebalancing_plan: Optional[dict]
    """리밸런싱 계획"""

    rebalance_prepared: bool
    """리밸런싱 준비 완료 여부"""

    rebalance_approved: bool
    """리밸런싱 승인 여부"""

    rebalance_executed: bool
    """리밸런싱 실행 완료 여부"""

    # 최종 결과
    final_portfolio: Optional[dict]
    """최종 포트폴리오 구성"""
```

---

## RiskState (Risk Agent)

Risk Agent 서브그래프가 사용하는 상태입니다.

```python
class RiskState(TypedDict, total=False):
    """Risk Agent 서브그래프 상태"""

    # LangGraph 표준
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 평가 대상
    portfolio: Optional[dict]
    """평가할 포트폴리오"""

    proposed_trade: Optional[dict]
    """평가할 거래 건"""

    # 리스크 평가 결과
    risk_level: Optional[str]
    """리스크 레벨 (low/medium/high/critical)"""

    risk_score: Optional[float]
    """리스크 점수 (0-100)"""

    concentration_risk: Optional[dict]
    """집중도 리스크"""

    volatility_risk: Optional[dict]
    """변동성 리스크"""

    sector_risk: Optional[dict]
    """섹터 리스크"""

    warnings: Optional[list[str]]
    """경고 메시지"""

    alternatives: Optional[list[dict]]
    """대안 제시"""

    requires_approval: bool
    """승인 필요 여부"""
```

---

## StrategyState (Strategy Agent)

Strategy Agent 서브그래프가 사용하는 상태입니다.

```python
class StrategyState(TypedDict, total=False):
    """Strategy Agent 서브그래프 상태"""

    # LangGraph 표준
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 사용자 정보
    user_profile: Optional[dict]
    """사용자 프로필 (투자 성향, 목표 등)"""

    # 전략 생성 결과
    strategy_type: Optional[str]
    """전략 유형 (성장형/안정형/배당형 등)"""

    recommended_stocks: Optional[list[dict]]
    """추천 종목 리스트"""

    target_allocation: Optional[dict]
    """목표 자산 배분"""

    investment_thesis: Optional[str]
    """투자 논리"""

    # HITL 상태
    strategy_prepared: bool
    strategy_approved: bool
    strategy_executed: bool
```

---

## State 필드 명명 규칙

### 진행 상태 플래그

HITL 개입이 있는 작업의 진행 상태는 다음 패턴을 따릅니다:

```python
{action}_prepared: bool   # 준비 완료
{action}_approved: bool   # 승인 완료
{action}_executed: bool   # 실행 완료
```

**예시:**
- `trade_prepared`, `trade_approved`, `trade_executed`
- `rebalance_prepared`, `rebalance_approved`, `rebalance_executed`
- `strategy_prepared`, `strategy_approved`, `strategy_executed`

### Optional 필드

모든 State는 `TypedDict(total=False)`로 정의되어 있어, 명시되지 않은 필드는 자동으로 Optional입니다.

---

## 버전 정보

- **버전**: 1.1
- **최종 업데이트**: 2025년 1월
- **변경 사항**:
  - Research Agent: Specialist Worker 분석 결과 필드 추가
  - Trading Agent: Buy/Sell Specialist, Risk/Reward Calculator 필드 추가
  - Portfolio Agent: Market Condition, Constraint Validation 필드 추가

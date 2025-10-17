# HAMA 에이전트 아키텍처 상세 설계

**작성일**: 2025-10-03
**목적**: Phase 2 실제 구현을 위한 각 에이전트의 역할, 구조, 서브에이전트 명세

---

## 📊 전체 아키텍처 개요

```
                    ┌──────────────────────┐
                    │   사용자 (Chat UI)   │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │   Master Agent       │
                    │  (LangGraph Router)  │
                    └──────────┬───────────┘
                               ↓
        ┌──────────────────────┼──────────────────────┐
        ↓                      ↓                      ↓
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Research      │     │ Strategy      │     │ Portfolio     │
│ Agent         │     │ Agent         │     │ Agent         │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        ↓                     ↓                     ↓
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Risk          │     │ Monitoring    │     │ Education     │
│ Agent         │     │ Agent         │     │ Agent         │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ↓
                   ┌────────────────────────┐
                   │ Data Collection Agent  │
                   │  + Service Layer       │
                   └────────────────────────┘
                              ↓
                   ┌────────────────────────┐
                   │ External Data Sources  │
                   │ - FinanceDataReader    │
                   │ - DART API             │
                   │ - News Crawler         │
                   └────────────────────────┘
```

---

## 🎯 1. Master Agent (graph_master.py)

### 역할 (Responsibilities)

```python
"""
Master Agent - 라우팅 및 오케스트레이션

핵심 역할:
1. 사용자 질의 의도 파악 (Intent Analysis)
2. 적절한 서브 에이전트 선택 및 순서 결정 (Routing)
3. 에이전트 간 데이터 전달 및 조율 (Orchestration)
4. HITL(Human-in-the-Loop) 트리거 판단
5. 여러 에이전트 결과 통합 (Aggregation)

의사결정:
- 어떤 에이전트를 호출할 것인가?
- 순차 실행인가, 병렬 실행인가?
- 사용자 개입이 필요한가?
- 결과를 어떻게 통합할 것인가?
"""
```

### 구조

**LangGraph StateGraph 기반**:
- 6개 노드로 구성
- AgentState로 상태 관리

### 노드 (Nodes)

#### 1. analyze_intent
```python
def analyze_intent_node(state: AgentState) -> AgentState:
    """
    의도 분석 노드

    입력: state["query"]
    출력: state["intent"]

    로직:
    - 키워드 기반 분류 (Phase 1)
    - LLM 기반 분류 (Phase 2)

    Intent 종류:
    - stock_analysis: 종목 분석
    - trade_execution: 매매 실행
    - portfolio_evaluation: 포트폴리오 평가
    - rebalancing: 리밸런싱
    - performance_check: 수익률 조회
    - market_status: 시장 상황
    - general_question: 일반 질문
    """
```

#### 2. determine_agents
```python
def determine_agents_node(state: AgentState) -> AgentState:
    """
    에이전트 결정 노드

    입력: state["intent"]
    출력: state["agents_to_call"]

    라우팅 맵:
    stock_analysis → [research, strategy, risk]
    trade_execution → [strategy, risk]
    rebalancing → [portfolio, strategy, risk]
    performance_check → [portfolio]
    market_status → [research, monitoring]
    general_question → [education]
    """
```

#### 3. call_agents
```python
async def call_agents_node(state: AgentState) -> AgentState:
    """
    에이전트 호출 노드

    입력: state["agents_to_call"]
    출력: state["agent_results"] (누적)

    로직:
    - asyncio.gather로 병렬 호출
    - 각 에이전트의 AgentOutput 수집
    - 실패 시 에러 핸들링
    """
```

#### 4. check_risk
```python
def check_risk_node(state: AgentState) -> AgentState:
    """
    리스크 체크 노드

    입력: state["agent_results"]["risk_agent"]
    출력: state["risk_level"]

    리스크 레벨:
    - low: 안전
    - medium: 주의
    - high: 경고 (HITL 트리거 가능)
    """
```

#### 5. check_hitl
```python
def check_hitl_node(state: AgentState) -> AgentState:
    """
    HITL 트리거 판단 노드

    입력:
    - state["intent"]
    - state["risk_level"]
    - state["automation_level"]

    출력: state["hitl_required"]

    트리거 조건:
    1. 매매 실행 (automation_level >= 2)
    2. 리밸런싱 (automation_level >= 1)
    3. 리스크 레벨 high
    4. Bull/Bear 의견 차이 < 10%
    """
```

#### 6. aggregate_results
```python
def aggregate_results_node(state: AgentState) -> AgentState:
    """
    결과 통합 노드

    입력: state["agent_results"]
    출력:
    - state["summary"]
    - state["final_response"]

    로직:
    - 각 에이전트 결과를 하나의 응답으로 통합
    - HITL 필요 시 approval_request 생성
    """
```

### Phase 2 개선 사항

```python
# TODO Phase 2:
# - [ ] LLM 기반 의도 분석 (현재는 키워드 매칭)
# - [ ] 동적 라우팅 (사용자 히스토리 기반)
# - [ ] 에이전트 실패 시 재시도 전략
# - [ ] 부분 실패 처리 (일부 에이전트만 성공)
```

---

## 🔍 2. Research Agent (research.py)

### 역할 (Responsibilities)

```python
"""
Research Agent - 기업 분석 및 데이터 수집

핵심 역할:
1. 기업 재무 분석 (재무제표, 비율 분석)
2. 기술적 분석 (차트, 지표)
3. 뉴스 및 공시 분석 (감정 분석 포함)
4. 종합 평가 및 등급 산출

데이터 소스:
- FinanceDataReader (주가 데이터)
- DART API (재무제표, 공시)
- 네이버 금융 (뉴스)

출력:
- 기업 평가 (rating 1-5)
- 추천 의견 (BUY/HOLD/SELL)
- 목표 가격
- 분석 근거
"""
```

### 서브 에이전트 (Sub-Agents)

#### 2-1. Financial Analysis Sub-Agent
```python
class FinancialAnalysisSubAgent:
    """
    재무 분석 서브에이전트

    역할:
    - 재무제표 분석 (손익계산서, 재무상태표, 현금흐름표)
    - 재무비율 계산 (PER, PBR, ROE, ROA, 부채비율 등)
    - 성장성 분석 (매출 성장률, 이익 성장률)
    - 수익성 분석 (영업이익률, 순이익률)
    - 안정성 분석 (유동비율, 당좌비율)

    입력:
    - corp_code (기업 코드)
    - fiscal_year (회계연도)

    출력:
    - financial_ratios: Dict[str, float]
    - growth_metrics: Dict[str, float]
    - profitability: Dict[str, float]
    - stability: Dict[str, float]

    TODO Phase 2:
    - [ ] DART API 연동 (재무제표 조회)
    - [ ] 재무비율 자동 계산
    - [ ] 업종 평균 대비 비교
    - [ ] 시계열 추세 분석 (3년치)
    """
```

#### 2-2. Technical Analysis Sub-Agent
```python
class TechnicalAnalysisSubAgent:
    """
    기술적 분석 서브에이전트

    역할:
    - 기술적 지표 계산 (RSI, MACD, Bollinger Bands, 이동평균선)
    - 추세 분석 (상승/하락/횡보)
    - 지지/저항선 식별
    - 매매 시그널 생성

    입력:
    - stock_code
    - period (분석 기간, 기본 90일)

    출력:
    - trend: str ("upward", "downward", "sideways")
    - indicators: Dict (RSI, MACD, etc.)
    - support_level: Decimal
    - resistance_level: Decimal
    - signals: List[str]

    TODO Phase 2:
    - [ ] FinanceDataReader로 주가 데이터 수집
    - [ ] TA-Lib 연동 (기술적 지표)
    - [ ] 패턴 인식 (Head & Shoulders, Double Top 등)
    - [ ] 볼륨 분석
    """
```

#### 2-3. News & Sentiment Analysis Sub-Agent
```python
class NewsSentimentSubAgent:
    """
    뉴스 및 감정 분석 서브에이전트

    역할:
    - 뉴스 크롤링 (네이버 금융, 증권 뉴스)
    - 감정 분석 (긍정/부정/중립)
    - 공시 요약 (중요 공시 추출)
    - 이슈 감지 (급등/급락 원인)

    입력:
    - stock_code
    - days (최근 N일, 기본 7일)

    출력:
    - news: List[NewsItem]
        - title, url, published_at, source
        - sentiment: str ("positive", "negative", "neutral")
        - importance: str ("high", "medium", "low")
    - overall_sentiment_score: float (-1.0 ~ 1.0)
    - key_events: List[str]

    TODO Phase 2:
    - [ ] 네이버 금융 크롤링 (BeautifulSoup)
    - [ ] LLM 기반 감정 분석
    - [ ] DART 공시 요약 (RAG 활용)
    - [ ] 중요도 자동 판단
    """
```

### 통합 프로세스 (Main Process)

```python
class ResearchAgent(BaseAgent):
    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        메인 리서치 프로세스

        1. 데이터 수집 (Data Collection Agent 호출)
        2. 서브 에이전트 병렬 실행
           - Financial Analysis
           - Technical Analysis
           - News Sentiment Analysis
        3. 결과 통합
        4. 종합 평가 (LLM)

        TODO Phase 2:
        - [ ] 3개 서브에이전트 구현
        - [ ] LLM 기반 종합 평가
        - [ ] 목표 가격 산정 로직
        - [ ] 평가 근거 생성
        """
```

---

## 💡 3. Strategy Agent (strategy.py)

### 역할 (Responsibilities)

```python
"""
Strategy Agent - 투자 전략 및 매매 시그널

핵심 역할:
1. Bull/Bear 분석 (상승/하락 근거)
2. Consensus 계산 (의견 종합)
3. 매매 시그널 생성 (BUY/SELL/HOLD)
4. 타이밍 전략 (진입/청산 시점)
5. 리스크/리워드 비율 계산

의사결정:
- 지금 매수해야 하는가?
- 목표 가격은?
- 손절가는?
- Bull과 Bear 중 누가 맞는가?
"""
```

### 서브 에이전트 (Sub-Agents)

#### 3-1. Bull Analyst Sub-Agent
```python
class BullAnalystSubAgent:
    """
    Bull 분석가 서브에이전트

    역할:
    - 상승 근거 분석
    - 긍정적 요인 식별
    - 상승 시나리오 생성
    - 기대 수익률 계산

    입력:
    - stock_code
    - research_result (Research Agent 결과)

    출력:
    - confidence: Decimal (0.0 ~ 1.0)
    - arguments: List[str] (상승 근거)
    - expected_return: Decimal (기대 수익률)
    - key_catalysts: List[str] (주요 상승 촉매)

    분석 요소:
    - 실적 개선
    - 업황 호전
    - 신제품/신사업
    - 밸류에이션 매력
    - 기술적 돌파

    TODO Phase 2:
    - [ ] LLM 기반 상승 근거 생성
    - [ ] Research Agent 결과 활용
    - [ ] 신뢰도 점수 계산 로직
    """
```

#### 3-2. Bear Analyst Sub-Agent
```python
class BearAnalystSubAgent:
    """
    Bear 분석가 서브에이전트

    역할:
    - 하락 근거 분석
    - 부정적 요인 식별
    - 하락 시나리오 생성
    - 예상 손실 계산

    입력:
    - stock_code
    - research_result

    출력:
    - confidence: Decimal (0.0 ~ 1.0)
    - arguments: List[str] (하락 근거)
    - expected_loss: Decimal (예상 손실률)
    - risk_factors: List[str] (주요 리스크)

    분석 요소:
    - 실적 악화
    - 업황 둔화
    - 경쟁 심화
    - 밸류에이션 부담
    - 기술적 약세

    TODO Phase 2:
    - [ ] LLM 기반 하락 근거 생성
    - [ ] Research Agent 결과 활용
    - [ ] 리스크 요인 자동 식별
    """
```

#### 3-3. Consensus Calculator Sub-Agent
```python
class ConsensusCalculatorSubAgent:
    """
    Consensus 계산 서브에이전트

    역할:
    - Bull/Bear 의견 종합
    - 최종 매매 시그널 생성
    - 신뢰도 계산
    - HITL 트리거 판단 (의견 차이 작을 때)

    입력:
    - bull_result
    - bear_result

    출력:
    - consensus: str ("bullish", "bearish", "neutral")
    - consensus_strength: str ("strong", "moderate", "weak")
    - final_signal: str ("BUY", "SELL", "HOLD")
    - confidence_score: Decimal
    - should_trigger_hitl: bool (의견 차이 < 10%p)

    로직:
    - Bull confidence > Bear confidence + 0.15 → BUY
    - Bear confidence > Bull confidence + 0.15 → SELL
    - 차이 < 0.15 → HOLD 또는 HITL

    TODO Phase 2:
    - [ ] Consensus 계산 알고리즘
    - [ ] HITL 트리거 조건 구현
    - [ ] 신뢰도 점수 계산
    """
```

### 통합 프로세스

```python
class StrategyAgent(BaseAgent):
    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        메인 전략 프로세스

        1. Research Agent 결과 가져오기
        2. Bull/Bear 서브에이전트 병렬 실행
        3. Consensus 계산
        4. 매매 시그널 및 타이밍 전략 생성
        5. HITL 필요 시 트리거

        TODO Phase 2:
        - [ ] 3개 서브에이전트 구현
        - [ ] 목표가/손절가 계산 로직
        - [ ] 타이밍 전략 (진입 전략)
        - [ ] LLM 프롬프트 엔지니어링
        """
```

---

## ⚠️ 4. Risk Agent (risk.py)

### 역할 (Responsibilities)

```python
"""
Risk Agent - 리스크 평가 및 경고

핵심 역할:
1. 포트폴리오 리스크 측정 (VaR, 변동성)
2. 집중도 리스크 분석 (종목/섹터 비중)
3. 손실 시뮬레이션 (Monte Carlo)
4. 리스크 임계값 체크
5. 경고 메시지 생성

HITL 트리거 조건:
- 개별 종목 비중 > 20%
- 섹터 비중 > 40%
- 예상 VaR > 목표 손실률
- 급격한 포트폴리오 변경 (30% 이상)
"""
```

### 서브 에이전트 없음 (단일 에이전트)

### 주요 기능

#### 4-1. VaR (Value at Risk) 계산
```python
async def calculate_var(self, portfolio, confidence=0.95):
    """
    VaR 계산

    방법:
    - Historical VaR (과거 데이터 기반)
    - Parametric VaR (정규분포 가정)

    입력:
    - portfolio: 포트폴리오 구성
    - confidence: 신뢰 수준 (95% 또는 99%)

    출력:
    - var_95: 95% 신뢰수준 VaR
    - var_99: 99% 신뢰수준 VaR

    TODO Phase 2:
    - [ ] Historical VaR 구현
    - [ ] numpy/scipy 활용
    - [ ] 포트폴리오 상관관계 고려
    """
```

#### 4-2. 집중도 리스크 분석
```python
async def analyze_concentration_risk(self, portfolio):
    """
    집중도 리스크 분석

    체크 항목:
    - 개별 종목 비중
    - 섹터 비중
    - HHI (Herfindahl-Hirschman Index)

    임계값:
    - 개별 종목 > 20%: 경고
    - 섹터 비중 > 40%: 경고
    - HHI > 0.2: 고집중

    TODO Phase 2:
    - [ ] HHI 계산
    - [ ] 섹터 분류 (GICS)
    - [ ] 동적 임계값 (사용자 설정)
    """
```

#### 4-3. Monte Carlo 시뮬레이션
```python
async def run_monte_carlo(self, portfolio, iterations=10000):
    """
    Monte Carlo 시뮬레이션

    목적:
    - 예상 손실/수익 분포 계산
    - 최악의 시나리오 분석
    - 확률적 리스크 평가

    입력:
    - portfolio
    - iterations (시뮬레이션 횟수)

    출력:
    - expected_return: 기대 수익률
    - worst_case: 최악의 시나리오 (1% 백분위수)
    - best_case: 최상의 시나리오 (99% 백분위수)

    TODO Phase 2:
    - [ ] GBM (Geometric Brownian Motion) 모델
    - [ ] numpy random 활용
    - [ ] 상관관계 고려
    """
```

---

## 📁 5. Portfolio Agent (portfolio.py)

### 역할 (Responsibilities)

```python
"""
Portfolio Agent - 포트폴리오 구성 및 최적화

핵심 역할:
1. 자산 배분 최적화 (Mean-Variance, Black-Litterman)
2. 리밸런싱 제안 (현재 vs 목표 비교)
3. 거래 계획 생성 (매수/매도 주문)
4. 성과 측정 (샤프 비율, 알파, 베타)
5. 포트폴리오 시뮬레이션

의사결정:
- 최적의 자산 배분은?
- 리밸런싱이 필요한가?
- 어떤 종목을 얼마나 사고 팔아야 하는가?
"""
```

### 서브 에이전트 (Sub-Agents)

#### 5-1. Portfolio Optimizer Sub-Agent
```python
class PortfolioOptimizerSubAgent:
    """
    포트폴리오 최적화 서브에이전트

    역할:
    - Mean-Variance 최적화
    - 샤프 비율 최대화
    - 제약 조건 적용 (최대 비중, 섹터 제한 등)

    입력:
    - candidate_stocks: List[str] (후보 종목)
    - constraints: Dict (제약 조건)
    - objective: str ("max_sharpe", "min_volatility")

    출력:
    - optimal_weights: Dict[str, Decimal] (종목별 비중)
    - expected_return: Decimal
    - expected_volatility: Decimal
    - sharpe_ratio: Decimal

    알고리즘:
    - Markowitz Mean-Variance
    - cvxpy 또는 scipy.optimize 사용

    TODO Phase 2:
    - [ ] Mean-Variance 최적화 구현
    - [ ] 제약 조건 처리 (최소/최대 비중)
    - [ ] Black-Litterman 모델 (선택)
    """
```

#### 5-2. Rebalancing Calculator Sub-Agent
```python
class RebalancingCalculatorSubAgent:
    """
    리밸런싱 계산 서브에이전트

    역할:
    - 현재 vs 목표 비중 비교
    - 필요한 거래 계산
    - 거래 비용 고려
    - 세금 최적화 (선택)

    입력:
    - current_portfolio
    - target_portfolio
    - total_value

    출력:
    - trades_required: List[Trade]
        - action: "BUY" | "SELL"
        - stock_code
        - amount (금액)
        - quantity (수량)
    - estimated_cost: Decimal (거래 비용)
    - tax_impact: Decimal (세금 영향, 선택)

    로직:
    - 비중 차이 계산
    - 매도 우선 → 매수 실행
    - 최소 거래 단위 고려

    TODO Phase 2:
    - [ ] 리밸런싱 알고리즘
    - [ ] 거래 비용 계산
    - [ ] 최소 거래 금액 필터링
    """
```

### 통합 프로세스

```python
class PortfolioAgent(BaseAgent):
    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        메인 포트폴리오 프로세스

        1. 현재 포트폴리오 조회 (DB)
        2. 최적 포트폴리오 계산 (Optimizer)
        3. 리밸런싱 필요성 판단
        4. 거래 계획 생성 (Rebalancing Calculator)
        5. 성과 측정 (알파, 베타, 샤프 비율)

        TODO Phase 2:
        - [ ] 2개 서브에이전트 구현
        - [ ] DB 연동 (현재 포트폴리오 조회)
        - [ ] 성과 측정 로직
        """
```

---

## 📡 6. Monitoring Agent (monitoring.py)

### 역할 (Responsibilities)

```python
"""
Monitoring Agent - 시장 및 포트폴리오 모니터링

핵심 역할:
1. 가격 변동 추적 (급등/급락 감지)
2. 이벤트 감지 (거래량 급증, VI 발동 등)
3. 공시 모니터링 (중요 공시 알림)
4. 뉴스 모니터링 (종목 관련 뉴스)
5. 정기 리포트 생성

작동 방식:
- 명시적 요청: 사용자가 "삼성전자 이슈는?" 질문
- 주기적: 일일/주간/월간 리포트
- 트리거: 가격 변동 > ±10%, 중요 공시 등

TODO Phase 2 후반:
- [ ] 실시간 가격 추적
- [ ] 이벤트 감지 로직
- [ ] 알림 시스템 (Email, Push)
"""
```

### 서브 에이전트 없음 (단일 에이전트)

---

## 📚 7. Education Agent (education.py)

### 역할 (Responsibilities)

```python
"""
Education Agent - 투자 교육 및 질의응답

핵심 역할:
1. 투자 용어 설명
2. 일반 시장 질문 답변
3. 투자 전략 교육
4. 맥락에 맞는 콘텐츠 추천

특징:
- HITL 트리거 없음 (완전 자동)
- LLM 기반 응답
- RAG 활용 (투자 용어 DB)

TODO Phase 2 후반:
- [ ] 투자 용어 사전 DB 구축
- [ ] RAG 기반 Q&A
- [ ] LLM 프롬프트 최적화
"""
```

### 서브 에이전트 없음 (단일 에이전트)

---

## 👤 8. Personalization Agent (personalization.py)

### 역할 (Responsibilities)

```python
"""
Personalization Agent - 사용자 프로필 및 선호도 관리

핵심 역할:
1. 사용자 프로필 CRUD
2. 투자 성향 관리 (리스크 허용도, 목표 등)
3. 선호/회피 종목/섹터 관리
4. 자동화 레벨 조정

Phase 2 추가:
5. 사용자 행동 학습 (승인/거부 패턴)
6. 개인화 추천
7. 맞춤형 알림 설정

TODO Phase 2 중반:
- [ ] 사용자 프로필 CRUD API
- [ ] DB 스키마 연동 (users 테이블)
- [ ] 투자 성향 진단 로직
"""
```

### 서브 에이전트 없음 (단일 에이전트)

---

## 🗂️ 9. Data Collection Agent (data_collection.py) ⭐ 핵심

### 역할 (Responsibilities)

```python
"""
Data Collection Agent - 중앙화된 데이터 수집

핵심 역할:
1. 모든 외부 데이터 소스 통합 관리
2. 데이터 캐싱 (Redis)
3. API 레이트 리밋 관리
4. 에러 핸들링 및 재시도

데이터 타입:
- stock_price: 주가 데이터 (FinanceDataReader)
- financial_statement: 재무제표 (DART API)
- dart_disclosure: 공시 문서 (DART API)
- news: 뉴스 (크롤링)
- realtime_quote: 실시간 호가 (KIS API, Phase 3)

중요성:
- 다른 모든 에이전트가 의존
- 캐싱으로 성능 최적화
- API 호출 중복 방지
"""
```

### Service Layer 의존

```python
class DataCollectionAgent(BaseAgent):
    """
    Service Layer를 사용하여 데이터 수집

    의존성:
    - StockDataService (FinanceDataReader)
    - DARTService (DART API)
    - NewsCrawlerService (네이버 금융)
    - CacheManager (Redis)

    TODO Phase 2 (최우선):
    - [ ] 3개 Service 구현
    - [ ] Redis 캐싱 통합
    - [ ] 에러 핸들링 (재시도 로직)
    - [ ] 데이터 정규화
    """
```

---

## 📊 에이전트 간 의존성 맵

```
Master Agent
    ├─ Research Agent
    │   └─ Data Collection Agent
    │       └─ Service Layer
    │           ├─ FinanceDataReader
    │           ├─ DART API
    │           └─ News Crawler
    │
    ├─ Strategy Agent
    │   └─ Research Agent (결과 활용)
    │
    ├─ Risk Agent
    │   └─ Portfolio Agent (포트폴리오 정보)
    │
    ├─ Portfolio Agent
    │   └─ Data Collection Agent
    │
    ├─ Monitoring Agent
    │   └─ Data Collection Agent
    │
    ├─ Education Agent
    │   └─ (독립적, 외부 의존 없음)
    │
    └─ Personalization Agent
        └─ DB만 의존
```

---

## 🚀 Phase 2 구현 우선순위

```
Week 11-12: Service Layer + Cache
    ├─ StockDataService (FinanceDataReader)
    ├─ DARTService (DART API)
    ├─ NewsCrawlerService
    └─ CacheManager (Redis)

Week 13: Data Collection Agent
    └─ 실제 구현 (Service Layer 통합)

Week 14-16: Research Agent
    ├─ Financial Analysis Sub-Agent
    ├─ Technical Analysis Sub-Agent
    └─ News Sentiment Sub-Agent

Week 17-19: Strategy Agent
    ├─ Bull Analyst Sub-Agent
    ├─ Bear Analyst Sub-Agent
    └─ Consensus Calculator Sub-Agent

Week 20-22: Portfolio Agent
    ├─ Portfolio Optimizer Sub-Agent
    └─ Rebalancing Calculator Sub-Agent

Week 23-24: Risk Agent
    ├─ VaR 계산
    ├─ 집중도 리스크
    └─ Monte Carlo 시뮬레이션

Week 25-26: Monitoring, Education, Personalization
```

---

**작성자**: Claude Code
**최종 업데이트**: 2025-10-03
**다음 단계**: Phase 1 완료 → Service Layer 구축 시작
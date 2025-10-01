# 에이전트 구현 상세 가이드

**버전**: 1.0
**작성일**: 2025-10-01
**기반 문서**: 에이전트 아키텍쳐 v2.0

---

## 목차

1. [공통 인터페이스](#공통-인터페이스)
2. [마스터 에이전트](#1-마스터-에이전트)
3. [개인화 에이전트](#2-개인화-에이전트)
4. [데이터 수집 에이전트](#3-데이터-수집-에이전트)
5. [리서치 에이전트](#4-리서치-에이전트)
6. [전략 에이전트](#5-전략-에이전트)
7. [포트폴리오 에이전트](#6-포트폴리오-에이전트)
8. [리스크 에이전트](#7-리스크-에이전트)
9. [모니터링 에이전트](#8-모니터링-에이전트)
10. [교육/질의 에이전트](#9-교육질의-에이전트)

---

## 공통 인터페이스

### 에이전트 기본 구조

모든 에이전트는 동일한 인터페이스를 따릅니다.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime

@dataclass
class AgentInput:
    """에이전트 입력 표준 포맷"""
    request_id: str
    user_id: str
    automation_level: int  # 1-3
    data: Dict[str, Any]
    metadata: Optional[Dict] = None

@dataclass
class AgentOutput:
    """에이전트 출력 표준 포맷"""
    request_id: str
    agent_id: str
    status: str  # "success", "error", "hitl_required"
    data: Dict[str, Any]
    hitl_trigger: Optional[Dict] = None
    metadata: Optional[Dict] = None
    timestamp: datetime = datetime.now()

class AgentInterface(ABC):
    """모든 에이전트가 구현해야 하는 인터페이스"""

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """에이전트 고유 ID"""
        pass

    @abstractmethod
    async def process(self, input: AgentInput) -> AgentOutput:
        """메인 처리 로직"""
        pass

    @abstractmethod
    async def validate(self, input: AgentInput) -> bool:
        """입력 검증"""
        pass

    def _create_output(
        self,
        request_id: str,
        status: str,
        data: Dict,
        hitl_trigger: Optional[Dict] = None
    ) -> AgentOutput:
        """표준 출력 생성 헬퍼"""
        return AgentOutput(
            request_id=request_id,
            agent_id=self.agent_id,
            status=status,
            data=data,
            hitl_trigger=hitl_trigger
        )
```

---

## 1. 마스터 에이전트

### 역할

- 사용자 질의 의도 분석
- 적절한 에이전트(들) 호출 및 라우팅
- 여러 에이전트 결과 통합
- HITL 개입 시점 판단

### 구현 단계

#### Phase 1: Mock 버전

```python
class MasterAgent(AgentInterface):
    """마스터 에이전트 - Mock 버전"""

    @property
    def agent_id(self) -> str:
        return "master_agent"

    def __init__(self):
        # 나중에 실제 에이전트로 교체
        self.agents = {
            "personalization": None,
            "data_collection": None,
            "research": None,
            "strategy": None,
            "portfolio": None,
            "risk": None,
            "monitoring": None,
            "education": None
        }

    async def process(self, input: AgentInput) -> AgentOutput:
        # 1. 의도 분석
        intent = await self._classify_intent(input.data['query'])

        # 2. Mock 응답 생성
        response = await self._generate_mock_response(intent, input)

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=response
        )

    async def _classify_intent(self, query: str) -> str:
        """의도 분석 - 간단한 키워드 매칭"""
        # TODO: LLM 기반 의도 분석으로 교체

        query_lower = query.lower()

        if any(kw in query_lower for kw in ['분석', '어때', '평가']):
            return "stock_analysis"
        elif any(kw in query_lower for kw in ['매수', '매도', '사', '팔']):
            return "trade_execution"
        elif any(kw in query_lower for kw in ['포트폴리오', '수익률', '현황']):
            return "portfolio_review"
        elif any(kw in query_lower for kw in ['리밸런싱', '재조정']):
            return "rebalancing"
        elif any(kw in query_lower for kw in ['시장', '경제', '증시']):
            return "market_status"
        else:
            return "general_question"

    async def _generate_mock_response(self, intent: str, input: AgentInput) -> Dict:
        """Mock 응답 생성"""
        # TODO: 실제 에이전트 호출로 교체

        mock_responses = {
            "stock_analysis": {
                "intent": "stock_analysis",
                "answer": "📊 삼성전자 분석 결과 (Mock)\n\n"
                         "**기업 평가**: ⭐⭐⭐⭐ (4/5)\n"
                         "**매매 의견**: HOLD\n"
                         "**리스크**: 중간"
            },
            "trade_execution": {
                "intent": "trade_execution",
                "answer": "⚠️ 매매 실행 전 확인이 필요합니다 (Mock)",
                "hitl_required": True
            },
            "portfolio_review": {
                "intent": "portfolio_review",
                "answer": "📊 포트폴리오 현황 (Mock)\n\n"
                         "총 자산: 10,000,000원\n"
                         "수익률: +5.2%"
            }
        }

        return mock_responses.get(intent, {"answer": "이해하지 못했습니다."})
```

#### Phase 2: 실제 구현

```python
class MasterAgent(AgentInterface):
    """마스터 에이전트 - 실제 구현"""

    def __init__(
        self,
        personalization_agent,
        data_collection_agent,
        research_agent,
        strategy_agent,
        portfolio_agent,
        risk_agent,
        monitoring_agent,
        education_agent,
        llm_client  # OpenAI or Claude
    ):
        self.agents = {
            "personalization": personalization_agent,
            "data_collection": data_collection_agent,
            "research": research_agent,
            "strategy": strategy_agent,
            "portfolio": portfolio_agent,
            "risk": risk_agent,
            "monitoring": monitoring_agent,
            "education": education_agent
        }
        self.llm = llm_client
        self.routing_map = self._init_routing_map()

    def _init_routing_map(self) -> Dict[str, List[str]]:
        """Intent → Agent 매핑"""
        return {
            "stock_analysis": ["data_collection", "research", "strategy"],
            "trade_execution": ["strategy", "risk", "portfolio"],
            "portfolio_review": ["portfolio", "risk"],
            "rebalancing": ["portfolio", "strategy", "risk"],
            "market_status": ["data_collection", "monitoring"],
            "general_question": ["education"]
        }

    async def _classify_intent(self, query: str) -> str:
        """LLM 기반 의도 분석"""
        prompt = f"""
        다음 사용자 질의의 의도를 분류하세요.

        질의: {query}

        가능한 의도:
        - stock_analysis: 종목 분석/평가
        - trade_execution: 매매 지시
        - portfolio_review: 포트폴리오 평가
        - rebalancing: 리밸런싱
        - market_status: 시장 상황
        - general_question: 일반 질문

        의도:
        """

        response = await self.llm.complete(prompt)
        return response.strip()

    async def process(self, input: AgentInput) -> AgentOutput:
        # 1. 의도 분석
        intent = await self._classify_intent(input.data['query'])

        # 2. 사용자 프로필 로드
        user_profile = await self.agents["personalization"].process(
            AgentInput(
                request_id=input.request_id,
                user_id=input.user_id,
                automation_level=input.automation_level,
                data={"action": "get_profile"}
            )
        )

        # 3. 필요한 에이전트들 병렬 호출
        agent_ids = self.routing_map.get(intent, [])
        tasks = [
            self.agents[agent_id].process(input)
            for agent_id in agent_ids
        ]

        results = await asyncio.gather(*tasks)

        # 4. 결과 통합
        integrated_result = await self._integrate_results(
            intent, results, user_profile.data
        )

        # 5. HITL 필요 여부 판단
        hitl_trigger = await self._check_hitl(
            intent,
            integrated_result,
            input.automation_level
        )

        return self._create_output(
            request_id=input.request_id,
            status="hitl_required" if hitl_trigger else "success",
            data=integrated_result,
            hitl_trigger=hitl_trigger
        )

    async def _check_hitl(
        self,
        intent: str,
        result: Dict,
        automation_level: int
    ) -> Optional[Dict]:
        """HITL 개입 필요 여부 판단"""

        # 매매 실행은 항상 HITL (레벨 2, 3)
        if intent == "trade_execution" and automation_level >= 2:
            return {
                "reason": "매매 실행에는 승인이 필요합니다",
                "urgency": "high",
                "options": ["취소", "수정", "진행"]
            }

        # 리스크 경고 발생 시
        if result.get("risk_warning"):
            return {
                "reason": result["risk_warning"]["message"],
                "urgency": "high",
                "options": ["취소", "수정", "진행"]
            }

        return None
```

### 체크리스트

**Mock 구현** (2주):
- [ ] 기본 인터페이스 구현
- [ ] 키워드 기반 의도 분석
- [ ] Mock 응답 생성
- [ ] 라우팅 맵 정의

**실제 구현** (추가 1주):
- [ ] LLM 기반 의도 분석
- [ ] 실제 에이전트 통합
- [ ] 병렬 처리
- [ ] 결과 통합 로직
- [ ] HITL 트리거 로직

---

## 2. 개인화 에이전트

### 역할

- 사용자 프로필 관리
- 투자 성향 추적
- 자동화 레벨 관리

### 데이터 스키마

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserProfile:
    user_id: str
    risk_tolerance: str  # "aggressive", "moderate", "conservative"
    investment_goal: str  # "growth", "income", "balanced"
    investment_horizon: str  # "short", "medium", "long"
    automation_level: int  # 1-3
    preferred_sectors: List[str]
    avoided_stocks: List[str]
    created_at: datetime
    updated_at: datetime
```

### Mock 구현

```python
class PersonalizationAgent(AgentInterface):
    """개인화 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "personalization_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        # TODO: 실제 DB 연동

        mock_profile = UserProfile(
            user_id=input.user_id,
            risk_tolerance="moderate",
            investment_goal="growth",
            investment_horizon="long",
            automation_level=input.automation_level,
            preferred_sectors=["IT", "반도체"],
            avoided_stocks=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data={"profile": mock_profile.__dict__}
        )
```

### 실제 구현

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

class PersonalizationAgent(AgentInterface):
    """개인화 에이전트 - 실제 구현"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def process(self, input: AgentInput) -> AgentOutput:
        action = input.data.get("action", "get_profile")

        if action == "get_profile":
            profile = await self._get_profile(input.user_id)
        elif action == "update_profile":
            profile = await self._update_profile(
                input.user_id,
                input.data["updates"]
            )
        else:
            profile = None

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data={"profile": profile}
        )

    async def _get_profile(self, user_id: str) -> Dict:
        """프로필 조회"""
        stmt = select(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        return profile.to_dict() if profile else self._default_profile(user_id)

    async def _update_profile(self, user_id: str, updates: Dict) -> Dict:
        """프로필 업데이트"""
        stmt = update(UserProfileModel).where(
            UserProfileModel.user_id == user_id
        ).values(**updates, updated_at=datetime.now())

        await self.db.execute(stmt)
        await self.db.commit()

        return await self._get_profile(user_id)
```

### 체크리스트

**Mock 구현** (1일):
- [ ] 기본 인터페이스
- [ ] Mock 프로필 반환

**실제 구현** (1주):
- [ ] DB 모델 정의
- [ ] CRUD 구현
- [ ] 초기 설문 처리
- [ ] 프로필 업데이트

---

## 3. 데이터 수집 에이전트

### 역할

- 멀티소스 데이터 수집 조율
- 캐싱 및 레이트 리밋 관리

**상세 내용은 [데이터 소스 통합 가이드](./data-sources-integration.md) 참조**

### Mock 구현

```python
class DataCollectionAgent(AgentInterface):
    """데이터 수집 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "data_collection_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        ticker = input.data.get("ticker")

        # TODO: 실제 API 연동
        mock_data = {
            "ticker": ticker,
            "price": {
                "current": 74500,
                "change": 500,
                "change_percent": 0.68
            },
            "financials": {
                "revenue": 302231158000000,
                "net_income": 26950784000000
            },
            "news": [
                {"title": "삼성전자, 실적 호조", "date": "2024-10-01"}
            ]
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=mock_data
        )
```

### 체크리스트

**Mock 구현** (1일):
- [ ] 기본 인터페이스
- [ ] Mock 데이터 반환

**실제 구현** (1-2주):
- [ ] pykrx 연동
- [ ] DART API 연동
- [ ] 한국투자증권 API 연동 (선택)
- [ ] 캐싱 전략
- [ ] 레이트 리밋

---

## 4. 리서치 에이전트

### 역할

- 기업 재무제표 분석
- 기술적 지표 계산
- 산업/경쟁사 비교

### Mock 구현

```python
class ResearchAgent(AgentInterface):
    """리서치 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "research_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        ticker = input.data.get("ticker")

        # TODO: 실제 분석 로직
        mock_analysis = {
            "ticker": ticker,
            "company_name": "삼성전자",
            "rating": 4,  # 1-5
            "profitability": {
                "roe": 0.0857,
                "roa": 0.0543,
                "net_margin": 0.0892
            },
            "growth": {
                "revenue_growth": 0.101,
                "profit_growth": 0.152
            },
            "stability": {
                "debt_ratio": 0.35,
                "current_ratio": 1.8
            },
            "technical": {
                "ma20": 74200,
                "ma60": 73500,
                "rsi": 58.3
            },
            "summary": "실적 양호, 기술적으로 중립"
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=mock_analysis
        )
```

### 실제 구현

```python
class ResearchAgent(AgentInterface):
    """리서치 에이전트 - 실제 구현"""

    def __init__(self, data_collector: DataCollectionAgent):
        self.data_collector = data_collector

    async def process(self, input: AgentInput) -> AgentOutput:
        ticker = input.data.get("ticker")

        # 1. 데이터 수집
        data = await self.data_collector.process(
            AgentInput(
                request_id=input.request_id,
                user_id=input.user_id,
                automation_level=input.automation_level,
                data={"ticker": ticker}
            )
        )

        # 2. 재무 분석
        profitability = self._analyze_profitability(
            data.data['financials']
        )

        # 3. 성장성 분석
        growth = self._analyze_growth(ticker)

        # 4. 안정성 분석
        stability = self._analyze_stability(
            data.data['financials']
        )

        # 5. 기술적 분석
        technical = self._analyze_technical(ticker)

        # 6. 종합 평가
        rating = self._calculate_rating(
            profitability, growth, stability, technical
        )

        analysis = {
            "ticker": ticker,
            "rating": rating,
            "profitability": profitability,
            "growth": growth,
            "stability": stability,
            "technical": technical,
            "summary": self._generate_summary(rating, profitability, technical)
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=analysis
        )

    def _analyze_profitability(self, financials: Dict) -> Dict:
        """수익성 분석"""
        roe = financials['net_income'] / financials['equity']
        roa = financials['net_income'] / financials['total_assets']
        net_margin = financials['net_income'] / financials['revenue']

        return {
            "roe": round(roe, 4),
            "roa": round(roa, 4),
            "net_margin": round(net_margin, 4)
        }

    def _analyze_technical(self, ticker: str) -> Dict:
        """기술적 분석"""
        from pykrx import stock
        today = pd.Timestamp.now().strftime("%Y%m%d")
        start = (pd.Timestamp.now() - pd.Timedelta(days=120)).strftime("%Y%m%d")

        df = stock.get_market_ohlcv(start, today, ticker)

        # 이동평균
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['MA60'] = df['종가'].rolling(window=60).mean()

        # RSI
        delta = df['종가'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        latest = df.iloc[-1]
        return {
            "current_price": latest['종가'],
            "ma20": latest['MA20'],
            "ma60": latest['MA60'],
            "rsi": rsi.iloc[-1]
        }
```

### 체크리스트

**Mock 구현** (1일):
- [ ] 기본 분석 구조
- [ ] Mock 분석 결과

**실제 구현** (2주):
- [ ] 재무 분석 로직
- [ ] 기술적 지표 (TA-Lib 활용)
- [ ] 산업 분석
- [ ] 평가 시스템

---

## 5. 전략 에이전트

### 역할

- 매수/매도 시그널 생성
- Bull/Bear 분석
- 종목 추천

### Mock 구현

```python
class StrategyAgent(AgentInterface):
    """전략 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "strategy_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        ticker = input.data.get("ticker")

        # TODO: Bull/Bear 서브에이전트 구현
        mock_signal = {
            "ticker": ticker,
            "action": "BUY",
            "confidence": 0.75,
            "price_target": 78000,
            "bull_case": {
                "confidence": 0.78,
                "reasoning": "반도체 업황 개선 조짐, 실적 성장 예상"
            },
            "bear_case": {
                "confidence": 0.22,
                "reasoning": "글로벌 경기 둔화 우려"
            },
            "consensus": "BUY",
            "reasoning": "Bull 의견이 우세, 기술적으로 지지선 확인"
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=mock_signal
        )
```

### 실제 구현

```python
class StrategyAgent(AgentInterface):
    """전략 에이전트 - 실제 구현"""

    def __init__(
        self,
        research_agent: ResearchAgent,
        bull_analyst,  # 서브에이전트
        bear_analyst,  # 서브에이전트
        llm_client
    ):
        self.research = research_agent
        self.bull = bull_analyst
        self.bear = bear_analyst
        self.llm = llm_client

    async def process(self, input: AgentInput) -> AgentOutput:
        ticker = input.data.get("ticker")

        # 1. 리서치 분석 가져오기
        research_result = await self.research.process(input)

        # 2. Bull/Bear 병렬 분석
        bull_result, bear_result = await asyncio.gather(
            self.bull.analyze(ticker, research_result.data),
            self.bear.analyze(ticker, research_result.data)
        )

        # 3. Consensus 계산
        consensus = self._calculate_consensus(
            bull_result, bear_result
        )

        # 4. 최종 시그널
        signal = {
            "ticker": ticker,
            "action": consensus['action'],
            "confidence": consensus['confidence'],
            "price_target": consensus['target_price'],
            "bull_case": bull_result,
            "bear_case": bear_result,
            "consensus": consensus['action'],
            "reasoning": consensus['reasoning']
        }

        # 5. HITL 체크 (의견 차이 작을 때)
        hitl_trigger = None
        if abs(bull_result['confidence'] - bear_result['confidence']) < 0.1:
            hitl_trigger = {
                "reason": "Bull/Bear 의견 차이가 작아 사용자 판단이 필요합니다",
                "urgency": "medium"
            }

        return self._create_output(
            request_id=input.request_id,
            status="hitl_required" if hitl_trigger else "success",
            data=signal,
            hitl_trigger=hitl_trigger
        )

    def _calculate_consensus(self, bull: Dict, bear: Dict) -> Dict:
        """Consensus 계산"""
        bull_confidence = bull['confidence']
        bear_confidence = bear['confidence']

        if bull_confidence > bear_confidence + 0.2:
            action = "BUY"
        elif bear_confidence > bull_confidence + 0.2:
            action = "SELL"
        else:
            action = "HOLD"

        avg_confidence = (bull_confidence + (1 - bear_confidence)) / 2

        return {
            "action": action,
            "confidence": avg_confidence,
            "target_price": bull.get('target_price', 0),
            "reasoning": f"Bull: {bull_confidence:.0%}, Bear: {bear_confidence:.0%}"
        }
```

### 체크리스트

**Mock 구현** (2일):
- [ ] 기본 시그널 구조
- [ ] Mock Bull/Bear 분석

**실제 구현** (3주):
- [ ] Bull 서브에이전트
- [ ] Bear 서브에이전트
- [ ] Consensus 로직
- [ ] LLM 기반 reasoning

---

## 6. 포트폴리오 에이전트

### 역할

- 자산 배분 최적화
- 리밸런싱 제안
- 성과 추적

### Mock 구현

```python
class PortfolioAgent(AgentInterface):
    """포트폴리오 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "portfolio_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        action = input.data.get("action", "get_portfolio")

        if action == "optimize":
            # TODO: 최적화 알고리즘
            result = {
                "portfolio": {
                    "005930": 0.30,  # 삼성전자 30%
                    "000660": 0.20,  # SK하이닉스 20%
                    "035420": 0.15,  # NAVER 15%
                    "cash": 0.35
                },
                "expected_return": 0.12,
                "risk": 0.16,
                "sharpe_ratio": 0.75
            }
        elif action == "rebalance":
            # TODO: 리밸런싱 로직
            result = {
                "current": {"005930": 0.35, "000660": 0.15},
                "target": {"005930": 0.30, "000660": 0.20},
                "trades": [
                    {"ticker": "005930", "action": "SELL", "amount": 2000000},
                    {"ticker": "000660", "action": "BUY", "amount": 1500000}
                ]
            }
        else:
            result = {}

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=result
        )
```

### 실제 구현 (샤프 비율 최적화)

```python
import numpy as np
from scipy.optimize import minimize

class PortfolioAgent(AgentInterface):
    """포트폴리오 에이전트 - 실제 구현"""

    async def optimize_allocation(
        self,
        tickers: List[str],
        total_capital: float,
        user_profile: Dict
    ) -> Dict:
        """자산 배분 최적화"""

        # 1. 과거 수익률 데이터 수집
        returns = await self._get_historical_returns(tickers)

        # 2. 공분산 행렬 계산
        cov_matrix = returns.cov()

        # 3. 샤프 비율 최대화
        num_assets = len(tickers)
        initial_weights = np.array([1/num_assets] * num_assets)

        def negative_sharpe(weights):
            portfolio_return = np.sum(returns.mean() * weights) * 252
            portfolio_std = np.sqrt(
                np.dot(weights.T, np.dot(cov_matrix * 252, weights))
            )
            sharpe = portfolio_return / portfolio_std
            return -sharpe

        # 제약 조건
        constraints = (
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},  # 합 = 1
        )

        bounds = tuple((0, 0.3) for _ in range(num_assets))  # 최대 30%

        # 최적화
        result = minimize(
            negative_sharpe,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        optimal_weights = result.x

        return {
            "portfolio": {
                ticker: round(weight, 4)
                for ticker, weight in zip(tickers, optimal_weights)
            },
            "expected_return": -result.fun,  # negative sharpe를 최소화했으므로
            "risk": self._calculate_portfolio_risk(optimal_weights, cov_matrix)
        }
```

### 체크리스트

**Mock 구현** (2일):
- [ ] 기본 포트폴리오 구조
- [ ] Mock 최적화 결과

**실제 구현** (3주):
- [ ] 샤프 비율 최적화
- [ ] 리밸런싱 알고리즘
- [ ] 성과 추적
- [ ] 제약 조건 처리

---

## 7. 리스크 에이전트

### 역할

- 포트폴리오 리스크 측정
- 집중도 리스크 평가
- HITL 트리거

### Mock 구현

```python
class RiskAgent(AgentInterface):
    """리스크 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "risk_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        portfolio = input.data.get("portfolio", {})

        # TODO: 실제 리스크 계산
        risk_metrics = {
            "volatility": 0.163,
            "var_95": -0.08,
            "concentration_risk": "medium",
            "warnings": []
        }

        # 집중도 체크
        for ticker, weight in portfolio.items():
            if weight > 0.2:  # 20% 초과
                risk_metrics["warnings"].append({
                    "type": "concentration",
                    "ticker": ticker,
                    "weight": weight,
                    "message": f"{ticker} 비중이 {weight:.1%}로 높습니다"
                })

        hitl_trigger = None
        if risk_metrics["warnings"]:
            hitl_trigger = {
                "reason": "리스크 경고 발생",
                "urgency": "high",
                "details": risk_metrics["warnings"]
            }

        return self._create_output(
            request_id=input.request_id,
            status="hitl_required" if hitl_trigger else "success",
            data=risk_metrics,
            hitl_trigger=hitl_trigger
        )
```

### 체크리스트

**Mock 구현** (1일):
- [ ] 기본 리스크 구조
- [ ] Mock 경고 시스템

**실제 구현** (2주):
- [ ] VaR 계산
- [ ] 집중도 리스크
- [ ] 손실 시뮬레이션
- [ ] HITL 트리거

---

## 8. 모니터링 에이전트

### 역할

- 실시간 가격 추적
- 이벤트 감지

### Mock 구현

```python
class MonitoringAgent(AgentInterface):
    """모니터링 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "monitoring_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        tickers = input.data.get("tickers", [])

        # TODO: 실제 모니터링
        alerts = [
            {
                "ticker": "005930",
                "type": "price_spike",
                "message": "삼성전자 +5.2% 급등",
                "urgency": "medium"
            }
        ]

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data={"alerts": alerts}
        )
```

### 체크리스트

**Mock 구현** (1일):
- [ ] 기본 알림 구조

**실제 구현** (2주):
- [ ] 실시간 가격 추적
- [ ] 이벤트 감지
- [ ] 트리거 시스템

---

## 9. 교육/질의 에이전트

### 역할

- 투자 용어 설명
- 일반 질문 응답

### Mock 구현

```python
class EducationAgent(AgentInterface):
    """교육/질의 에이전트 - Mock"""

    @property
    def agent_id(self) -> str:
        return "education_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        query = input.data.get("query")

        # TODO: RAG 기반 검색
        mock_answer = {
            "answer": f"{query}에 대한 설명입니다 (Mock)",
            "references": []
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=mock_answer
        )
```

### 체크리스트

**Mock 구현** (1일):
- [ ] 기본 응답 구조

**실제 구현** (1주):
- [ ] 용어 DB 구축
- [ ] RAG 시스템
- [ ] LLM 기반 응답

---

**문서 끝**

**다음 문서**: [기술 스택 설정](./tech-stack-setup.md)
# 에이전트 구현 상세 가이드

**버전**: 2.0
**작성일**: 2025-10-01
**최종 수정일**: 2025-10-04
**기반 문서**: 에이전트 아키텍쳐 v2.0

**주요 변경사항 (v2.0)**:
- **Strategy Agent**: 개별 종목 시그널 → 투자 대전략(거시경제, 섹터 로테이션)
- **Research Agent**: Bull/Bear 서브에이전트 통합, 종합 평가 강화
- **Portfolio Agent**: 전략 구현 전 과정 책임 (스크리닝 → 분석 → 최적화)

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

## 4. 리서치 에이전트 (Research Agent)

### 역할

**개별 종목 심층 분석 및 평가**

- 기업 재무제표 분석 (수익성, 성장성, 안정성)
- 기술적 지표 계산 및 분석
- Bull/Bear 서브에이전트 운용 ⭐ **핵심**
- 산업/경쟁사 비교 분석
- 종합 평가 점수 산정
- 목표가 제시

**출력물**: 종목 분석 리포트 → Portfolio Agent에 제공

---

### Phase 1: Mock 버전

```python
class ResearchAgent(AgentInterface):
    """리서치 에이전트 - Mock 버전"""

    @property
    def agent_id(self) -> str:
        return "research_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        ticker = input.data.get("ticker")

        # TODO: 실제 분석 로직
        mock_analysis = {
            "ticker": ticker,
            "company_name": "삼성전자",

            # 종합 평가
            "overall_rating": 4.2,  # 1-5점
            "recommendation": "BUY",  # BUY/HOLD/SELL
            "target_price": 82000,

            # 재무 분석
            "profitability": {
                "roe": 0.0857,
                "roa": 0.0543,
                "net_margin": 0.0892,
                "score": 4.0
            },

            # 성장성 분석
            "growth": {
                "revenue_growth_yoy": 0.101,
                "profit_growth_yoy": 0.152,
                "revenue_growth_3y_cagr": 0.085,
                "score": 4.5
            },

            # 안정성 분석
            "stability": {
                "debt_ratio": 0.35,
                "current_ratio": 1.8,
                "interest_coverage": 12.5,
                "score": 4.2
            },

            # 기술적 분석
            "technical": {
                "current_price": 74500,
                "ma20": 74200,
                "ma60": 73500,
                "rsi": 58.3,
                "trend": "상승 추세",
                "score": 3.8
            },

            # Bull/Bear 분석 ⭐ 추가
            "bull_analysis": {
                "confidence": 0.75,
                "key_factors": [
                    "AI 수요 증가로 HBM 매출 급증",
                    "2분기 실적 예상 상회",
                    "밸류에이션 매력적 (PER 12배)"
                ],
                "target_price": 85000,
                "probability": 0.65
            },

            "bear_analysis": {
                "confidence": 0.25,
                "key_factors": [
                    "글로벌 경기 둔화 우려",
                    "중국 반도체 경쟁 심화",
                    "스마트폰 수요 정체"
                ],
                "downside_risk": 68000,
                "probability": 0.35
            },

            # Consensus (Bull/Bear 통합)
            "consensus": {
                "direction": "bullish",
                "conviction": "strong",
                "summary": "강한 매수. Bull 요인이 Bear 리스크를 압도"
            },

            # 종합 의견
            "summary": "실적 양호, 기술적으로 중립. AI 수요 증가가 핵심 상승 동력"
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=mock_analysis
        )
```

---

### Phase 2: 실제 구현

```python
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class BullAnalysis:
    """Bull 분석 결과"""
    confidence: float
    key_factors: List[str]
    target_price: float
    probability: float
    reasoning: str

@dataclass
class BearAnalysis:
    """Bear 분석 결과"""
    confidence: float
    key_factors: List[str]
    downside_risk: float
    probability: float
    reasoning: str

class ResearchAgent(AgentInterface):
    """리서치 에이전트 - 실제 구현"""

    def __init__(
        self,
        data_collector: DataCollectionAgent,
        bull_analyst,  # 서브에이전트
        bear_analyst,  # 서브에이전트
        llm_client
    ):
        self.data_collector = data_collector
        self.bull_analyst = bull_analyst
        self.bear_analyst = bear_analyst
        self.llm = llm_client

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
        profitability = self._analyze_profitability(data.data['financials'])
        growth = await self._analyze_growth(ticker, data.data)
        stability = self._analyze_stability(data.data['financials'])
        technical = await self._analyze_technical(ticker)

        # 3. Bull/Bear 병렬 분석 ⭐ 핵심
        bull_result, bear_result = await asyncio.gather(
            self.bull_analyst.analyze(
                ticker,
                {
                    "financials": data.data['financials'],
                    "news": data.data.get('news', []),
                    "profitability": profitability,
                    "growth": growth,
                    "technical": technical
                }
            ),
            self.bear_analyst.analyze(
                ticker,
                {
                    "financials": data.data['financials'],
                    "news": data.data.get('news', []),
                    "stability": stability,
                    "technical": technical
                }
            )
        )

        # 4. Consensus 계산
        consensus = self._calculate_consensus(bull_result, bear_result)

        # 5. 종합 평가
        overall_rating = self._calculate_overall_rating(
            profitability, growth, stability, technical, consensus
        )

        # 6. 목표가 산정
        target_price = self._calculate_target_price(
            bull_result, bear_result, technical
        )

        # 7. 최종 분석 결과
        analysis = {
            "ticker": ticker,
            "overall_rating": overall_rating,
            "recommendation": self._get_recommendation(overall_rating, consensus),
            "target_price": target_price,
            "profitability": profitability,
            "growth": growth,
            "stability": stability,
            "technical": technical,
            "bull_analysis": bull_result.__dict__,
            "bear_analysis": bear_result.__dict__,
            "consensus": consensus,
            "summary": self._generate_summary(
                overall_rating, consensus, bull_result, bear_result
            )
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=analysis
        )

    def _calculate_consensus(
        self,
        bull: BullAnalysis,
        bear: BearAnalysis
    ) -> Dict:
        """Bull/Bear Consensus 계산"""

        confidence_diff = bull.confidence - bear.confidence

        if confidence_diff > 0.3:
            direction = "bullish"
            conviction = "strong"
        elif confidence_diff > 0.1:
            direction = "bullish"
            conviction = "moderate"
        elif confidence_diff < -0.3:
            direction = "bearish"
            conviction = "strong"
        elif confidence_diff < -0.1:
            direction = "bearish"
            conviction = "moderate"
        else:
            direction = "neutral"
            conviction = "weak"

        return {
            "direction": direction,
            "conviction": conviction,
            "bull_confidence": bull.confidence,
            "bear_confidence": bear.confidence,
            "summary": f"{conviction.title()} {direction}"
        }

    def _calculate_target_price(
        self,
        bull: BullAnalysis,
        bear: BearAnalysis,
        technical: Dict
    ) -> float:
        """목표가 산정 (확률 가중)"""
        target = (
            bull.target_price * bull.probability +
            bear.downside_risk * bear.probability
        )
        return round(target, -2)
```

---

### Bull/Bear 서브에이전트

#### Bull Analyst (긍정적 시나리오)

```python
class BullAnalyst:
    """Bull 분석 서브에이전트"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def analyze(self, ticker: str, context: Dict) -> BullAnalysis:
        """Bull 케이스 분석"""

        prompt = f"""
        종목: {ticker}

        다음 데이터를 바탕으로 Bull 케이스를 분석하세요:
        - 재무 지표: {context['profitability']}
        - 성장성: {context['growth']}
        - 최근 뉴스: {context.get('news', [])}

        다음을 분석:
        1. 긍정적 요인 (최대 5개)
        2. 상승 시나리오 확률
        3. 목표가
        4. 확신도 (0-1)

        JSON 형식으로 답변하세요.
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)
        return BullAnalysis(**data)
```

#### Bear Analyst (부정적 시나리오)

```python
class BearAnalyst:
    """Bear 분석 서브에이전트"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def analyze(self, ticker: str, context: Dict) -> BearAnalysis:
        """Bear 케이스 분석"""

        prompt = f"""
        종목: {ticker}

        다음 데이터를 바탕으로 Bear 케이스를 분석하세요:
        - 안정성: {context['stability']}
        - 기술적: {context['technical']}

        다음을 분석:
        1. 부정적 요인 (최대 5개)
        2. 하락 시나리오 확률
        3. 하방 리스크
        4. 확신도 (0-1)

        JSON 형식으로 답변하세요.
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)
        return BearAnalysis(**data)
```

---

### 체크리스트

**Mock 구현** (2일):
- [ ] 기본 분석 구조
- [ ] Mock Bull/Bear 분석
- [ ] Mock 재무/기술적 지표

**실제 구현** (3주):
- [ ] 재무 분석 로직
- [ ] 기술적 지표 (TA-Lib)
- [ ] Bull Analyst 서브에이전트
- [ ] Bear Analyst 서브에이전트
- [ ] Consensus 계산 로직
- [ ] 종합 평가 시스템
- [ ] 목표가 산정 알고리즘

---

### 핵심 개선 사항

**기존**: 재무/기술적 분석만 수행

**개선**: Bull/Bear 분석 통합
- ✅ 긍정적/부정적 시나리오 모두 고려
- ✅ 확률 가중 목표가 산정
- ✅ Portfolio Agent에 명확한 평가 제공
- ✅ 서브에이전트 패턴 적용

---

## 5. 전략 에이전트 (Strategy Agent)

### 역할

**투자 대전략(Grand Strategy) 수립**

- 시장 사이클 및 거시경제 환경 분석
- 섹터 로테이션 전략 수립
- 리스크 스탠스 결정 (공격적/중립/방어적)
- 자산군 배분 방향성 제시
- 투자 스타일 설정
- 사용자 전략 요구사항 해석 및 구체화

**출력물**: Strategic Blueprint (전략 청사진) → Portfolio Agent에 전달

---

### Phase 1: Mock 버전

```python
class StrategyAgent(AgentInterface):
    """전략 에이전트 - Mock 버전"""

    @property
    def agent_id(self) -> str:
        return "strategy_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        # 사용자 요구사항 파싱
        user_request = input.data.get("query", "")
        user_profile = input.data.get("user_profile", {})

        # TODO: 실제 시장 분석으로 교체
        mock_blueprint = {
            "request_id": input.request_id,
            "user_id": input.user_id,

            # 시장 전망
            "market_outlook": {
                "cycle": "mid_bull_market",  # 중기 강세장
                "confidence": 0.72,
                "timeframe": "3-6개월",
                "summary": "금리 인하 기대감으로 중기 강세 예상"
            },

            # 리스크 스탠스
            "risk_stance": "moderate_risk_on",  # 공격적, 중립, 방어적

            # 섹터 전략
            "sector_strategy": {
                "overweight": ["IT", "반도체", "헬스케어"],
                "neutral": ["금융", "소비재"],
                "underweight": ["에너지"],
                "avoid": []
            },

            # 자산 배분 목표
            "asset_allocation_target": {
                "stocks": 0.75,
                "cash": 0.25
            },

            # 투자 스타일
            "investment_style": {
                "growth_vs_value": "growth",  # 성장주 선호
                "size": "large_mid",  # 대형주 + 중형주
                "approach": "gradual_buy"  # 적립식 매수
            },

            # 리밸런싱 정책
            "rebalancing_policy": {
                "frequency": "monthly",
                "trigger_threshold": 0.05  # 5% 이상 괴리 시
            },

            # 전략 근거
            "rationale": [
                "미국 금리 인하 사이클 진입 예상",
                "AI 투자 확대로 반도체 업황 개선",
                "사용자 위험성향: 중립적 → 중간 수준 공격성"
            ]
        }

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data={"blueprint": mock_blueprint}
        )
```

---

### Phase 2: 실제 구현

```python
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class StrategicBlueprint:
    """전략 청사진 데이터 클래스"""
    market_outlook: Dict
    risk_stance: str
    sector_strategy: Dict
    asset_allocation_target: Dict
    investment_style: Dict
    rebalancing_policy: Dict
    rationale: List[str]


class StrategyAgent(AgentInterface):
    """전략 에이전트 - 실제 구현"""

    def __init__(
        self,
        data_collector: DataCollectionAgent,
        llm_client,
        market_analyzer  # 시장 분석 서브모듈
    ):
        self.data_collector = data_collector
        self.llm = llm_client
        self.market_analyzer = market_analyzer

    async def process(self, input: AgentInput) -> AgentOutput:
        """메인 전략 수립 프로세스"""

        user_request = input.data.get("query", "")
        user_profile = input.data.get("user_profile", {})

        # 1. 거시경제 데이터 수집
        macro_data = await self._collect_macro_data()

        # 2. 시장 사이클 분석
        market_cycle = await self._analyze_market_cycle(macro_data)

        # 3. 리스크 스탠스 결정
        risk_stance = self._determine_risk_stance(
            market_cycle,
            user_profile
        )

        # 4. 섹터 전략 수립
        sector_strategy = await self._formulate_sector_strategy(
            market_cycle,
            risk_stance
        )

        # 5. 사용자 요구사항 해석
        investment_style = await self._interpret_user_strategy(
            user_request,
            user_profile
        )

        # 6. 전략 청사진 생성
        blueprint = StrategicBlueprint(
            market_outlook=market_cycle,
            risk_stance=risk_stance,
            sector_strategy=sector_strategy,
            asset_allocation_target=self._calculate_asset_allocation(
                risk_stance,
                user_profile
            ),
            investment_style=investment_style,
            rebalancing_policy=self._define_rebalancing_policy(
                investment_style
            ),
            rationale=self._generate_rationale(
                market_cycle,
                sector_strategy,
                user_profile
            )
        )

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data={"blueprint": blueprint.__dict__}
        )

    async def _analyze_market_cycle(self, macro_data: Dict) -> Dict:
        """시장 사이클 분석 (LLM 활용)"""

        prompt = f"""
        다음 거시경제 데이터를 바탕으로 현재 시장 사이클을 분석하세요.

        데이터:
        - 금리: {macro_data['interest_rate']}% ({macro_data['interest_rate_trend']})
        - CPI: {macro_data['cpi']}%
        - GDP 성장률: {macro_data['gdp_growth']}%

        현재 시장 사이클 위치를 판단하고 JSON 형식으로 답변하세요.
        """

        response = await self.llm.complete(prompt)
        return json.loads(response)

    def _determine_risk_stance(
        self,
        market_cycle: Dict,
        user_profile: Dict
    ) -> str:
        """리스크 스탠스 결정"""

        # 시장 환경과 사용자 성향 결합
        risk_map = {
            ("aggressive", "bull"): "aggressive_risk_on",
            ("moderate", "bull"): "moderate_risk_on",
            ("conservative", "bull"): "neutral",
            # ... 기타 조합
        }

        return risk_map.get((user_profile['risk_tolerance'], "bull"), "neutral")
```

---

### 출력 예시: Strategic Blueprint

```json
{
  "market_outlook": {
    "cycle": "mid_bull_market",
    "confidence": 0.72,
    "timeframe": "3-6개월",
    "summary": "금리 인하 기대감으로 중기 강세 예상"
  },
  "risk_stance": "moderate_risk_on",
  "sector_strategy": {
    "overweight": ["IT", "반도체", "헬스케어"],
    "neutral": ["금융", "소비재"],
    "underweight": ["에너지"],
    "avoid": []
  },
  "asset_allocation_target": {
    "stocks": 0.75,
    "cash": 0.25
  },
  "investment_style": {
    "growth_vs_value": "growth",
    "size": "large_mid",
    "approach": "gradual_buy"
  },
  "rebalancing_policy": {
    "frequency": "monthly",
    "trigger_threshold": 0.05
  }
}
```

---

### 체크리스트

**Mock 구현** (3일):
- [ ] 기본 인터페이스
- [ ] Mock 시장 사이클 데이터
- [ ] Mock 섹터 전략
- [ ] Strategic Blueprint 스키마

**실제 구현** (3주):
- [ ] 거시경제 데이터 수집
- [ ] LLM 기반 시장 사이클 분석
- [ ] 리스크 스탠스 로직
- [ ] 섹터 로테이션 전략
- [ ] 사용자 요구사항 해석
- [ ] 전략 청사진 생성

---

### 핵심 개선 사항

**기존 (개별 종목 시그널)**:
- Bull/Bear 분석
- 매수/매도 시그널
- 목표가 제시

**개선 (거시적 대전략)**:
- 시장 사이클 분석
- 섹터 로테이션
- 자산 배분 방향성
- 투자 스타일 설정

**→ Portfolio Agent에게 명확한 가이드라인 제공**

---

## 6. 포트폴리오 에이전트 (Portfolio Agent)

### 역할

**전략 청사진을 구체적 포트폴리오로 구현**

- Strategic Blueprint 해석 및 제약조건 파악
- 후보 종목 스크리닝 (섹터/스타일/시가총액 필터링)
- Research Agent 결과 활용하여 최종 종목 선택
- 자산 배분 최적화 (샤프 비율, 리스크 제약)
- 리밸런싱 계획 수립 및 실행
- 포트폴리오 성과 추적

**입력**: Strategic Blueprint, 현재 포트폴리오
**출력**: 구체적 종목 리스트 + 비중 + 매매 지시

---

### Phase 1: Mock 버전

```python
class PortfolioAgent(AgentInterface):
    """포트폴리오 에이전트 - Mock 버전"""

    @property
    def agent_id(self) -> str:
        return "portfolio_agent"

    async def process(self, input: AgentInput) -> AgentOutput:
        action = input.data.get("action", "construct")

        if action == "construct":
            # 새 포트폴리오 구성
            result = await self._mock_construct_portfolio(input)
        elif action == "rebalance":
            # 리밸런싱
            result = await self._mock_rebalance(input)
        else:
            result = {"error": "Unknown action"}

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=result
        )

    async def _mock_construct_portfolio(self, input: AgentInput) -> Dict:
        """포트폴리오 구성 - Mock"""

        blueprint = input.data.get("blueprint", {})
        total_capital = input.data.get("total_capital", 10000000)

        mock_portfolio = {
            "portfolio_id": f"PF_{input.request_id[:8]}",
            "total_capital": total_capital,

            # 구성 종목
            "holdings": {
                "005930": {
                    "name": "삼성전자",
                    "sector": "IT",
                    "weight": 0.25,
                    "shares": 33,
                    "research_score": 4.2,
                    "reason": "IT 섹터 대표주, AI 수요 증가"
                }
            },

            # 현금
            "cash": {"weight": 0.25, "amount": 2500000},

            # 포트폴리오 지표
            "metrics": {
                "expected_return": 0.128,
                "sharpe_ratio": 0.776
            },

            # 섹터 배분
            "sector_allocation": {
                "IT": 0.40,
                "반도체": 0.20,
                "현금": 0.25
            }
        }

        return mock_portfolio
```

---

### Phase 2: 실제 구현

```python
import numpy as np
from scipy.optimize import minimize

class PortfolioAgent(AgentInterface):
    """포트폴리오 에이전트 - 실제 구현"""

    def __init__(
        self,
        strategy_agent: StrategyAgent,
        research_agent: ResearchAgent,
        risk_agent: RiskAgent
    ):
        self.strategy = strategy_agent
        self.research = research_agent
        self.risk = risk_agent

    async def process(self, input: AgentInput) -> AgentOutput:
        action = input.data.get("action", "construct")

        if action == "construct":
            result = await self._construct_portfolio(input)
        elif action == "rebalance":
            result = await self._rebalance_portfolio(input)
        else:
            result = {"error": "Unknown action"}

        return self._create_output(
            request_id=input.request_id,
            status="success",
            data=result
        )

    async def _construct_portfolio(self, input: AgentInput) -> Dict:
        """포트폴리오 구성"""

        blueprint = input.data.get("blueprint")
        total_capital = input.data.get("total_capital", 10000000)

        # 1. Strategic Blueprint 해석
        constraints = self._parse_blueprint_constraints(blueprint)

        # 2. 후보 종목 스크리닝
        candidate_tickers = await self._screen_candidates(blueprint)

        # 3. 후보 종목 분석 (Research Agent 활용)
        analyses = await self._analyze_candidates(candidate_tickers, input)

        # 4. 종목 선택
        selected_tickers = self._select_stocks(analyses, constraints)

        # 5. 자산 배분 최적화
        optimal_weights = await self._optimize_allocation(
            selected_tickers,
            blueprint,
            constraints
        )

        # 6. 포트폴리오 구성
        portfolio = self._build_portfolio(
            selected_tickers,
            optimal_weights,
            analyses,
            total_capital
        )

        return portfolio

    async def _screen_candidates(self, blueprint: Dict) -> List[str]:
        """후보 종목 스크리닝"""

        # 1. 선호 섹터 종목 리스트업
        overweight_sectors = blueprint['sector_strategy']['overweight']
        candidates = []

        for sector in overweight_sectors:
            sector_stocks = await self._get_sector_stocks(sector)
            candidates.extend(sector_stocks)

        # 2. 스타일 필터링
        if blueprint['investment_style']['size'] == 'large':
            candidates = self._filter_by_market_cap(candidates, 'large')

        return candidates[:30]  # 최대 30개

    async def _analyze_candidates(
        self,
        tickers: List[str],
        input: AgentInput
    ) -> Dict[str, Dict]:
        """후보 종목들 분석 (Research Agent 병렬 호출)"""

        tasks = [
            self.research.process(
                AgentInput(
                    request_id=input.request_id,
                    user_id=input.user_id,
                    automation_level=input.automation_level,
                    data={"ticker": ticker}
                )
            )
            for ticker in tickers
        ]

        results = await asyncio.gather(*tasks)

        return {
            ticker: result.data
            for ticker, result in zip(tickers, results)
        }

    def _select_stocks(
        self,
        analyses: Dict[str, Dict],
        constraints: Dict
    ) -> List[str]:
        """종목 선택 (분석 결과 기반)"""

        # 평가 점수 기준 정렬
        ranked = sorted(
            analyses.items(),
            key=lambda x: x[1]['overall_rating'],
            reverse=True
        )

        # 최소 기준 충족 종목만
        min_rating = 3.0
        qualified = [
            ticker for ticker, analysis in ranked
            if analysis['overall_rating'] >= min_rating
        ]

        return qualified[:constraints.get('max_stocks', 10)]

    async def _optimize_allocation(
        self,
        tickers: List[str],
        blueprint: Dict,
        constraints: Dict
    ) -> Dict[str, float]:
        """샤프 비율 최적화"""

        # 과거 수익률 데이터
        returns_data = await self._get_historical_returns(tickers)
        expected_returns = returns_data.mean() * 252
        cov_matrix = returns_data.cov() * 252

        # 최적화
        num_assets = len(tickers)

        def negative_sharpe(weights):
            portfolio_return = np.sum(expected_returns * weights)
            portfolio_std = np.sqrt(
                np.dot(weights.T, np.dot(cov_matrix, weights))
            )
            return -portfolio_return / portfolio_std if portfolio_std > 0 else 0

        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - constraints['stock_ratio']}
        ]

        bounds = tuple((0.0, 0.30) for _ in range(num_assets))

        result = minimize(
            negative_sharpe,
            [constraints['stock_ratio'] / num_assets] * num_assets,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )

        return {
            ticker: round(weight, 4)
            for ticker, weight in zip(tickers, result.x)
            if weight > 0.01
        }
```

---

### 체크리스트

**Mock 구현** (2일):
- [ ] 기본 포트폴리오 구조
- [ ] Mock 종목 선택

**실제 구현** (3주):
- [ ] Blueprint 해석 로직
- [ ] 후보 종목 스크리닝
- [ ] Research Agent 통합
- [ ] 샤프 비율 최적화
- [ ] 리밸런싱 알고리즘
- [ ] 전략 준수도 검증

---

### 핵심 개선 사항

**기존**: 자산 배분 최적화만 담당

**개선**: 전략 구현의 전 과정 책임
- ✅ Strategic Blueprint 해석
- ✅ 종목 스크리닝 → 분석 → 선택
- ✅ Research Agent 결과 활용
- ✅ 최적화 + 리밸런싱

**→ Strategy Agent의 방향성을 구체적 포트폴리오로 구현**

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
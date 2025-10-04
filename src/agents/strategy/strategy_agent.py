"""
Strategy Agent v2.0 - 거시 대전략 수립

역할 재정의:
- 개별 종목 분석 ❌ (Research Agent로 이관)
- 거시적 시장 분석 ✅
- 섹터 로테이션 전략 ✅
- 자산 배분 전략 ✅
- Strategic Blueprint 생성 ✅

출력물: Strategic Blueprint (Portfolio Agent에게 전달)
"""

from decimal import Decimal
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput
from src.schemas.strategy import (
    StrategicBlueprint,
    MarketCycle,
    SectorStrategy,
    SectorWeight,
    AssetAllocation,
    InvestmentStyle
)


class StrategyAgent(BaseAgent):
    """
    Strategy Agent v2.0 - 거시 대전략 수립

    Week 13 Mock 구현:
    - [x] Strategic Blueprint 스키마 정의
    - [x] Mock 시장 사이클 분석
    - [x] Mock 섹터 전략 생성
    - [x] 사용자 선호도 반영

    Week 14 실제 구현 예정:
    - [ ] LLM 기반 시장 사이클 분석
    - [ ] 거시경제 데이터 연동
    - [ ] 섹터 로테이션 로직 고도화
    """

    def __init__(self):
        super().__init__("strategy_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        거시 대전략 수립 프로세스

        입력:
        - context.user_preferences: 사용자 선호 설정
        - context.portfolio_balance: 투자 가능 금액
        - context.risk_tolerance: 리스크 허용도

        출력:
        - Strategic Blueprint
        """
        try:
            # 컨텍스트 추출
            context = input_data.context or {}
            user_preferences = context.get("user_preferences", {})
            risk_tolerance = context.get("risk_tolerance", "moderate")

            print(f"\n🎯 [Strategy Agent] 거시 대전략 수립 시작...")
            print(f"   리스크 허용도: {risk_tolerance}")

            # 1. 시장 사이클 분석 (Mock)
            market_outlook = await self._analyze_market_cycle()

            # 2. 섹터 전략 수립 (Mock)
            sector_strategy = await self._create_sector_strategy(
                market_cycle=market_outlook.cycle,
                user_preferences=user_preferences
            )

            # 3. 자산 배분 결정 (Mock)
            asset_allocation = await self._determine_asset_allocation(
                market_cycle=market_outlook.cycle,
                risk_tolerance=risk_tolerance
            )

            # 4. 투자 스타일 결정
            investment_style = self._determine_investment_style(
                user_preferences=user_preferences
            )

            # 5. Strategic Blueprint 생성
            blueprint = StrategicBlueprint(
                market_outlook=market_outlook,
                sector_strategy=sector_strategy,
                asset_allocation=asset_allocation,
                investment_style=investment_style,
                risk_tolerance=risk_tolerance,
                constraints={
                    "max_stocks": 10,
                    "max_per_stock": 0.20,
                    "min_stocks": 5
                },
                confidence_score=0.75,
                key_assumptions=[
                    "IT 섹터 주도 상승장 지속",
                    "금리 안정화 국면",
                    "중기적 강세장 유지"
                ]
            )

            print(f"✅ [Strategy Agent] Strategic Blueprint 생성 완료")
            print(f"   시장 전망: {market_outlook.cycle} (신뢰도: {market_outlook.confidence:.0%})")
            print(f"   자산 배분: 주식 {asset_allocation.stocks:.0%}, 현금 {asset_allocation.cash:.0%}")
            print(f"   핵심 섹터: {', '.join(sector_strategy.overweight)}")

            return AgentOutput(
                status="success",
                data={
                    "blueprint": blueprint.model_dump(),
                    "summary": self._create_summary(blueprint)
                },
                metadata={
                    "agent_version": "v2.0",
                    "implementation": "mock",
                    "market_cycle": market_outlook.cycle
                }
            )

        except Exception as e:
            print(f"❌ [Strategy Agent] Error: {e}")
            return AgentOutput(
                status="failure",
                error=str(e)
            )

    async def _analyze_market_cycle(self) -> MarketCycle:
        """
        시장 사이클 분석 (Mock)

        Week 14 실제 구현:
        - 거시경제 지표 수집 (금리, CPI, GDP)
        - LLM 기반 사이클 판단
        - 신뢰도 계산
        """
        # Mock: 중기 강세장
        return MarketCycle(
            cycle="mid_bull_market",
            confidence=0.72,
            summary="IT 섹터 주도의 중기 강세장. 금리 안정화로 기술주 선호 지속"
        )

    async def _create_sector_strategy(
        self,
        market_cycle: str,
        user_preferences: dict
    ) -> SectorStrategy:
        """
        섹터 전략 수립 (Mock)

        Week 14 실제 구현:
        - LLM 기반 섹터 평가
        - 사용자 선호도 통합
        - 동적 비중 조정
        """
        # Mock: IT/반도체 중심 전략
        sectors = [
            SectorWeight(sector="IT", weight=Decimal("0.40"), stance="overweight"),
            SectorWeight(sector="반도체", weight=Decimal("0.20"), stance="overweight"),
            SectorWeight(sector="헬스케어", weight=Decimal("0.15"), stance="neutral"),
            SectorWeight(sector="금융", weight=Decimal("0.15"), stance="neutral"),
            SectorWeight(sector="에너지", weight=Decimal("0.10"), stance="underweight"),
        ]

        # 사용자 선호도 반영
        preferred_sectors = user_preferences.get("sectors", [])
        if preferred_sectors:
            print(f"   사용자 선호 섹터 반영: {preferred_sectors}")

        return SectorStrategy(
            sectors=sectors,
            overweight=["IT", "반도체"],
            underweight=["에너지"],
            rationale="중기 강세장에서 IT 섹터 주도 상승 예상. 금리 안정화로 기술주 선호 지속"
        )

    async def _determine_asset_allocation(
        self,
        market_cycle: str,
        risk_tolerance: str
    ) -> AssetAllocation:
        """
        자산 배분 결정 (Mock)

        리스크 허용도별 주식/현금 비율:
        - conservative: 60% / 40%
        - moderate: 75% / 25%
        - aggressive: 90% / 10%
        """
        allocation_map = {
            "conservative": (Decimal("0.60"), Decimal("0.40")),
            "moderate": (Decimal("0.75"), Decimal("0.25")),
            "aggressive": (Decimal("0.90"), Decimal("0.10")),
        }

        stocks, cash = allocation_map.get(risk_tolerance, (Decimal("0.75"), Decimal("0.25")))

        return AssetAllocation(
            stocks=stocks,
            cash=cash,
            rationale=f"{risk_tolerance} 리스크 허용도에 맞춘 자산 배분. 중기 강세장 기조 반영"
        )

    def _determine_investment_style(self, user_preferences: dict) -> InvestmentStyle:
        """투자 스타일 결정"""
        return InvestmentStyle(
            type=user_preferences.get("style", "growth"),
            horizon=user_preferences.get("horizon", "mid_term"),
            approach=user_preferences.get("approach", "dollar_cost_averaging"),
            size_preference=user_preferences.get("size", "large")
        )

    def _create_summary(self, blueprint: StrategicBlueprint) -> str:
        """Blueprint 요약 생성"""
        market = blueprint.market_outlook
        sectors = blueprint.sector_strategy
        allocation = blueprint.asset_allocation

        return (
            f"{market.cycle} 국면, "
            f"주식 {allocation.stocks:.0%}/현금 {allocation.cash:.0%}, "
            f"핵심 섹터: {', '.join(sectors.overweight[:2])}"
        )

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock response (deprecated in v2.0)"""
        return AgentOutput(
            status="success",
            data={"message": "v2.0 uses real implementation"}
        )


# Global instance
strategy_agent = StrategyAgent()

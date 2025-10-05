"""
Risk Agent - Risk Assessment and Warnings

Responsibilities:
- Portfolio risk measurement
- Concentration risk alerts
- Loss simulation
- Risk threshold monitoring
"""
from decimal import Decimal
from src.agents.legacy import LegacyAgent
from src.schemas.agent import AgentInput, AgentOutput


class RiskAgent(LegacyAgent):
    """
    Risk Agent - Evaluates and warns about risks

    TODO Phase 1 실제 구현:
    - [ ] VaR (Value at Risk) 계산
    - [ ] 집중도 리스크 분석
    - [ ] 손실 시뮬레이션 (Monte Carlo)
    - [ ] 포트폴리오 변동성 계산
    - [ ] 리스크 임계값 체크
    """

    def __init__(self):
        super().__init__("risk_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        Main risk assessment process

        TODO: Implement actual risk calculations
        """
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock risk assessment"""
        return AgentOutput(
            status="success",
            data={
                "risk_level": "medium",
                "risk_score": Decimal("55"),
                "concentration_risk": Decimal("0.35"),
                "volatility": Decimal("0.18"),
                "var_95": Decimal("0.08"),
                "max_drawdown_estimate": Decimal("0.12"),
                "warnings": [
                    "삼성전자 비중이 포트폴리오의 35%로 높음",
                    "반도체 섹터 집중도 50% 초과"
                ],
                "recommendations": [
                    "삼성전자 비중을 25% 이하로 조정 권장",
                    "IT 외 다른 섹터로 분산 투자 필요"
                ],
                "should_trigger_hitl": False,
                "sector_breakdown": {
                    "IT": Decimal("0.55"),
                    "Finance": Decimal("0.20"),
                    "Healthcare": Decimal("0.15"),
                    "Others": Decimal("0.10")
                }
            },
            metadata={
                "source": "mock",
                "note": "TODO: Implement VaR and risk simulation"
            }
        )


# Global instance
risk_agent = RiskAgent()

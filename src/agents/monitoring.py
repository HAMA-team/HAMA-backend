"""
Monitoring Agent - Market and Portfolio Monitoring

Responsibilities:
- Track price movements
- Detect important events
- Generate alerts
- Periodic reporting
"""
from decimal import Decimal
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput


class MonitoringAgent(BaseAgent):
    """
    Monitoring Agent - Monitors market and portfolio status

    TODO Phase 1 실제 구현:
    - [ ] 실시간 가격 추적
    - [ ] 이벤트 감지 (급등/급락, 거래량 급증)
    - [ ] 공시 모니터링
    - [ ] 뉴스 모니터링
    - [ ] 알림 트리거 시스템
    """

    def __init__(self):
        super().__init__("monitoring_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main monitoring process"""
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock monitoring report"""
        return AgentOutput(
            status="success",
            data={
                "monitoring_period": "daily",
                "alerts_generated": 2,
                "portfolio_status": "normal",
                "significant_events": [
                    {
                        "type": "price_movement",
                        "stock": "005930",
                        "change": Decimal("0.032"),
                        "message": "삼성전자 +3.2% 상승"
                    },
                    {
                        "type": "disclosure",
                        "stock": "000660",
                        "message": "SK하이닉스 분기보고서 제출"
                    }
                ],
                "market_summary": {
                    "kospi": {"change": Decimal("0.015"), "status": "상승"},
                    "kosdaq": {"change": Decimal("-0.008"), "status": "하락"},
                },
                "recommendations": [
                    "보유 종목 중 공시 발표 예정 종목 확인 필요"
                ]
            },
            metadata={
                "source": "mock",
                "note": "TODO: Implement real-time monitoring system"
            }
        )


# Global instance
monitoring_agent = MonitoringAgent()
"""
Strategy Agent - Investment Strategy and Signals

Responsibilities:
- Generate buy/sell signals
- Bull/Bear analysis
- Stock screening
- Timing recommendations
"""
from decimal import Decimal
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput


class StrategyAgent(BaseAgent):
    """
    Strategy Agent - Generates investment strategies and signals

    TODO Phase 1 실제 구현:
    - [ ] Bull/Bear 서브에이전트 구현
    - [ ] 매매 시그널 생성 로직
    - [ ] 종목 스크리닝 알고리즘
    - [ ] 타이밍 분석 (기술적 분석 + 모멘텀)
    - [ ] LLM 기반 의견 종합
    """

    def __init__(self):
        super().__init__("strategy_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        Main strategy process

        TODO: Implement actual strategy logic
        - Run Bull/Bear debate
        - Generate trading signals
        - Calculate confidence scores
        - Determine consensus
        """
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock strategy response"""
        stock_code = input_data.context.get("stock_code", "005930") if input_data.context else "005930"

        return AgentOutput(
            status="success",
            data={
                "stock_code": stock_code,
                "action": "BUY",
                "confidence": Decimal("0.72"),
                "current_price": Decimal("76000"),
                "target_price": Decimal("85000"),
                "stop_loss": Decimal("71000"),
                "reasoning": "반도체 업황 회복 + 기술적 돌파 임박",
                "bull_analysis": {
                    "confidence": Decimal("0.75"),
                    "arguments": [
                        "메모리 반도체 가격 반등 시작",
                        "AI 서버용 HBM 수요 급증",
                        "기술적으로 200일선 돌파"
                    ],
                    "expected_return": Decimal("0.12")
                },
                "bear_analysis": {
                    "confidence": Decimal("0.28"),
                    "arguments": [
                        "글로벌 경기 둔화 우려",
                        "중국 시장 회복 지연",
                        "단기 과매수 구간"
                    ],
                    "expected_loss": Decimal("-0.06")
                },
                "consensus": "bullish",
                "consensus_strength": "moderate",
                "timing": {
                    "immediate": True,
                    "horizon": "3-6 months",
                    "entry_strategy": "적립식 매수 권장"
                }
            },
            metadata={
                "source": "mock",
                "note": "TODO: Implement Bull/Bear sub-agents with LLM"
            }
        )


# Global instance
strategy_agent = StrategyAgent()
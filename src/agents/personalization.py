"""
Personalization Agent - User Profile and Preference Management

Responsibilities:
- Manage user investment profile
- Track user preferences
- Learn from user decisions (Phase 2)
- Customize recommendations
"""
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput


class PersonalizationAgent(BaseAgent):
    """
    Personalization Agent - Manages user profiles and preferences

    TODO Phase 1 실제 구현:
    - [ ] 사용자 프로필 CRUD
    - [ ] 투자 성향 분석
    - [ ] 선호/회피 종목/섹터 관리
    - [ ] 자동화 레벨 조정 로직

    TODO Phase 2:
    - [ ] 사용자 행동 학습
    - [ ] 개인화 추천 시스템
    - [ ] 맞춤형 알림 설정
    """

    def __init__(self):
        super().__init__("personalization_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main personalization process"""
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock user profile"""
        return AgentOutput(
            status="success",
            data={
                "user_id": "mock_user_001",
                "profile": {
                    "risk_tolerance": "active",
                    "investment_goal": "mid_long_term",
                    "investment_horizon": "3_5y",
                    "automation_level": 2,
                },
                "preferences": {
                    "preferred_sectors": ["IT", "Healthcare"],
                    "avoided_sectors": ["Construction"],
                    "preferred_stocks": [],
                    "avoided_stocks": ["담배 관련"],
                },
                "constraints": {
                    "max_single_stock_ratio": 0.20,
                    "max_sector_ratio": 0.40,
                    "initial_capital": 10000000,
                },
                "customization": {
                    "notification_settings": {
                        "email": True,
                        "push": False,
                    },
                    "monitoring_frequency": "daily",
                }
            },
            metadata={
                "source": "mock",
                "note": "TODO: Implement user profile management"
            }
        )


# Global instance
personalization_agent = PersonalizationAgent()
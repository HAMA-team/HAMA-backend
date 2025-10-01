"""
Education/Q&A Agent - Investment Education and General Questions

Responsibilities:
- Explain investment terms
- Answer general market questions
- Provide educational content
- Market context explanation
"""
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput


class EducationAgent(BaseAgent):
    """
    Education Agent - Provides investment education and answers questions

    TODO Phase 1 실제 구현:
    - [ ] 투자 용어 사전 DB 구축
    - [ ] RAG 기반 질의응답
    - [ ] LLM 기반 설명 생성
    - [ ] 맥락에 맞는 교육 콘텐츠 추천
    """

    def __init__(self):
        super().__init__("education_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main education process"""
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock educational response"""
        query = input_data.context.get("query", "") if input_data.context else ""

        return AgentOutput(
            status="success",
            data={
                "query": query,
                "answer": "PER(주가수익비율)은 주가를 주당순이익(EPS)으로 나눈 값으로, "
                         "주가가 1주당 수익의 몇 배로 거래되고 있는지를 나타냅니다. "
                         "일반적으로 PER이 낮을수록 저평가, 높을수록 고평가로 해석됩니다.",
                "related_terms": ["EPS", "PBR", "ROE"],
                "examples": {
                    "삼성전자": "PER 15배는 15년 치 이익으로 현재 주가를 회수할 수 있다는 의미"
                },
                "educational_content": [
                    {
                        "title": "PER 해석 시 주의사항",
                        "content": "업종별로 적정 PER이 다르므로 절대적 기준으로 사용하면 안 됨"
                    }
                ]
            },
            metadata={
                "source": "mock",
                "note": "TODO: Implement RAG-based Q&A system"
            }
        )


# Global instance
education_agent = EducationAgent()
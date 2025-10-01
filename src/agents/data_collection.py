"""
Data Collection Agent - Raw Data Fetching

Responsibilities:
- Fetch stock prices (pykrx)
- Fetch financial statements (DART)
- Fetch news (web scraping)
- Cache and store data
"""
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput


class DataCollectionAgent(BaseAgent):
    """
    Data Collection Agent - Fetches raw data from external sources

    TODO Phase 1 실제 구현:
    - [ ] pykrx 통합 (주가, 거래량, 시가총액)
    - [ ] DART API 통합 (재무제표, 공시)
    - [ ] 한국투자증권 API (실시간 시세) - Phase 2
    - [ ] 네이버 금융 크롤링 (뉴스)
    - [ ] 데이터 캐싱 (functools.lru_cache)
    - [ ] 에러 핸들링 및 재시도 로직
    """

    def __init__(self):
        super().__init__("data_collection_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main data collection process"""
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock data collection response"""
        data_type = input_data.context.get("data_type", "stock_price") if input_data.context else "stock_price"
        stock_code = input_data.context.get("stock_code", "005930") if input_data.context else "005930"

        if data_type == "stock_price":
            return AgentOutput(
                status="success",
                data={
                    "stock_code": stock_code,
                    "prices": [
                        {"date": "2025-09-28", "close": 76000, "volume": 12000000},
                        {"date": "2025-09-27", "close": 75500, "volume": 11500000},
                    ],
                    "source": "pykrx"
                },
                metadata={"source": "mock", "note": "TODO: Integrate pykrx"}
            )
        elif data_type == "financial_statement":
            return AgentOutput(
                status="success",
                data={
                    "stock_code": stock_code,
                    "fiscal_year": 2025,
                    "fiscal_quarter": 2,
                    "revenue": 77000000000000,
                    "operating_profit": 10500000000000,
                    "net_profit": 8200000000000,
                    "source": "DART"
                },
                metadata={"source": "mock", "note": "TODO: Integrate DART API"}
            )
        elif data_type == "news":
            return AgentOutput(
                status="success",
                data={
                    "stock_code": stock_code,
                    "news": [
                        {
                            "title": "삼성전자, AI 반도체 공급 확대",
                            "url": "https://...",
                            "published_at": "2025-09-28",
                            "source": "네이버 금융"
                        }
                    ]
                },
                metadata={"source": "mock", "note": "TODO: Implement web scraping"}
            )

        return AgentOutput(status="failure", error="Unknown data type")


# Global instance
data_collection_agent = DataCollectionAgent()
"""
Data Collection Agent - Raw Data Fetching

Responsibilities:
- Fetch stock prices (FinanceDataReader)
- Fetch financial statements (DART)
- Fetch news (web scraping) - Phase 2
- Cache and store data
"""
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput
from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service
from datetime import datetime


class DataCollectionAgent(BaseAgent):
    """
    Data Collection Agent - Fetches raw data from external sources

    Phase 2 실제 구현 완료:
    - [x] FinanceDataReader 통합 (주가, 거래량)
    - [x] DART API 통합 (재무제표, 공시, 기업 정보)
    - [x] 데이터 캐싱 (CacheManager)
    - [x] 에러 핸들링

    TODO Phase 3:
    - [ ] 한국투자증권 API (실시간 시세)
    - [ ] 네이버 금융 크롤링 (뉴스)
    """

    def __init__(self):
        super().__init__("data_collection_agent")
        self.stock_service = stock_data_service
        self.dart_service = dart_service

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main data collection process"""
        data_type = input_data.context.get("data_type") if input_data.context else None

        if not data_type:
            return AgentOutput(
                status="failure",
                error="data_type is required in context"
            )

        try:
            if data_type == "stock_price":
                return await self._fetch_stock_price(input_data)
            elif data_type == "financial_statement":
                return await self._fetch_financial_statement(input_data)
            elif data_type == "company_info":
                return await self._fetch_company_info(input_data)
            elif data_type == "disclosure":
                return await self._fetch_disclosure(input_data)
            elif data_type == "stock_returns":
                return await self._fetch_stock_returns(input_data)
            else:
                return AgentOutput(
                    status="failure",
                    error=f"Unknown data type: {data_type}"
                )
        except Exception as e:
            print(f"❌ Data Collection Error: {e}")
            return AgentOutput(
                status="failure",
                error=str(e)
            )

    async def _fetch_stock_price(self, input_data: AgentInput) -> AgentOutput:
        """주가 데이터 조회"""
        stock_code = input_data.context.get("stock_code")
        days = input_data.context.get("days", 30)

        if not stock_code:
            return AgentOutput(status="failure", error="stock_code is required")

        df = await self.stock_service.get_stock_price(stock_code, days)

        if df is None or len(df) == 0:
            return AgentOutput(
                status="failure",
                error=f"No stock data found for {stock_code}"
            )

        # DataFrame을 dict로 변환
        prices = df.reset_index().to_dict("records")

        return AgentOutput(
            status="success",
            data={
                "stock_code": stock_code,
                "days": len(prices),
                "prices": prices,
                "latest_close": float(df.iloc[-1]["Close"]),
                "latest_volume": int(df.iloc[-1]["Volume"]),
                "source": "FinanceDataReader"
            },
            metadata={"days_requested": days, "days_returned": len(prices)}
        )

    async def _fetch_stock_returns(self, input_data: AgentInput) -> AgentOutput:
        """수익률 계산"""
        stock_code = input_data.context.get("stock_code")
        days = input_data.context.get("days", 30)

        if not stock_code:
            return AgentOutput(status="failure", error="stock_code is required")

        df = await self.stock_service.calculate_returns(stock_code, days)

        if df is None or len(df) == 0:
            return AgentOutput(
                status="failure",
                error=f"No stock data found for {stock_code}"
            )

        return AgentOutput(
            status="success",
            data={
                "stock_code": stock_code,
                "daily_return": float(df.iloc[-1]["Daily_Return"]) if "Daily_Return" in df.columns else None,
                "cumulative_return": float(df.iloc[-1]["Cumulative_Return"]) if "Cumulative_Return" in df.columns else None,
                "source": "FinanceDataReader"
            }
        )

    async def _fetch_financial_statement(self, input_data: AgentInput) -> AgentOutput:
        """재무제표 조회"""
        stock_code = input_data.context.get("stock_code")
        year = input_data.context.get("year", "2023")

        if not stock_code:
            return AgentOutput(status="failure", error="stock_code is required")

        # 종목코드 → 고유번호 변환
        corp_code = self.dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            return AgentOutput(
                status="failure",
                error=f"Cannot find corp_code for stock {stock_code}"
            )

        # 재무제표 조회
        statements = await self.dart_service.get_financial_statement(
            corp_code, bsns_year=str(year)
        )

        if not statements:
            return AgentOutput(
                status="failure",
                error=f"No financial data found for {stock_code}"
            )

        # 주요 항목 추출
        revenue = [s for s in statements if "매출액" in s.get("account_nm", "")]
        operating_profit = [s for s in statements if "영업이익" in s.get("account_nm", "")]
        net_profit = [s for s in statements if "당기순이익" in s.get("account_nm", "")]

        return AgentOutput(
            status="success",
            data={
                "stock_code": stock_code,
                "corp_code": corp_code,
                "year": year,
                "revenue_items": revenue[:5] if revenue else [],
                "operating_profit_items": operating_profit[:5] if operating_profit else [],
                "net_profit_items": net_profit[:5] if net_profit else [],
                "total_items": len(statements),
                "source": "DART"
            }
        )

    async def _fetch_company_info(self, input_data: AgentInput) -> AgentOutput:
        """기업 정보 조회"""
        stock_code = input_data.context.get("stock_code")

        if not stock_code:
            return AgentOutput(status="failure", error="stock_code is required")

        # 종목코드 → 고유번호 변환
        corp_code = self.dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            return AgentOutput(
                status="failure",
                error=f"Cannot find corp_code for stock {stock_code}"
            )

        # 기업 정보 조회
        company_info = await self.dart_service.get_company_info(corp_code)

        if not company_info:
            return AgentOutput(
                status="failure",
                error=f"No company info found for {stock_code}"
            )

        return AgentOutput(
            status="success",
            data={
                "stock_code": stock_code,
                "corp_code": corp_code,
                "corp_name": company_info.get("corp_name"),
                "ceo_nm": company_info.get("ceo_nm"),
                "corp_cls": company_info.get("corp_cls"),
                "est_dt": company_info.get("est_dt"),
                "adres": company_info.get("adres"),
                "source": "DART"
            }
        )

    async def _fetch_disclosure(self, input_data: AgentInput) -> AgentOutput:
        """공시 목록 조회"""
        stock_code = input_data.context.get("stock_code")
        bgn_de = input_data.context.get("bgn_de", "20240901")
        end_de = input_data.context.get("end_de", datetime.now().strftime("%Y%m%d"))

        if not stock_code:
            return AgentOutput(status="failure", error="stock_code is required")

        # 종목코드 → 고유번호 변환
        corp_code = self.dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            return AgentOutput(
                status="failure",
                error=f"Cannot find corp_code for stock {stock_code}"
            )

        # 공시 목록 조회
        disclosures = await self.dart_service.get_disclosure_list(
            corp_code, bgn_de=bgn_de, end_de=end_de, page_count=10
        )

        return AgentOutput(
            status="success",
            data={
                "stock_code": stock_code,
                "corp_code": corp_code,
                "count": len(disclosures) if disclosures else 0,
                "disclosures": disclosures[:10] if disclosures else [],
                "source": "DART"
            }
        )

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
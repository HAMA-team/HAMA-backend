"""
Portfolio 차트 관련 스키마

Frontend 차트 컴포넌트(Treemap, Pie, Bar)용 데이터 구조
"""
from pydantic import BaseModel, Field
from typing import List, Dict


class StockChartData(BaseModel):
    """차트용 종목 데이터"""
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    quantity: int = Field(..., description="보유 수량", ge=0)
    current_price: float = Field(..., description="현재가 (원)", ge=0)
    purchase_price: float = Field(..., description="매수가 (원)", ge=0)
    weight: float = Field(..., description="비중 (0~1)", ge=0, le=1)
    return_percent: float = Field(..., description="수익률 (%)")
    sector: str = Field(..., description="섹터")

    class Config:
        schema_extra = {
            "example": {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 10,
                "current_price": 76300,
                "purchase_price": 70000,
                "weight": 0.35,
                "return_percent": 9.0,
                "sector": "반도체"
            }
        }


class PortfolioChartData(BaseModel):
    """
    포트폴리오 차트 데이터

    Frontend Recharts 연동용 데이터 구조
    """
    stocks: List[StockChartData] = Field(..., description="보유 종목 목록")
    total_value: float = Field(..., description="총 평가금액 (원)", ge=0)
    total_return: float = Field(..., description="총 수익금 (원)")
    total_return_percent: float = Field(..., description="총 수익률 (%)")
    cash: float = Field(..., description="현금 보유액 (원)", ge=0)

    # 섹터별 비중 (원 그래프용)
    sectors: Dict[str, float] = Field(
        ...,
        description="섹터별 비중 (0~1)"
    )

    class Config:
        schema_extra = {
            "example": {
                "stocks": [
                    {
                        "stock_code": "005930",
                        "stock_name": "삼성전자",
                        "quantity": 10,
                        "current_price": 76300,
                        "purchase_price": 70000,
                        "weight": 0.35,
                        "return_percent": 9.0,
                        "sector": "반도체"
                    },
                    {
                        "stock_code": "000660",
                        "stock_name": "SK하이닉스",
                        "quantity": 5,
                        "current_price": 142000,
                        "purchase_price": 130000,
                        "weight": 0.30,
                        "return_percent": 9.2,
                        "sector": "반도체"
                    }
                ],
                "total_value": 10000000,
                "total_return": 900000,
                "total_return_percent": 9.0,
                "cash": 1000000,
                "sectors": {
                    "반도체": 0.65,
                    "배터리": 0.15,
                    "현금": 0.20
                }
            }
        }

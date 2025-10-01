"""
Stocks API endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import date

router = APIRouter()


class StockInfo(BaseModel):
    """Basic stock information"""
    stock_code: str
    stock_name: str
    market: str
    sector: Optional[str]
    current_price: Decimal
    change_rate: Decimal
    volume: int


class StockPrice(BaseModel):
    """Stock price data"""
    date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    """Search stocks by name or code"""
    # TODO: Implement actual stock search
    mock_results = [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "market": "KOSPI",
            "sector": "반도체",
            "current_price": Decimal("76000"),
            "change_rate": Decimal("0.02"),
            "volume": 12000000,
        }
    ]
    return {"results": mock_results, "total": 1}


@router.get("/{stock_code}", response_model=StockInfo)
async def get_stock_info(stock_code: str):
    """Get detailed stock information"""
    # TODO: Implement actual stock info retrieval
    if stock_code == "005930":
        return StockInfo(
            stock_code="005930",
            stock_name="삼성전자",
            market="KOSPI",
            sector="반도체",
            current_price=Decimal("76000"),
            change_rate=Decimal("0.02"),
            volume=12000000,
        )
    raise HTTPException(status_code=404, detail="Stock not found")


@router.get("/{stock_code}/price-history")
async def get_price_history(
    stock_code: str,
    days: int = Query(30, ge=1, le=365)
):
    """Get stock price history"""
    # TODO: Implement actual price history retrieval
    return {
        "stock_code": stock_code,
        "prices": [],
        "message": f"[MOCK] Price history for last {days} days"
    }


@router.get("/{stock_code}/analysis")
async def get_stock_analysis(stock_code: str):
    """
    Get comprehensive stock analysis
    This will trigger Research Agent
    """
    # TODO: Implement Research Agent call
    return {
        "stock_code": stock_code,
        "rating": 4,
        "recommendation": "BUY",
        "target_price": Decimal("85000"),
        "summary": "[MOCK] Analysis pending - Research Agent not yet implemented",
    }
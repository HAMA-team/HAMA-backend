"""
주식 데이터 관련 API 엔드포인트 모음
"""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from src.subgraphs.research_subgraph import research_agent
from src.services import stock_data_service

router = APIRouter()


class StockInfo(BaseModel):
    """주식 기본 정보"""

    stock_code: str
    stock_name: str
    market: str
    sector: Optional[str]
    current_price: Optional[Decimal]
    change_rate: Optional[Decimal]
    volume: Optional[int]


class StockPrice(BaseModel):
    """주가 데이터"""

    date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int


async def _latest_price(stock_code: str) -> Dict[str, Any]:
    """지정한 종목 코드의 최신 종가와 거래량을 조회합니다."""
    df = await stock_data_service.get_stock_price(stock_code, days=2)
    if df is None or df.empty:
        return {}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None
    close_price = float(latest["Close"])
    change_rate = None
    if prev is not None and prev["Close"]:
        change_rate = (close_price - float(prev["Close"])) / float(prev["Close"])

    return {
        "current_price": Decimal(str(close_price)),
        "volume": int(latest.get("Volume", 0)),
        "change_rate": Decimal(str(change_rate)) if change_rate is not None else None,
    }


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1), market: str = Query("KOSPI")):
    """종목명 또는 종목코드로 주식을 검색합니다."""
    df = await stock_data_service.get_stock_listing(market)
    if df is None or df.empty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="종목 목록을 조회할 수 없습니다.",
        )

    query = q.strip().upper()
    is_code = query.isdigit()

    if is_code:
        mask = df["Code"].str.contains(query, case=False, na=False)
    else:
        mask = df["Name"].str.contains(query, case=False, na=False)

    filtered = df[mask]
    if filtered.empty and not is_code:
        mask = df["Code"].str.contains(query, case=False, na=False)
        filtered = df[mask]

    matches = filtered.head(10)

    results: List[Dict[str, Any]] = []
    codes = matches["Code"].tolist()

    price_tasks = [asyncio.create_task(_latest_price(code)) for code in codes]
    price_results = await asyncio.gather(*price_tasks, return_exceptions=True)
    price_map: Dict[str, Dict[str, Any]] = {}
    for code, value in zip(codes, price_results):
        if isinstance(value, Exception):
            continue
        price_map[code] = value

    for _, row in matches.iterrows():
        code = row["Code"]
        price_payload = price_map.get(code, {})
        results.append(
            {
                "stock_code": code,
                "stock_name": row["Name"],
                "market": row.get("Market", market),
                "sector": row.get("Industry"),
                "current_price": price_payload.get("current_price"),
                "change_rate": price_payload.get("change_rate"),
                "volume": price_payload.get("volume"),
            }
        )

    return {"results": results, "total": int(filtered.shape[0])}


@router.get("/{stock_code}", response_model=StockInfo)
async def get_stock_info(stock_code: str, market: str = Query("KOSPI")):
    """특정 종목의 기본 정보를 조회합니다."""
    df = await stock_data_service.get_stock_listing(market)
    if df is None or df.empty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="종목 목록을 조회할 수 없습니다.",
        )

    match = df[df["Code"] == stock_code].head(1)
    if match.empty:
        raise HTTPException(status_code=404, detail="요청한 종목을 찾을 수 없습니다.")

    row = match.iloc[0]
    price_payload = await _latest_price(stock_code)

    return StockInfo(
        stock_code=stock_code,
        stock_name=row["Name"],
        market=row.get("Market", market),
        sector=row.get("Industry"),
        current_price=price_payload.get("current_price"),
        change_rate=price_payload.get("change_rate"),
        volume=price_payload.get("volume"),
    )


@router.get("/{stock_code}/price-history")
async def get_price_history(
    stock_code: str,
    days: int = Query(30, ge=1, le=365),
):
    """특정 종목의 기간별 주가 히스토리를 반환합니다."""
    df = await stock_data_service.get_stock_price(stock_code, days=days)
    if df is None or df.empty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="주가 히스토리를 조회할 수 없습니다.",
        )

    prices: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        prices.append(
            {
                "date": idx.date(),
                "open_price": Decimal(str(row["Open"])),
                "high_price": Decimal(str(row["High"])),
                "low_price": Decimal(str(row["Low"])),
                "close_price": Decimal(str(row["Close"])),
                "volume": int(row.get("Volume", 0)),
            }
        )

    return {
        "stock_code": stock_code,
        "prices": prices,
        "count": len(prices),
    }


@router.get("/{stock_code}/analysis")
async def get_stock_analysis(stock_code: str):
    """
    리서치 에이전트를 호출해 종합 종목 분석을 제공합니다.
    """
    try:
        result = await research_agent.ainvoke(
            {
                "stock_code": stock_code,
                "query": f"{stock_code} 분석",
                "messages": [HumanMessage(content=f"{stock_code} 종목 분석 요청")],
                "request_id": str(uuid4()),
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"리서치 에이전트를 사용할 수 없습니다: {exc}",
        ) from exc

    consensus = result.get("consensus")
    if not consensus:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research agent did not return a consensus",
        )

    return {
        "stock_code": stock_code,
        "recommendation": consensus.get("recommendation"),
        "target_price": consensus.get("target_price"),
        "current_price": consensus.get("current_price"),
        "upside_potential": consensus.get("upside_potential"),
        "confidence": consensus.get("confidence"),
        "bull_case": consensus.get("bull_case"),
        "bear_case": consensus.get("bear_case"),
        "summary": consensus.get("summary"),
    }

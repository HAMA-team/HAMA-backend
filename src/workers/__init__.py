"""
Workers: 단순 데이터 조회를 위한 경량 워커 모듈

LangGraph 서브그래프가 아닌, 빠른 API 호출로 단순 정보를 조회합니다.

Available Workers:
- market_data: 주가, 지수 등 시장 데이터 조회
"""

from src.workers.market_data import get_stock_price, get_index_price

__all__ = ["get_stock_price", "get_index_price"]

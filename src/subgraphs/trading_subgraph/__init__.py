"""
Trading Agent SubGraph 패키지 초기화
"""
from .graph import build_trading_subgraph

trading_subgraph = build_trading_subgraph().compile(name="trading_agent")

# 기존 명칭과의 호환성을 위해 alias 제공
trading_agent = trading_subgraph

__all__ = ["build_trading_subgraph", "trading_agent", "trading_subgraph"]

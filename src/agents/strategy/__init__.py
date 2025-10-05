"""Strategy Agent Module - 거시 대전략 수립 (LangGraph 서브그래프)"""

from .graph import strategy_subgraph

# Supervisor 패턴용 export (이미 컴파일된 서브그래프)
strategy_agent = strategy_subgraph

__all__ = ["strategy_agent"]

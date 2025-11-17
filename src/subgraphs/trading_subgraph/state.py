"""
Trading SubGraph State 정의.

기존 GraphState를 그대로 재사용하여 Supervisor와 동일한 상태를 공유합니다.
"""
from src.schemas.graph_state import GraphState

# 현재는 GraphState 전체를 그대로 사용하지만,
# 추후 Trading 전용 필드를 분리할 때를 대비해 별도 alias를 제공한다.
TradingState = GraphState

__all__ = ["TradingState"]

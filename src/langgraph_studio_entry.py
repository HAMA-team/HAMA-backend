"""
LangGraph Studio에서 사용할 Supervisor 그래프 엔트리 포인트.

LangGraph Studio는 자체적으로 persistence를 제공하므로,
커스텀 checkpointer를 사용하지 않습니다.
"""

from src.subgraphs.graph_master import build_graph

# LangGraph Studio는 자체 persistence를 제공하므로 checkpointer 미사용
graph = build_graph(automation_level=2, use_checkpointer=False)

__all__ = ["graph"]

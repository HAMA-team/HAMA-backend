"""
LangGraph Studio에서 사용할 Supervisor 그래프 엔트리 포인트.
"""

from src.subgraphs.graph_master import build_graph

# build_graph는 이미 compile된 상태를 반환합니다.
graph = build_graph(automation_level=2)

__all__ = ["graph"]

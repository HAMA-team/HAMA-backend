"""
LangGraph Studio에서 사용할 마스터 그래프 엔트리 포인트.
"""

from src.agents.graph_master import build_state_graph

# Studio 런타임은 자체적으로 체크포인터를 제공하므로, 별도 checkpointer를 넘기지 않는다.
graph = build_state_graph(automation_level=2).compile(name="master_graph_studio")

__all__ = ["graph"]

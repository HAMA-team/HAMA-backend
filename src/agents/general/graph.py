"""
General Agent 서브그래프 (ReAct 래퍼)
"""
from langgraph.graph import StateGraph, END

from .state import GeneralState
from .nodes import react_node


def build_general_subgraph():
    graph = StateGraph(GeneralState)
    graph.add_node("react", react_node)
    graph.set_entry_point("react")
    graph.add_edge("react", END)
    return graph.compile(name="general_agent")


general_subgraph = build_general_subgraph()

__all__ = ["general_subgraph"]

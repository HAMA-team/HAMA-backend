"""
General Agent Module - 일반 질의응답 (Langgraph 서브그래프)
"""
from .graph import general_subgraph

# Supervisor 패턴용 export (이미 컴파일된 서브그래프)
general_agent = general_subgraph

__all__ = ["general_agent"]

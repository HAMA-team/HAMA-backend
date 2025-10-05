"""
Risk Agent - LangGraph 서브그래프

리스크 평가 및 경고 시스템
"""
from src.agents.risk.graph import risk_subgraph

# Supervisor 패턴용 export (이미 컴파일된 서브그래프)
risk_agent = risk_subgraph

__all__ = ["risk_agent"]

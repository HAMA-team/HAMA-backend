"""Research Agent Module - 종목 심층 분석 (Langgraph 서브그래프)"""

from .graph import research_subgraph

# Supervisor 패턴용 export (이미 컴파일된 서브그래프)
research_agent = research_subgraph

__all__ = ["research_agent"]

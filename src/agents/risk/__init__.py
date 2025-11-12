"""
Risk Agent - Langgraph 서브그래프

리스크 평가 및 경고 시스템

⚠️ DEPRECATED: 이 모듈은 곧 제거될 예정입니다.
새로운 아키텍처에서는 calculate_portfolio_risk tool로 대체됩니다.
"""
import warnings

warnings.warn(
    "Risk Agent는 deprecated되었습니다. "
    "src/subgraphs/tools/risk_tools.py의 calculate_portfolio_risk tool로 마이그레이션하세요.",
    DeprecationWarning,
    stacklevel=2
)

from src.agents.risk.graph import risk_subgraph

# Supervisor 패턴용 export (이미 컴파일된 서브그래프)
risk_agent = risk_subgraph

__all__ = ["risk_agent"]

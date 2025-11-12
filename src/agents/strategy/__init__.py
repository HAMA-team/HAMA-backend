"""
Strategy Agent Module - 거시 대전략 수립 (Langgraph 서브그래프)

⚠️ DEPRECATED: 이 모듈은 곧 제거될 예정입니다.
새로운 아키텍처에서는 Quantitative SubGraph로 대체됩니다.
"""
import warnings

warnings.warn(
    "Strategy Agent는 deprecated되었습니다. "
    "Quantitative SubGraph로 마이그레이션하세요.",
    DeprecationWarning,
    stacklevel=2
)

from .graph import strategy_subgraph

# Supervisor 패턴용 export (이미 컴파일된 서브그래프)
strategy_agent = strategy_subgraph

__all__ = ["strategy_agent"]

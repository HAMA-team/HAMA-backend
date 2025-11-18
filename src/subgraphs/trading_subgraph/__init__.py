"""
Trading Agent SubGraph 패키지 초기화
"""
import logging

from .graph import build_trading_subgraph

logger = logging.getLogger(__name__)


def _create_trading_subgraph():
    """
    Trading SubGraph 생성 및 컴파일

    ⚠️ 중요: SubGraph는 checkpointer를 사용하지 않음!
    Master graph의 checkpointer를 상속하여 상태를 공유합니다.

    이렇게 하면:
    1. SubGraph의 interrupt는 Master graph의 checkpoint에 저장됨
    2. 같은 thread_id로 통신 가능
    3. /approve에서 Master graph astream만으로 충분
    """
    graph = build_trading_subgraph()

    try:
        # checkpointer를 사용하지 않고 compile (Master graph가 관리)
        compiled = graph.compile(name="trading_agent")
        logger.info("✅ [Trading SubGraph] Checkpointer 없이 컴파일 (Master graph 상속)")
    except Exception as exc:
        logger.warning("⚠️ [Trading SubGraph] 컴파일 실패: %s", exc)
        raise

    return compiled


trading_subgraph = _create_trading_subgraph()

# 기존 명칭과의 호환성을 위해 alias 제공
trading_agent = trading_subgraph

__all__ = ["build_trading_subgraph", "trading_agent", "trading_subgraph"]

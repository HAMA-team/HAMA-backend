"""
LangGraph Checkpointer 팩토리

환경에 따라 MemorySaver 또는 PostgresSaver를 제공
- Production/Demo: PostgresSaver (영속성)
- Development/Test: MemorySaver (빠른 개발)
"""
import logging
from functools import lru_cache
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from src.config.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_postgres_checkpointer() -> BaseCheckpointSaver:
    """
    PostgresSaver 인스턴스 생성 (싱글톤)

    Returns:
        PostgresSaver: PostgreSQL 기반 체크포인터

    Raises:
        ImportError: langgraph-checkpoint-postgres 미설치 시
        Exception: DB 연결 실패 시
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    db_uri = settings.database_url

    # 보안을 위해 호스트 정보만 로깅
    safe_uri = db_uri.split("@")[-1] if "@" in db_uri else "localhost"
    logger.info("🗄️  [Checkpointer] PostgresSaver 초기화: %s", safe_uri)

    # PostgresSaver 생성
    checkpointer = PostgresSaver.from_conn_string(db_uri)

    # 최초 실행 시 테이블 생성 (멱등성 보장)
    # 테이블: checkpoints, checkpoint_writes, checkpoint_blobs
    checkpointer.setup()

    logger.info("✅ [Checkpointer] PostgresSaver 설정 완료")

    return checkpointer


def get_checkpointer(use_postgres: Optional[bool] = None) -> BaseCheckpointSaver:
    """
    환경에 맞는 Checkpointer 반환

    Args:
        use_postgres: True면 PostgresSaver, False면 MemorySaver
                     None이면 환경변수 기반 자동 선택

    Returns:
        BaseCheckpointSaver: 체크포인터 인스턴스

    Examples:
        >>> # 자동 선택 (ENV 기반)
        >>> checkpointer = get_checkpointer()

        >>> # 명시적으로 Postgres 사용
        >>> checkpointer = get_checkpointer(use_postgres=True)

        >>> # 명시적으로 Memory 사용
        >>> checkpointer = get_checkpointer(use_postgres=False)
    """
    # 명시적 설정이 없으면 환경 기반 판단
    if use_postgres is None:
        # settings.USE_POSTGRES_CHECKPOINTER 우선, 없으면 ENV 기반
        if hasattr(settings, "USE_POSTGRES_CHECKPOINTER"):
            use_postgres = settings.USE_POSTGRES_CHECKPOINTER
        else:
            env = settings.ENV.lower()
            use_postgres = env in ["production", "prod", "demo"]

    if use_postgres:
        return _get_postgres_checkpointer()
    else:
        logger.info("💾 [Checkpointer] MemorySaver 사용 (개발/테스트 모드)")
        return MemorySaver()
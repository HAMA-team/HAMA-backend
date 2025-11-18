"""
LangGraph Checkpointer for PostgreSQL (AsyncPostgresSaver 기반)

PostgreSQL 기반 비동기 checkpointer만 제공
- AsyncPostgresSaver 공식 구현 사용 (LangGraph 1.0.52+)
- 동기/비동기 그래프 모두 지원
- 싱글톤 패턴으로 인스턴스 재사용
"""
import logging
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.config.settings import settings

logger = logging.getLogger(__name__)

# 싱글톤 인스턴스
_checkpointer_instance: Optional[AsyncPostgresSaver] = None
_checkpointer_cm = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    AsyncPostgresSaver 인스턴스 생성 (싱글톤)

    동기/비동기 그래프 모두 사용 가능합니다.

    Returns:
        AsyncPostgresSaver: PostgreSQL 기반 비동기 체크포인터

    Raises:
        ImportError: langgraph-checkpoint-postgres 미설치 시
        RuntimeError: PostgreSQL 연결 실패 시
    Note:
        이 함수는 context manager를 내부적으로 관리하여
        PostgreSQL 연결을 유지합니다. 애플리케이션 종료 시
        close_checkpointer()를 호출해야 합니다.
    """
    global _checkpointer_instance, _checkpointer_cm

    # 이미 초기화된 경우 재사용
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as APS
    except ImportError as e:
        logger.error("❌ [Checkpointer] langgraph-checkpoint-postgres 패키지가 설치되지 않았습니다")
        raise ImportError(
            "langgraph-checkpoint-postgres 패키지가 필요합니다. "
            "다음 명령어로 설치하세요: pip install langgraph-checkpoint-postgres"
        ) from e

    db_uri = settings.database_url

    # 보안을 위해 호스트 정보만 로깅
    safe_uri = db_uri.split("@")[-1] if "@" in db_uri else "localhost"
    logger.info("🗄️  [Checkpointer] AsyncPostgresSaver 초기화: %s", safe_uri)

    try:
        # Context manager 생성 및 진입 (비동기)
        _checkpointer_cm = APS.from_conn_string(db_uri)
        _checkpointer_instance = await _checkpointer_cm.__aenter__()

        # 최초 실행 시 테이블 생성 (멱등성 보장)
        # 테이블: checkpoints, checkpoint_writes, checkpoint_blobs
        await _checkpointer_instance.setup()

        logger.info("✅ [Checkpointer] AsyncPostgresSaver 설정 완료")

        return _checkpointer_instance
    except Exception as e:
        logger.error("❌ [Checkpointer] PostgreSQL 연결 실패: %s", str(e))
        # 연결 실패 시 context manager 정리
        if _checkpointer_cm is not None:
            try:
                await _checkpointer_cm.__aexit__(None, None, None)
            except:
                pass
            _checkpointer_cm = None
            _checkpointer_instance = None

        raise RuntimeError(
            f"PostgreSQL checkpointer 초기화 실패: {str(e)}\n"
            f"DATABASE_URL 환경변수를 확인하세요: {safe_uri}"
        ) from e


async def close_checkpointer():
    """
    Checkpointer 연결 종료 (애플리케이션 종료 시 호출)

    이 함수는 애플리케이션 shutdown 단계에서 명시적으로 호출되어야 합니다.

    Examples:
        >>> @app.on_event("shutdown")
        >>> async def shutdown():
        ...     await close_checkpointer()
    """
    global _checkpointer_instance, _checkpointer_cm

    if _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
            logger.info("✅ [Checkpointer] PostgreSQL 연결 종료")
        except Exception as e:
            logger.warning("⚠️  [Checkpointer] 연결 종료 중 오류: %s", str(e))
        finally:
            _checkpointer_cm = None
            _checkpointer_instance = None
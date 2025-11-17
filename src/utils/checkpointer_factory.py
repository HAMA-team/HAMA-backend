"""
LangGraph Checkpointer for PostgreSQL

PostgreSQL 기반 영속성 checkpointer만 제공
- MemorySaver는 제거됨 (LangGraph Studio와 충돌)
- Fallback 없이 PostgreSQL 연결 실패 시 에러 반환
- 동기/비동기 checkpointer 모두 지원
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Sequence

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple

from src.config.settings import settings

logger = logging.getLogger(__name__)

# 전역 checkpointer 및 context manager 유지 (동기식)
_checkpointer_cm = None
_checkpointer_instance = None

# 비동기 checkpointer (astream_events용)
_async_checkpointer_cm = None
_async_checkpointer_instance = None


def get_checkpointer() -> BaseCheckpointSaver:
    """
    PostgresSaver 인스턴스 생성 (싱글톤)

    Returns:
        PostgresSaver: PostgreSQL 기반 체크포인터

    Raises:
        ImportError: langgraph-checkpoint-postgres 미설치 시
        Exception: DB 연결 실패 시

    Examples:
        >>> checkpointer = get_checkpointer()

    Note:
        이 함수는 context manager를 내부적으로 관리하여
        PostgreSQL 연결을 유지합니다.
    """
    global _checkpointer_cm, _checkpointer_instance

    # 이미 초기화된 경우 재사용
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError as e:
        logger.error("❌ [Checkpointer] langgraph-checkpoint-postgres 패키지가 설치되지 않았습니다")
        raise ImportError(
            "langgraph-checkpoint-postgres 패키지가 필요합니다. "
            "다음 명령어로 설치하세요: pip install langgraph-checkpoint-postgres"
        ) from e

    class AsyncReadyPostgresSaver(PostgresSaver):
        """PostgresSaver에 async API를 얇게 래핑해 ainvoke 경로에서 재사용한다."""

        async def aget_tuple(self, config) -> CheckpointTuple | None:
            return await asyncio.to_thread(PostgresSaver.get_tuple, self, config)

        async def alist(
            self,
            config,
            *,
            filter: dict[str, Any] | None = None,
            before=None,
            limit: int | None = None,
        ) -> AsyncIterator[CheckpointTuple]:
            def _load_list():
                return list(
                    PostgresSaver.list(
                        self,
                        config,
                        filter=filter,
                        before=before,
                        limit=limit,
                    )
                )

            rows = await asyncio.to_thread(_load_list)
            for row in rows:
                yield row

        async def aput(self, config, checkpoint, metadata, new_versions):
            return await asyncio.to_thread(
                PostgresSaver.put,
                self,
                config,
                checkpoint,
                metadata,
                new_versions,
            )

        async def aput_writes(
            self,
            config,
            writes: Sequence[tuple[str, Any]],
            task_id: str,
            task_path: str = "",
        ) -> None:
            await asyncio.to_thread(
                PostgresSaver.put_writes,
                self,
                config,
                writes,
                task_id,
                task_path,
            )

        async def adelete_thread(self, thread_id: str) -> None:
            await asyncio.to_thread(PostgresSaver.delete_thread, self, thread_id)

    db_uri = settings.database_url

    # 보안을 위해 호스트 정보만 로깅
    safe_uri = db_uri.split("@")[-1] if "@" in db_uri else "localhost"
    logger.info("🗄️  [Checkpointer] PostgresSaver 초기화: %s", safe_uri)

    try:
        # Context manager 생성 및 진입
        _checkpointer_cm = AsyncReadyPostgresSaver.from_conn_string(db_uri)
        _checkpointer_instance = _checkpointer_cm.__enter__()

        # 최초 실행 시 테이블 생성 (멱등성 보장)
        # 테이블: checkpoints, checkpoint_writes, checkpoint_blobs
        _checkpointer_instance.setup()

        logger.info("✅ [Checkpointer] PostgresSaver 설정 완료")

        return _checkpointer_instance
    except Exception as e:
        logger.error("❌ [Checkpointer] PostgreSQL 연결 실패: %s", str(e))
        # 연결 실패 시 context manager 정리
        if _checkpointer_cm is not None:
            try:
                _checkpointer_cm.__exit__(None, None, None)
            except:
                pass
            _checkpointer_cm = None
            _checkpointer_instance = None

        raise RuntimeError(
            f"PostgreSQL checkpointer 초기화 실패: {str(e)}\n"
            f"DATABASE_URL 환경변수를 확인하세요: {safe_uri}"
        ) from e


async def get_async_checkpointer():
    """
    AsyncPostgresSaver 인스턴스 생성 (싱글톤)

    astream_events 등 비동기 LangGraph API에서 사용합니다.

    Returns:
        AsyncPostgresSaver: 비동기 PostgreSQL 기반 체크포인터

    Raises:
        ImportError: langgraph-checkpoint-postgres 미설치 시
        Exception: DB 연결 실패 시

    Examples:
        >>> checkpointer = await get_async_checkpointer()
    """
    global _async_checkpointer_cm, _async_checkpointer_instance

    # 이미 초기화된 경우 재사용
    if _async_checkpointer_instance is not None:
        return _async_checkpointer_instance

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as e:
        logger.error("❌ [AsyncCheckpointer] langgraph-checkpoint-postgres 패키지가 설치되지 않았습니다")
        raise ImportError(
            "langgraph-checkpoint-postgres 패키지가 필요합니다. "
            "다음 명령어로 설치하세요: pip install langgraph-checkpoint-postgres"
        ) from e

    db_uri = settings.database_url

    # 보안을 위해 호스트 정보만 로깅
    safe_uri = db_uri.split("@")[-1] if "@" in db_uri else "localhost"
    logger.info("🗄️  [AsyncCheckpointer] AsyncPostgresSaver 초기화: %s", safe_uri)

    try:
        # Context manager 생성 및 진입 (비동기)
        _async_checkpointer_cm = AsyncPostgresSaver.from_conn_string(db_uri)
        _async_checkpointer_instance = await _async_checkpointer_cm.__aenter__()

        # 최초 실행 시 테이블 생성 (멱등성 보장)
        await _async_checkpointer_instance.setup()

        logger.info("✅ [AsyncCheckpointer] AsyncPostgresSaver 설정 완료")

        return _async_checkpointer_instance
    except Exception as e:
        logger.error("❌ [AsyncCheckpointer] PostgreSQL 연결 실패: %s", str(e))
        # 연결 실패 시 context manager 정리
        if _async_checkpointer_cm is not None:
            try:
                await _async_checkpointer_cm.__aexit__(None, None, None)
            except:
                pass
            _async_checkpointer_cm = None
            _async_checkpointer_instance = None

        raise RuntimeError(
            f"AsyncPostgresSaver 초기화 실패: {str(e)}\n"
            f"DATABASE_URL 환경변수를 확인하세요: {safe_uri}"
        ) from e


def close_checkpointer():
    """
    Checkpointer 연결 종료 (애플리케이션 종료 시 호출)

    이 함수는 일반적으로 필요하지 않지만,
    테스트나 애플리케이션 종료 시 명시적으로 연결을 닫을 때 사용할 수 있습니다.
    """
    global _checkpointer_cm, _checkpointer_instance

    if _checkpointer_cm is not None:
        try:
            _checkpointer_cm.__exit__(None, None, None)
            logger.info("✅ [Checkpointer] PostgreSQL 연결 종료")
        except Exception as e:
            logger.warning("⚠️  [Checkpointer] 연결 종료 중 오류: %s", str(e))
        finally:
            _checkpointer_cm = None
            _checkpointer_instance = None


async def close_async_checkpointer():
    """
    비동기 Checkpointer 연결 종료 (애플리케이션 종료 시 호출)
    """
    global _async_checkpointer_cm, _async_checkpointer_instance

    if _async_checkpointer_cm is not None:
        try:
            await _async_checkpointer_cm.__aexit__(None, None, None)
            logger.info("✅ [AsyncCheckpointer] PostgreSQL 연결 종료")
        except Exception as e:
            logger.warning("⚠️  [AsyncCheckpointer] 연결 종료 중 오류: %s", str(e))
        finally:
            _async_checkpointer_cm = None
            _async_checkpointer_instance = None

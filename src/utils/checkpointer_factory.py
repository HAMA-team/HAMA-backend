"""
LangGraph Checkpointer for PostgreSQL

PostgreSQL 기반 영속성 checkpointer만 제공
- MemorySaver는 제거됨 (LangGraph Studio와 충돌)
- Fallback 없이 PostgreSQL 연결 실패 시 에러 반환
"""
import logging

from langgraph.checkpoint.base import BaseCheckpointSaver

from src.config.settings import settings

logger = logging.getLogger(__name__)

# 전역 checkpointer 및 context manager 유지
_checkpointer_cm = None
_checkpointer_instance = None


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

    db_uri = settings.database_url

    # 보안을 위해 호스트 정보만 로깅
    safe_uri = db_uri.split("@")[-1] if "@" in db_uri else "localhost"
    logger.info("🗄️  [Checkpointer] PostgresSaver 초기화: %s", safe_uri)

    try:
        # Context manager 생성 및 진입
        _checkpointer_cm = PostgresSaver.from_conn_string(db_uri)
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
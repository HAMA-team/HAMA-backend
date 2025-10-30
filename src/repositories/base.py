"""
공통 Repository 유틸리티
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator

from sqlalchemy.orm import Session


class BaseRepository:
    """SQLAlchemy 세션 관리를 담당하는 기본 Repository."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """트랜잭션 스코프 컨텍스트 매니저."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

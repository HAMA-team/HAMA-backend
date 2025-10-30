"""
Database configuration and session management
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
from src.config.settings import settings

DATABASE_URL = settings.database_url


def _create_engine() -> Engine:
    """PostgreSQL 엔진 생성"""
    return create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=settings.DB_ECHO,  # DB 로그는 별도로 제어
    )


# Create database engine
engine = _create_engine()

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Database session dependency for FastAPI
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Session:
    """동기 컨텍스트 매니저로 DB 세션 제공"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    # Ensure models are registered before creating tables
    import src.models.portfolio  # noqa: F401
    import src.models.stock  # noqa: F401
    import src.models.user  # noqa: F401
    import src.models.agent  # noqa: F401
    import src.models.chat  # noqa: F401
    import src.models.macro  # noqa: F401

    Base.metadata.create_all(bind=engine)

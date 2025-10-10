"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from src.config.settings import settings

DATABASE_URL = settings.database_url


def _create_engine() -> Engine:
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
        )

    return create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=settings.DEBUG,
    )


# Create database engine
engine = _create_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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


def init_db():
    """Initialize database - create all tables"""
    if engine.dialect.name == "sqlite":
        # SQLite tests only require chat history tables
        import src.models.chat  # noqa: F401
    else:
        # Ensure models are registered before creating tables for production databases
        import src.models.portfolio  # noqa: F401
        import src.models.stock  # noqa: F401
        import src.models.user  # noqa: F401
        import src.models.agent  # noqa: F401
        import src.models.chat  # noqa: F401

    Base.metadata.create_all(bind=engine)

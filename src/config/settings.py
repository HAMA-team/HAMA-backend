"""
Application configuration and settings
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "HAMA"
    ENV: str = "development"
    DEBUG: bool = True
    API_VERSION: str = "v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/hama_db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # LLM APIs
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str | None = None
    DEFAULT_LLM_MODEL: str = "claude-sonnet-4-5-20250929"
    CLAUDE_MODEL: str = "claude-sonnet-4-5-20250929"

    # LLM Settings
    LLM_TIMEOUT: int = 30
    MAX_TOKENS: int = 4000
    LLM_TEMPERATURE: float = 0.1

    # GPT-5 nano Settings (Intent & Supervisor)
    INTENT_MODEL: str = "gpt-5-nano"
    SUPERVISOR_MODEL: str = "gpt-5-nano"
    INTENT_REASONING_EFFORT: str = "minimal"
    SUPERVISOR_REASONING_EFFORT: str = "low"

    # DART API
    DART_API_KEY: str

    # KIS API (Phase 2)
    KIS_APP_KEY: str | None = None
    KIS_APP_SECRET: str | None = None
    KIS_ACCOUNT_NUMBER: str | None = None

    # JWT (Phase 2)
    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Vector DB (Phase 2)
    PINECONE_API_KEY: str | None = None
    PINECONE_ENVIRONMENT: str | None = None
    QDRANT_URL: str = "http://localhost:6333"

    # Redis (Phase 2)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Caching (TTL in seconds)
    CACHE_TTL_MARKET_DATA: int = 60
    CACHE_TTL_NEWS: int = 300
    CACHE_TTL_FINANCIAL_STATEMENTS: int = 86400
    CACHE_TTL_ANALYSIS_RESULTS: int = 3600

    # LangSmith (Optional)
    LANGSMITH_API_KEY: str | None = None
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_PROJECT: str = "hama-backend"

    # Celery (Phase 2)
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Monitoring (Phase 2)
    PROMETHEUS_PORT: int = 8001
    GRAFANA_URL: str = "http://localhost:3000"

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
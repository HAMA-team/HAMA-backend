"""
Application configuration and settings
"""
import os
import uuid
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    DEMO_USER_ID: str = "3bd04ffb-350a-5fa4-bee5-6ce019fdad9c"

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/hama_db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    @property
    def database_url(self) -> str:
        """환경과 관계없이 기본적으로 PostgreSQL URL을 사용합니다."""
        env = os.getenv("ENV", self.ENV).lower()
        if env == "test":
            return os.getenv("TEST_DATABASE_URL", self.DATABASE_URL)
        return os.getenv("DATABASE_URL", self.DATABASE_URL)

    # LLM APIs
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"  # .env에서 오버라이드 가능
    ANTHROPIC_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash-exp"

    # LLM Mode: "test" (Gemini) or "production" (Claude)
    LLM_MODE: str = "production"  # test, production, demo 등

    # Router 전용 모델 (빠른 라우팅을 위해 경량 모델 사용)
    ROUTER_MODEL_PROVIDER: str = "anthropic"  # anthropic, openai, google
    ROUTER_MODEL: str = "claude-haiku-4-5-20251001"

    # LLM Settings
    LLM_TIMEOUT: int = 30
    MAX_TOKENS: int = 4000
    LLM_TEMPERATURE: float = 0.1

    @property
    def llm_provider(self) -> str:
        """현재 LLM 모드에 따라 사용할 프로바이더 반환"""
        mode = os.getenv("LLM_MODE", self.LLM_MODE).lower()

        # 명시적으로 provider 지정한 경우
        if mode in ["openai", "gpt"]:
            return "openai"
        elif mode in ["anthropic", "claude"]:
            return "anthropic"
        elif mode in ["google", "gemini"]:
            return "google"

        # 레거시 모드 매핑
        if mode in ["production", "prod", "demo"]:
            return "anthropic"
        else:  # test, development 등
            return "google"

    @property
    def llm_model_name(self) -> str:
        """현재 프로바이더에 맞는 모델명 반환"""
        provider = self.llm_provider
        if provider == "anthropic":
            return self.CLAUDE_MODEL
        elif provider == "google":
            return self.GEMINI_MODEL
        elif provider == "openai":
            return self.OPENAI_MODEL  # OpenAI 모델 사용
        else:
            return self.CLAUDE_MODEL  # fallback

    # GPT-5 nano Settings (Intent & Supervisor)
    INTENT_MODEL: str = "gpt-5-nano"
    SUPERVISOR_MODEL: str = "gpt-5-nano"
    INTENT_REASONING_EFFORT: str = "minimal"
    SUPERVISOR_REASONING_EFFORT: str = "low"

    # DART API
    DART_API_KEY: str = ""

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
    CACHE_TTL_MARKET_DATA: int = 60  # 개별 종목 주가 데이터
    CACHE_TTL_MARKET_INDEX: int = 3600  # 시장 지수 (KOSPI, KOSDAQ 등) - Rate Limit 방지
    CACHE_TTL_REALTIME_PRICE: int = 120  # 실시간 주가 (Celery Worker 갱신)
    CACHE_TTL_NEWS: int = 300
    CACHE_TTL_FINANCIAL_STATEMENTS: int = 86400
    CACHE_TTL_ANALYSIS_RESULTS: int = 3600

    # LangSmith (Optional)
    LANGSMITH_API_KEY: str | None = None
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_PROJECT: str = "hama-backend"

    # Celery (실시간 데이터 수집)
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_REALTIME_UPDATE_INTERVAL: int = 60  # 실시간 데이터 업데이트 주기 (초)
    CELERY_BATCH_SIZE: int = 50  # 배치당 종목 수 (Rate Limit 관리)

    # Monitoring (Phase 2)
    PROMETHEUS_PORT: int = 8001
    GRAFANA_URL: str = "http://localhost:3000"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Langgraph persistence
    LANGGRAPH_CHECKPOINT_TTL_MINUTES: int = 43200  # 30일
    LANGGRAPH_CHECKPOINT_REFRESH_ON_READ: bool = True
    GRAPH_CHECKPOINT_BACKEND: str = "memory"  # memory | redis (비동기 구조 개선 후)
    # Note: Redis/PostgreSQL checkpointer는 비동기 context manager로 구현되어
    # 현재 동기 캐싱 구조에서는 사용 복잡. 추후 비동기 초기화로 개선 예정 (Phase 2)

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def demo_user_uuid(self) -> uuid.UUID:
        """프로토타입 데모 계정 UUID를 UUID 객체로 반환"""
        return uuid.UUID(self.DEMO_USER_ID)

    @property
    def langgraph_default_ttl(self) -> int:
        """환경에 따라 Langgraph 체크포인트 TTL(분)을 조정"""
        env = os.getenv("ENV", self.ENV).lower()
        if env == "test":
            return min(self.LANGGRAPH_CHECKPOINT_TTL_MINUTES, 120)
        return self.LANGGRAPH_CHECKPOINT_TTL_MINUTES

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",  # .env의 추가 필드 무시
    )


# Global settings instance
settings = Settings()

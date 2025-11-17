"""
Application configuration and settings
"""
import os
import uuid
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


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
    DATABASE_URL: str = ""  # 환경변수 필수
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False  # SQLAlchemy 쿼리 로그 출력 여부 (개발 시 True로 변경 가능)

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

    # LLM Mode: openai (기본), anthropic, google 등
    LLM_MODE: str = "anthropic"  # openai, anthropic (기본), google 등

    # Router 전용 모델 (정확한 라우팅을 위해 강력한 모델 사용)
    ROUTER_MODEL_PROVIDER: str = "anthropic"  # anthropic (기본), openai, google
    ROUTER_MODEL: str = "claude-haiku-4-5-20251001"  # 종목명 인식 개선을 위해 Claude 사용


    # Web Search
    ENABLE_WEB_SEARCH: bool = True
    WEB_SEARCH_MAX_RESULTS: int = 5
    WEB_SEARCH_TIMEOUT: float = 8.0
    WEB_SEARCH_REGION: str = "kr-kr"

    # LLM Settings
    LLM_TIMEOUT: int = 30
    MAX_TOKENS: int = 4000
    LLM_TEMPERATURE: float = 0.1

    @property
    def llm_provider(self) -> str:
        """현재 LLM 모드에 따라 사용할 프로바이더 반환

        기본 우선순위: OpenAI → Claude (Anthropic)
        """
        mode = os.getenv("LLM_MODE", self.LLM_MODE).lower()

        # 명시적으로 provider 지정한 경우
        if mode in ["openai", "gpt"]:
            return "openai"
        elif mode in ["anthropic", "claude"]:
            return "anthropic"
        elif mode in ["google", "gemini"]:
            return "google"

        # 레거시 모드 매핑 (기본값: Claude 우선)
        # production, demo 등 모든 환경에서 Claude를 기본으로 사용
        return "anthropic"

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

    # DART API
    DART_API_KEY: str = ""

    # BOK API
    BOK_API_KEY: str = ""

    # 네이버 검색 API
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    BOK_BASE_URL: str = "https://ecos.bok.or.kr/api"

    # KIS API (Phase 2)
    KIS_APP_KEY: str | None = None
    KIS_APP_SECRET: str | None = None
    KIS_ACCOUNT_NUMBER: str | None = None
    KIS_TOKEN_CACHE_PATH: str | None = ".cache/kis_token.json"

    @property
    def kis_token_cache_path(self) -> Path | None:
        """KIS 토큰 캐시 파일 경로를 반환합니다."""
        path = (self.KIS_TOKEN_CACHE_PATH or "").strip()
        if not path:
            return None
        return Path(path).expanduser()

    # LangSmith (Optional)
    LANGSMITH_API_KEY: str | None = None
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_PROJECT: str = "hama-backend"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Langgraph persistence
    # PostgreSQL checkpointer만 지원 (MemorySaver 제거됨)
    # LangGraph Studio는 자체 persistence를 제공하므로 use_checkpointer=False 사용
    LANGGRAPH_CHECKPOINT_TTL_MINUTES: int = 43200  # 30일
    LANGGRAPH_CHECKPOINT_REFRESH_ON_READ: bool = True

    # CORS
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:8000,"
        "http://127.0.0.1:3000,"
        "http://0.0.0.0:3000"
    )
    CORS_ORIGIN_REGEX: str = (
        r"https://.*\.vercel\.app$|"
        r"http://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$|"
        r"http://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$|"
        r"http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cors_origin_regex(self) -> Optional[str]:
        """Return combined CORS origin regex pattern or None"""
        value = (self.CORS_ORIGIN_REGEX or "").strip()
        return value or None

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

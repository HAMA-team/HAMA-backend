"""
LLM Provider Factory

테스트/개발 환경에서는 Gemini를 사용하고,
프로덕션/데모 환경에서는 Claude를 사용하도록 자동 전환
"""
import asyncio
import logging
import threading
from functools import lru_cache
from typing import Optional

try:
    from redis.exceptions import ResponseError as RedisResponseError
except Exception:  # redis가 선택적 의존성인 환경 지원
    RedisResponseError = None

from langchain_anthropic import ChatAnthropic
from langchain_core.caches import InMemoryCache
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.config.settings import settings

logger = logging.getLogger(__name__)

# 캐시 초기화 상태 플래그
_cache_initialized = False


def _loop_token() -> str:
    """
    현재 실행 중인 이벤트 루프(또는 스레드)를 식별하기 위한 토큰 반환.

    gRPC 기반 LLM들은 이벤트 루프에 종속적인 리소스를 사용하므로,
    서로 다른 루프 간에 인스턴스를 공유하면 'Event loop is closed' 오류가 발생할 수 있다.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 동기 컨텍스트에서는 스레드 ID 기준으로 격리
        return f"sync-{threading.get_ident()}"
    return f"loop-{id(loop)}"


@lru_cache(maxsize=16)
def _build_llm(
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    loop_token: str,
) -> BaseChatModel:
    """
    LLM 인스턴스를 생성하고 캐싱합니다.

    동일한 설정(provider, model, temperature, max_tokens, loop_token)에 대해서는
    캐시된 인스턴스를 재사용하여 초기화 비용을 줄입니다.
    """
    logger.info(
        "🤖 LLM 초기화: provider=%s, model=%s, temperature=%s, max_tokens=%s, loop=%s",
        provider,
        model_name,
        temperature,
        max_tokens,
        loop_token,
    )

    if provider == "anthropic":
        # Claude 프롬프트 캐싱 활성화
        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.ANTHROPIC_API_KEY,
            default_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )

    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=settings.GEMINI_API_KEY,
        )

    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.OPENAI_API_KEY,
        )

    raise ValueError(f"지원하지 않는 LLM provider: {provider}")


def get_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """
    LLM 모드에 따라 적절한 LLM 인스턴스 반환

    기본 우선순위: OpenAI → Claude (Anthropic) → Gemini (Google)
    - 환경 변수 LLM_MODE로 provider를 명시할 수 있음
    - API 키가 없으면 자동으로 폴백
    """
    requested_provider = settings.llm_provider
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else settings.llm_model_name

    provider = requested_provider

    # 폴백 체인: OpenAI → Claude → Gemini
    if provider == "openai" and not settings.OPENAI_API_KEY:
        logger.warning(
            "⚠️ OPENAI_API_KEY가 설정되지 않았습니다. Claude로 폴백합니다."
        )
        provider = "anthropic"

    if provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
        logger.warning(
            "⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다. Gemini로 폴백합니다."
        )
        provider = "google"

    # 최종 검증
    if provider == "openai" and not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    if provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    if provider == "google" and not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm(provider, model_name, float(temp), int(tokens), loop_token)


def get_claude_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatAnthropic:
    """강제로 Claude 사용 (모드 무시)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else settings.CLAUDE_MODEL

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("anthropic", model_name, float(temp), int(tokens), loop_token)


def get_openai_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatOpenAI:
    """강제로 OpenAI 사용 (모드 무시)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else "gpt-4o-mini"

    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("openai", model_name, float(temp), int(tokens), loop_token)


def get_gemini_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatGoogleGenerativeAI:
    """강제로 Gemini 사용 (모드 무시)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else settings.GEMINI_MODEL

    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("google", model_name, float(temp), int(tokens), loop_token)


def get_research_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatAnthropic:
    """Research Agent 전용 LLM (Claude Haiku 4.5 - 프롬프트 캐싱 활성화)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("anthropic", model_name, float(temp), int(tokens), loop_token)


def get_router_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatAnthropic:
    """Router Agent 전용 LLM (Claude Haiku 4.5 - 프롬프트 캐싱 활성화)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("anthropic", model_name, float(temp), int(tokens), loop_token)


def get_strategy_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatAnthropic:
    """Strategy Agent 전용 LLM (Claude Haiku 4.5 - 프롬프트 캐싱 활성화)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("anthropic", model_name, float(temp), int(tokens), loop_token)


def get_portfolio_risk_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatAnthropic:
    """Portfolio/Risk Agent 전용 LLM (Claude Haiku 4.5 - 프롬프트 캐싱 활성화)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("anthropic", model_name, float(temp), int(tokens), loop_token)


def get_default_agent_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    """기본 에이전트 LLM (GPT-5-mini)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = "gpt-5-mini"  # GPT-5-mini

    if not settings.OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("openai", model_name, float(temp), int(tokens), loop_token)


def initialize_semantic_cache():
    """
    RedisSemanticCache를 초기화하여 LLM 응답 캐싱을 활성화합니다.

    이 함수는 애플리케이션 시작 시 한 번만 호출되어야 합니다.
    의미적으로 유사한 질문에 대해 캐시된 응답을 재사용하여 LLM 호출을 줄입니다.

    설정:
    - ENABLE_SEMANTIC_CACHE: 캐시 활성화 여부
    - REDIS_URL: Redis 서버 주소
    - SEMANTIC_CACHE_DISTANCE_THRESHOLD: 유사도 임계값 (0.1~0.3 권장)
    - SEMANTIC_CACHE_TTL: 캐시 만료 시간(초)
    """
    global _cache_initialized

    if _cache_initialized:
        logger.info("✅ [Cache] RedisSemanticCache가 이미 초기화되었습니다.")
        return

    if not settings.ENABLE_SEMANTIC_CACHE:
        logger.info("⏭️ [Cache] SemanticCache가 비활성화되어 있습니다.")
        return

    try:
        from langchain_core.globals import set_llm_cache
        from langchain_openai import OpenAIEmbeddings
        from langchain_redis import RedisSemanticCache

        # OpenAI 임베딩 초기화 (의미 유사도 계산용)
        embeddings = OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-ada-002"
        )

        # RedisSemanticCache 초기화
        semantic_cache = RedisSemanticCache(
            redis_url=settings.REDIS_URL,
            embeddings=embeddings,
            distance_threshold=settings.SEMANTIC_CACHE_DISTANCE_THRESHOLD,
            ttl=settings.SEMANTIC_CACHE_TTL,
        )

        # 전역 LLM 캐시 설정
        set_llm_cache(semantic_cache)

        _cache_initialized = True

        logger.info(
            "✅ [Cache] RedisSemanticCache 초기화 완료 "
            "(threshold=%.2f, ttl=%ds)",
            settings.SEMANTIC_CACHE_DISTANCE_THRESHOLD,
            settings.SEMANTIC_CACHE_TTL,
        )

    except ImportError as e:
        logger.error(
            "❌ [Cache] RedisSemanticCache 초기화 실패: 필요한 패키지가 없습니다. "
            "langchain-redis를 설치하세요. (%s)",
            e,
        )
    except Exception as e:
        message = str(e)
        if (
            RedisResponseError is not None
            and isinstance(e, RedisResponseError)
            and "FT._LIST" in message
        ):
            logger.info(
                "ℹ️ [Cache] RediSearch 모듈을 찾을 수 없습니다. "
                "벡터 인덱스를 사용하지 않는 RedisCache로 폴백합니다. (redis_url=%s)",
                settings.REDIS_URL,
            )
            try:
                import redis
                from langchain_community.cache import RedisCache

                redis_client = redis.from_url(settings.REDIS_URL)
                basic_cache = RedisCache(
                    redis_=redis_client,
                    ttl=settings.SEMANTIC_CACHE_TTL or None,
                )
                set_llm_cache(basic_cache)
                logger.info(
                    "✅ [Cache] RedisCache 초기화 완료 (key-value fallback, ttl=%s)",
                    settings.SEMANTIC_CACHE_TTL or "∞",
                )
            except Exception as fallback_error:
                logger.warning(
                    "⚠️ [Cache] RedisCache 폴백에도 실패했습니다. InMemoryCache로 전환합니다. (%s)",
                    fallback_error,
                )
                set_llm_cache(InMemoryCache())
                logger.info("✅ [Cache] InMemoryCache 초기화 완료 (semantic cache fallback)")

            _cache_initialized = True
            return

        logger.error(
            "❌ [Cache] RedisSemanticCache 초기화 실패: %s",
            message,
            exc_info=True,
        )

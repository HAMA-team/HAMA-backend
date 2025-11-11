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

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.config.settings import settings

logger = logging.getLogger(__name__)


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
    model_name = model if model is not None else "gpt-5-chat-latest"

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
) -> ChatAnthropic:
    """기본 에이전트 LLM (Claude Haiku 4.5)"""
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = settings.CLAUDE_MODEL

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    loop_token = _loop_token()
    return _build_llm("anthropic", model_name, float(temp), int(tokens), loop_token)

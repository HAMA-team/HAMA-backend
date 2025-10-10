"""
LLM Provider Factory

테스트/개발 환경에서는 Gemini를 사용하고,
프로덕션/데모 환경에서는 Claude를 사용하도록 자동 전환
"""
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import settings

logger = logging.getLogger(__name__)


def get_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """
    LLM 모드에 따라 적절한 LLM 인스턴스 반환

    환경 변수 LLM_MODE에 따라:
    - "production", "prod", "demo" → Claude (Anthropic)
    - 그 외 (test, development) → Gemini (Google)

    Args:
        temperature: LLM temperature (기본값: settings.LLM_TEMPERATURE)
        max_tokens: 최대 토큰 수 (기본값: settings.MAX_TOKENS)
        model: 모델 이름 (기본값: 자동 선택)

    Returns:
        BaseChatModel: LLM 인스턴스

    Examples:
        >>> # 테스트 환경 (LLM_MODE=test)
        >>> llm = get_llm()  # Gemini 반환
        >>>
        >>> # 프로덕션 환경 (LLM_MODE=production)
        >>> llm = get_llm()  # Claude 반환
    """
    provider = settings.llm_provider
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else settings.llm_model_name

    logger.info(f"🤖 LLM 초기화: provider={provider}, model={model_name}")

    if provider == "anthropic":
        # Claude (Anthropic)
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다. Gemini로 폴백합니다.")
            provider = "google"
        else:
            return ChatAnthropic(
                model=model_name,
                temperature=temp,
                max_tokens=tokens,
                api_key=settings.ANTHROPIC_API_KEY,
            )

    if provider == "google":
        # Gemini (Google)
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
            )

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temp,
            max_output_tokens=tokens,
            google_api_key=settings.GEMINI_API_KEY,
        )

    # Fallback (should not reach here)
    raise ValueError(f"지원하지 않는 LLM provider: {provider}")


def get_claude_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatAnthropic:
    """
    강제로 Claude 사용 (모드 무시)

    시연이나 특정 기능에서 Claude를 명시적으로 사용해야 할 때

    Args:
        temperature: LLM temperature
        max_tokens: 최대 토큰 수
        model: 모델 이름 (기본값: CLAUDE_MODEL)

    Returns:
        ChatAnthropic: Claude 인스턴스
    """
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else settings.CLAUDE_MODEL

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    logger.info(f"🎯 Claude 강제 사용: model={model_name}")

    return ChatAnthropic(
        model=model_name,
        temperature=temp,
        max_tokens=tokens,
        api_key=settings.ANTHROPIC_API_KEY,
    )


def get_gemini_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatGoogleGenerativeAI:
    """
    강제로 Gemini 사용 (모드 무시)

    테스트나 비용 절감이 필요할 때

    Args:
        temperature: LLM temperature
        max_tokens: 최대 토큰 수
        model: 모델 이름 (기본값: GEMINI_MODEL)

    Returns:
        ChatGoogleGenerativeAI: Gemini 인스턴스
    """
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    model_name = model if model is not None else settings.GEMINI_MODEL

    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    logger.info(f"⚡ Gemini 강제 사용: model={model_name}")

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temp,
        max_output_tokens=tokens,
        google_api_key=settings.GEMINI_API_KEY,
    )

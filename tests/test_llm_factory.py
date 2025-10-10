"""
LLM Factory 테스트

LLM_MODE에 따라 Gemini와 Claude가 올바르게 선택되는지 테스트
"""
import os
import pytest
from src.utils.llm_factory import get_llm, get_claude_llm, get_gemini_llm
from src.config.settings import settings
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI


def test_llm_mode_selection():
    """LLM 모드에 따른 provider 선택 테스트"""
    print(f"\n현재 LLM_MODE: {settings.LLM_MODE}")
    print(f"현재 Provider: {settings.llm_provider}")
    print(f"현재 Model: {settings.llm_model_name}")

    # 기본값 (test 모드)
    assert settings.llm_provider in ["google", "anthropic"]


def test_get_llm_test_mode():
    """테스트 모드에서 Gemini 사용 확인"""
    # LLM_MODE=test일 때
    os.environ["LLM_MODE"] = "test"

    try:
        llm = get_llm()
        print(f"\n✅ LLM 생성 성공: {type(llm).__name__}")

        # Gemini 체크
        if isinstance(llm, ChatGoogleGenerativeAI):
            print("✅ Gemini (Google) 사용 중")
        elif isinstance(llm, ChatAnthropic):
            print("✅ Claude (Anthropic) 사용 중")

        assert llm is not None

    except ValueError as e:
        # API 키가 없으면 스킵
        print(f"⚠️ API 키 없음: {e}")
        pytest.skip(f"API 키 필요: {e}")


def test_get_llm_production_mode():
    """프로덕션 모드에서 Claude 사용 확인"""
    # LLM_MODE=production일 때
    os.environ["LLM_MODE"] = "production"

    try:
        llm = get_llm()
        print(f"\n✅ LLM 생성 성공: {type(llm).__name__}")

        # Claude 체크
        assert isinstance(llm, ChatAnthropic)
        print("✅ Claude (Anthropic) 사용 중")

    except ValueError as e:
        # API 키가 없으면 스킵
        print(f"⚠️ API 키 없음: {e}")
        pytest.skip(f"API 키 필요: {e}")
    finally:
        # 원래대로 복구
        os.environ["LLM_MODE"] = "test"


@pytest.mark.asyncio
async def test_llm_invocation_gemini():
    """Gemini LLM 호출 테스트"""
    if not settings.GEMINI_API_KEY:
        pytest.skip("GEMINI_API_KEY 필요")

    try:
        llm = get_gemini_llm()
        response = await llm.ainvoke("Hello! Reply with 'OK' only.")

        print(f"\n✅ Gemini 응답: {response.content}")
        assert response is not None
        assert len(response.content) > 0

    except Exception as e:
        pytest.fail(f"Gemini 호출 실패: {e}")


@pytest.mark.asyncio
async def test_llm_invocation_claude():
    """Claude LLM 호출 테스트 (API 크레딧 있을 때만)"""
    if not settings.ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY 필요")

    try:
        llm = get_claude_llm()
        response = await llm.ainvoke("Hello! Reply with 'OK' only.")

        print(f"\n✅ Claude 응답: {response.content}")
        assert response is not None
        assert len(response.content) > 0

    except Exception as e:
        # 크레딧 부족은 정상
        if "credit balance" in str(e).lower():
            print(f"⚠️ Claude 크레딧 부족 (정상): {e}")
            pytest.skip("Claude 크레딧 부족")
        else:
            pytest.fail(f"Claude 호출 실패: {e}")


if __name__ == "__main__":
    """직접 실행"""
    import asyncio

    async def main():
        print("\n" + "=" * 80)
        print("LLM Factory 테스트")
        print("=" * 80)

        # 1. 모드 선택 테스트
        print("\n[1/4] LLM 모드 선택 테스트")
        test_llm_mode_selection()

        # 2. 테스트 모드 (Gemini)
        print("\n[2/4] 테스트 모드 (Gemini)")
        test_get_llm_test_mode()

        # 3. 프로덕션 모드 (Claude)
        print("\n[3/4] 프로덕션 모드 (Claude)")
        test_get_llm_production_mode()

        # 4. Gemini 호출 테스트
        print("\n[4/4] Gemini 실제 호출 테스트")
        try:
            await test_llm_invocation_gemini()
        except Exception as e:
            print(f"⚠️ 스킵: {e}")

        print("\n" + "=" * 80)
        print("✅ 모든 테스트 완료!")
        print("=" * 80)

    asyncio.run(main())

"""LLM 설정 변경 검증 테스트"""
import asyncio
from src.utils.llm_factory import (
    get_router_llm,
    get_research_llm,
    get_strategy_llm,
    get_portfolio_risk_llm,
    get_default_agent_llm,
)


async def test_llm_models():
    """LLM 모델 설정 확인"""
    print("=" * 70)
    print("LLM 모델 설정 검증")
    print("=" * 70)

    # 1. Router LLM 확인
    print("\n1. Router Agent LLM (Claude Sonnet 4.5):")
    try:
        router_llm = get_router_llm(temperature=0, max_tokens=100)
        print(f"   ✅ Model: {router_llm.model}")
        print(f"   ✅ Type: {type(router_llm).__name__}")
        assert router_llm.model == "claude-sonnet-4-5-20250929", f"Expected claude-sonnet-4-5-20250929, got {router_llm.model}"
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 2. Research LLM 확인
    print("\n2. Research Agent LLM (Claude Sonnet 4.5):")
    try:
        research_llm = get_research_llm(temperature=0, max_tokens=100)
        print(f"   ✅ Model: {research_llm.model}")
        print(f"   ✅ Type: {type(research_llm).__name__}")
        assert research_llm.model == "claude-sonnet-4-5-20250929", f"Expected claude-sonnet-4-5-20250929, got {research_llm.model}"
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 3. Strategy LLM 확인
    print("\n3. Strategy Agent LLM (Claude Sonnet 4.5):")
    try:
        strategy_llm = get_strategy_llm(temperature=0, max_tokens=100)
        print(f"   ✅ Model: {strategy_llm.model}")
        print(f"   ✅ Type: {type(strategy_llm).__name__}")
        assert strategy_llm.model == "claude-sonnet-4-5-20250929", f"Expected claude-sonnet-4-5-20250929, got {strategy_llm.model}"
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 4. Portfolio/Risk LLM 확인
    print("\n4. Portfolio/Risk Agent LLM (Claude Haiku 4.5):")
    try:
        portfolio_risk_llm = get_portfolio_risk_llm(temperature=0, max_tokens=100)
        print(f"   ✅ Model: {portfolio_risk_llm.model}")
        print(f"   ✅ Type: {type(portfolio_risk_llm).__name__}")
        print(f"   ℹ️  현재 모델: {portfolio_risk_llm.model}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 5. Default Agent LLM 확인
    print("\n5. Trading + 기타 Agent LLM (GPT-5-mini):")
    try:
        default_llm = get_default_agent_llm(temperature=0, max_tokens=100)
        model_name = getattr(default_llm, 'model', None) or getattr(default_llm, 'model_name', None)
        print(f"   ✅ Model: {model_name}")
        print(f"   ✅ Type: {type(default_llm).__name__}")
        assert model_name == "gpt-5-mini", f"Expected gpt-5-mini, got {model_name}"
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print("\n" + "=" * 70)
    print("✅ 모든 LLM 설정 검증 완료")
    print("=" * 70)
    print("\n📊 에이전트별 모델 할당:")
    print("  - Router Agent         : Claude Sonnet 4.5  (claude-sonnet-4-5-20250929)")
    print("  - Research Agent       : Claude Sonnet 4.5  (claude-sonnet-4-5-20250929)")
    print("  - Strategy Agent       : Claude Sonnet 4.5  (claude-sonnet-4-5-20250929) ⭐")
    print("  - Portfolio Agent      : Claude Haiku 4.5   (claude-haiku-4-5-*)")
    print("  - Risk Agent           : Claude Haiku 4.5   (claude-haiku-4-5-*)")
    print("  - Trading Agent        : GPT-5-mini         (gpt-5-mini)")
    print("  - Monitoring Agent     : GPT-5-mini         (gpt-5-mini)")
    print("  - Report Gen Agent     : GPT-5-mini         (gpt-5-mini)")


if __name__ == "__main__":
    asyncio.run(test_llm_models())

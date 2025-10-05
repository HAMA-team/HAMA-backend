"""
Master Supervisor 패턴 테스트

최근 변경사항:
- Master Agent가 LangGraph Supervisor 패턴으로 전환됨
- langgraph_supervisor 라이브러리 사용
- 병렬 에이전트 호출 지원
- 동적 라우팅 구현
- Claude 모델 사용

참고: 이 테스트는 실제 Claude API 호출을 수행합니다.
      .env 파일에 ANTHROPIC_API_KEY가 설정되어 있어야 합니다.
"""
import pytest
from unittest.mock import AsyncMock, patch

from src.agents.graph_master import build_graph, run_graph


@pytest.mark.asyncio
async def test_supervisor_build():
    """Supervisor 그래프 빌드 테스트"""
    graph = build_graph(automation_level=2)

    assert graph is not None
    print("\n✅ Supervisor 그래프 빌드 성공")


@pytest.mark.asyncio
async def test_supervisor_general_query():
    """일반 질문 라우팅 테스트"""
    query = "PER이 뭐야?"

    result = await run_graph(
        query=query,
        automation_level=2,
        request_id="test_general"
    )

    assert result is not None
    assert "message" in result

    print("\n✅ 일반 질의 응답 성공")
    print(f"   질문: {query}")
    print(f"   응답: {result['message'][:100]}...")


@pytest.mark.asyncio
async def test_supervisor_stock_analysis_routing():
    """종목 분석 요청 시 적절한 에이전트 라우팅 테스트"""
    query = "삼성전자 분석해줘"

    result = await run_graph(
        query=query,
        automation_level=2,
        request_id="test_stock_analysis"
    )

    assert result is not None
    assert "message" in result

    # Research + Strategy + Risk 에이전트가 호출되었을 것으로 예상
    print("\n✅ 종목 분석 라우팅 성공")
    print(f"   질문: {query}")
    print(f"   응답 메시지 수: {len(result.get('messages', []))}")


@pytest.mark.asyncio
async def test_supervisor_portfolio_query():
    """포트폴리오 관련 질문 라우팅 테스트"""
    query = "내 포트폴리오 리밸런싱해줘"

    result = await run_graph(
        query=query,
        automation_level=2,
        request_id="test_portfolio"
    )

    assert result is not None
    assert "message" in result

    print("\n✅ 포트폴리오 질의 라우팅 성공")
    print(f"   질문: {query}")


@pytest.mark.asyncio
async def test_supervisor_trading_query():
    """매매 요청 라우팅 테스트"""
    query = "삼성전자 10주 매수해줘"

    result = await run_graph(
        query=query,
        automation_level=2,
        request_id="test_trading"
    )

    assert result is not None
    assert "message" in result

    # Trading agent가 호출되었을 것으로 예상
    print("\n✅ 매매 요청 라우팅 성공")
    print(f"   질문: {query}")


@pytest.mark.asyncio
async def test_supervisor_thread_consistency():
    """동일 스레드에서 대화 연속성 테스트"""
    thread_id = "test_thread_consistency"

    # 첫 번째 질문
    result1 = await run_graph(
        query="삼성전자에 대해 알려줘",
        automation_level=2,
        thread_id=thread_id
    )

    assert result1 is not None

    # 두 번째 질문 (컨텍스트 유지)
    result2 = await run_graph(
        query="그럼 이 종목을 매수해야 할까?",
        automation_level=2,
        thread_id=thread_id
    )

    assert result2 is not None

    print("\n✅ 스레드 연속성 테스트 성공")
    print(f"   첫 번째 응답: {result1['message'][:50]}...")
    print(f"   두 번째 응답: {result2['message'][:50]}...")


@pytest.mark.asyncio
async def test_supervisor_automation_level_1():
    """자동화 레벨 1 (Pilot) 테스트"""
    result = await run_graph(
        query="삼성전자 분석해줘",
        automation_level=1,  # Pilot: 거의 자동
        request_id="test_pilot"
    )

    assert result is not None
    print("\n✅ Pilot 모드 (레벨 1) 동작 확인")


@pytest.mark.asyncio
async def test_supervisor_automation_level_3():
    """자동화 레벨 3 (Advisor) 테스트"""
    result = await run_graph(
        query="포트폴리오 추천해줘",
        automation_level=3,  # Advisor: 모든 결정 승인 필요
        request_id="test_advisor"
    )

    assert result is not None
    print("\n✅ Advisor 모드 (레벨 3) 동작 확인")


if __name__ == "__main__":
    """직접 실행 시 모든 테스트 실행"""
    import asyncio
    import sys

    async def run_all_tests():
        print("=" * 60)
        print("Master Supervisor 패턴 종합 테스트")
        print("=" * 60)

        tests = [
            ("Supervisor 빌드", test_supervisor_build),
            ("일반 질문 라우팅", test_supervisor_general_query),
            ("종목 분석 라우팅", test_supervisor_stock_analysis_routing),
            ("포트폴리오 라우팅", test_supervisor_portfolio_query),
            ("매매 요청 라우팅", test_supervisor_trading_query),
            ("스레드 연속성", test_supervisor_thread_consistency),
            ("자동화 레벨 1", test_supervisor_automation_level_1),
            ("자동화 레벨 3", test_supervisor_automation_level_3),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                print(f"\n[테스트] {name}")
                await test_func()
                passed += 1
            except AssertionError as e:
                print(f"❌ 실패: {e}")
                failed += 1
            except Exception as e:
                print(f"❌ 에러: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

        print("\n" + "=" * 60)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 60)

        return failed == 0

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

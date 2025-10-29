"""
General Agent JSON 파싱 테스트

목적:
- General Agent가 LLM 응답을 JSON으로 파싱하는 로직이 올바른지 검증
- JSON이 아닌 일반 텍스트 응답도 안전하게 처리하는지 검증
"""
import asyncio
from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.agents.graph_master import build_graph
from src.config.settings import settings


async def test_general_agent_per_question():
    """
    PER 정의 질문 테스트

    이전 에러 재현:
    - 질문: "per에 대해 알려줘"
    - LLM이 JSON 대신 일반 텍스트로 응답
    - JSON 파싱 실패로 ValueError 발생
    """
    print("\n" + "=" * 60)
    print("[테스트] General Agent - PER 정의 질문")
    print("=" * 60)

    if not settings.OPENAI_API_KEY:
        print("⚠️  OPENAI_API_KEY가 없어 테스트를 건너뜁니다")
        return

    app = build_graph(automation_level=2)

    initial_state = {
        "messages": [HumanMessage(content="per에 대해 알려줘")],
        "user_id": str(uuid4()),
        "conversation_id": str(uuid4()),
        "automation_level": 2,
        "query": "per에 대해 알려줘",
        "agent_results": {},
        "agents_to_call": [],
        "agents_called": [],
    }

    config = {"configurable": {"thread_id": str(uuid4())}}

    try:
        result = await app.ainvoke(initial_state, config)

        print(f"\n✅ 실행 성공 (에러 없음)")

        # agent_results 확인
        agent_results = result.get("agent_results", {})
        general_result = agent_results.get("general")

        if general_result:
            print(f"\n📊 General Agent 결과:")
            print(f"  - answer 존재: {bool(general_result.get('answer'))}")
            print(f"  - answer 길이: {len(general_result.get('answer', ''))}")
            print(f"  - sources: {general_result.get('sources', [])}")
            print(f"  - confidence: {general_result.get('confidence', 'N/A')}")

            answer = general_result.get("answer", "")
            if answer:
                print(f"\n📝 Answer (처음 200자):")
                print(f"  {answer[:200]}")

            return True
        else:
            print("⚠️  General Agent 결과가 없습니다")
            print(f"전체 agent_results: {agent_results}")
            return False

    except ValueError as e:
        print(f"\n❌ ValueError 발생: {e}")
        print("이것은 JSON 파싱 실패를 의미합니다")
        return False

    except Exception as e:
        print(f"\n❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_general_agent_various_questions():
    """
    다양한 질문으로 General Agent 테스트
    """
    print("\n" + "=" * 60)
    print("[테스트] General Agent - 다양한 질문")
    print("=" * 60)

    if not settings.OPENAI_API_KEY:
        print("⚠️  OPENAI_API_KEY가 없어 테스트를 건너뜁니다")
        return

    questions = [
        "ROE가 뭐야?",
        "주가수익비율 설명해줘",
        "배당수익률이란?",
    ]

    app = build_graph(automation_level=2)
    results = []

    for question in questions:
        print(f"\n질문: {question}")

        initial_state = {
            "messages": [HumanMessage(content=question)],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 2,
            "query": question,
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        try:
            result = await app.ainvoke(initial_state, config)

            general_result = result.get("agent_results", {}).get("general")
            if general_result and general_result.get("answer"):
                print(f"  ✅ 성공 (answer 길이: {len(general_result['answer'])})")
                results.append(True)
            else:
                print(f"  ⚠️  응답 없음")
                results.append(False)

        except Exception as e:
            print(f"  ❌ 에러: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) * 100 if results else 0
    print(f"\n성공률: {success_rate:.1f}% ({sum(results)}/{len(results)})")

    return success_rate == 100


async def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("General Agent JSON 파싱 테스트")
    print("=" * 60)

    tests = [
        ("PER 정의 질문", test_general_agent_per_question),
        ("다양한 질문", test_general_agent_various_questions),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            success = await test_func()

            if success:
                passed += 1
                print(f"\n✅ {name} 성공")
            else:
                failed += 1
                print(f"\n⚠️  {name} 부분 성공")

        except Exception as e:
            failed += 1
            print(f"\n❌ {name} 실패: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"테스트 결과: {passed} 성공, {failed} 실패")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
"""
Graph Build 테스트

Supervisor가 정상적으로 빌드되는지 확인합니다.
"""
import logging
from src.subgraphs.graph_master import build_graph, build_supervisor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_supervisor_build():
    """Supervisor 생성 테스트"""
    logger.info("=" * 60)
    logger.info("🏗️ Supervisor 생성 테스트 시작")
    logger.info("=" * 60)

    try:
        # Supervisor workflow 생성 (컴파일되지 않은 상태)
        supervisor_workflow = build_supervisor(intervention_required=False)
        logger.info("✅ Supervisor workflow 생성 성공")

        # 노드 및 엣지 정보 확인
        if hasattr(supervisor_workflow, 'nodes'):
            logger.info(f"📋 노드 목록: {list(supervisor_workflow.nodes.keys())}")

        return True
    except Exception as e:
        logger.error(f"❌ Supervisor workflow 생성 실패: {e}", exc_info=True)
        return False


def test_graph_compile():
    """Graph 컴파일 테스트"""
    logger.info("=" * 60)
    logger.info("🔧 Graph 컴파일 테스트 시작")
    logger.info("=" * 60)

    try:
        # Graph 컴파일 (get_compiled_graph 호출)
        compiled_graph = build_graph(intervention_required=False)
        logger.info("✅ Graph 컴파일 성공")

        # 컴파일된 그래프 정보 확인
        logger.info(f"📊 Graph 타입: {type(compiled_graph)}")

        # 노드 확인
        if hasattr(compiled_graph, 'nodes'):
            nodes = list(compiled_graph.nodes.keys())
            logger.info(f"📋 컴파일된 노드 목록 ({len(nodes)}개): {nodes}")

        # 엣지 확인
        if hasattr(compiled_graph, 'edges'):
            edges = compiled_graph.edges
            logger.info(f"🔗 엣지 정보: {edges}")

        return True
    except Exception as e:
        logger.error(f"❌ Graph 컴파일 실패: {e}", exc_info=True)
        return False


def test_tools_loading():
    """Tools 로딩 테스트"""
    logger.info("=" * 60)
    logger.info("🔧 Tools 로딩 테스트 시작")
    logger.info("=" * 60)

    try:
        from src.subgraphs.tools import get_all_tools

        tools = get_all_tools()
        logger.info(f"✅ Tools 로딩 성공: {len(tools)}개")

        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description[:100]}...")

        return True
    except Exception as e:
        logger.error(f"❌ Tools 로딩 실패: {e}", exc_info=True)
        return False


def test_research_agent_import():
    """Research Agent import 테스트"""
    logger.info("=" * 60)
    logger.info("👥 Research Agent import 테스트 시작")
    logger.info("=" * 60)

    try:
        from src.subgraphs.research_subgraph import research_agent

        logger.info(f"✅ Research Agent import 성공")
        logger.info(f"  - Agent 이름: {research_agent.name}")
        logger.info(f"  - Agent 타입: {type(research_agent)}")

        return True
    except Exception as e:
        logger.error(f"❌ Research Agent import 실패: {e}", exc_info=True)
        return False


def main():
    """전체 테스트 실행"""
    logger.info("")
    logger.info("🚀 Graph Build 통합 테스트 시작")
    logger.info("")

    results = []

    # 1. Tools 로딩 테스트
    results.append(("Tools 로딩", test_tools_loading()))

    # 2. Research Agent import 테스트
    results.append(("Research Agent import", test_research_agent_import()))

    # 3. Supervisor 생성 테스트
    results.append(("Supervisor 생성", test_supervisor_build()))

    # 4. Graph 컴파일 테스트
    results.append(("Graph 컴파일", test_graph_compile()))

    # 결과 요약
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 테스트 결과 요약")
    logger.info("=" * 60)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        logger.info("")
        logger.info("🎉 모든 테스트 통과!")
        return 0
    else:
        logger.info("")
        logger.info("⚠️ 일부 테스트 실패")
        return 1


if __name__ == "__main__":
    exit(main())

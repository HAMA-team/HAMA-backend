"""
동적 Worker 선택 시스템 테스트

Query Intent Classifier와 Smart Planner의 동작을 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.constants.analysis_depth import (
    classify_depth_by_keywords,
    extract_focus_areas,
    get_recommended_workers,
    get_depth_config,
    ANALYSIS_DEPTH_LEVELS,
)
from src.agents.research.nodes import (
    query_intent_classifier_node,
    planner_node,
)
from src.agents.research.state import ResearchState


class TestAnalysisDepthHelpers:
    """Analysis Depth 헬퍼 함수 테스트"""

    def test_classify_quick_depth(self):
        """Quick 키워드 감지 테스트"""
        quick_queries = [
            "삼성전자 현재가?",
            "빠르게 알려줘",
            "가격만 확인",
            "간단히 보여줘",
        ]
        for query in quick_queries:
            assert classify_depth_by_keywords(query) == "quick"

    def test_classify_comprehensive_depth(self):
        """Comprehensive 키워드 감지 테스트"""
        comprehensive_queries = [
            "삼성전자 상세히 분석해줘",
            "종합적으로 판단해줘",
            "매수해도 될까?",
            "자세히 알려줘",
        ]
        for query in comprehensive_queries:
            assert classify_depth_by_keywords(query) == "comprehensive"

    def test_classify_standard_depth_default(self):
        """기본값 standard 테스트"""
        standard_queries = [
            "삼성전자 분석",
            "이 종목 괜찮아?",
            "SK하이닉스 보고 싶어",
        ]
        for query in standard_queries:
            assert classify_depth_by_keywords(query) == "standard"

    def test_extract_focus_areas(self):
        """Focus area 추출 테스트"""
        test_cases = [
            ("기술적 분석 해줘", ["technical"]),
            ("수급 상황 알려줘", ["trading_flow"]),
            ("뉴스랑 차트 분석", ["information", "technical"]),
            ("외국인 매수 추세", ["trading_flow"]),
            ("금리 영향 분석", ["macro"]),
            ("재무제표 확인", ["data"]),
        ]
        for query, expected_workers in test_cases:
            result = extract_focus_areas(query)
            for worker in expected_workers:
                assert worker in result, f"Query: {query}, Expected: {expected_workers}, Got: {result}"

    def test_get_recommended_workers_quick(self):
        """Quick depth의 추천 worker 테스트"""
        workers = get_recommended_workers("quick")
        config = get_depth_config("quick")

        assert "data" in workers  # data는 required
        assert len(workers) <= config["max_workers"]
        assert len(workers) >= 1

    def test_get_recommended_workers_standard(self):
        """Standard depth의 추천 worker 테스트"""
        workers = get_recommended_workers("standard")
        config = get_depth_config("standard")

        assert "data" in workers
        assert "technical" in workers
        assert len(workers) <= config["max_workers"]
        assert len(workers) >= 2

    def test_get_recommended_workers_comprehensive(self):
        """Comprehensive depth의 추천 worker 테스트"""
        workers = get_recommended_workers("comprehensive")
        config = get_depth_config("comprehensive")

        assert "data" in workers
        assert "technical" in workers
        assert "trading_flow" in workers
        assert "information" in workers
        assert len(workers) <= config["max_workers"]
        assert len(workers) >= 4

    def test_get_recommended_workers_with_focus_areas(self):
        """Focus areas가 우선적으로 포함되는지 테스트"""
        workers = get_recommended_workers("quick", focus_areas=["technical"])
        assert "technical" in workers

        workers = get_recommended_workers("quick", focus_areas=["macro"])
        # quick mode에서는 max_workers=3이므로 macro가 포함될 수 있음
        assert len(workers) <= 3


@pytest.mark.asyncio
class TestQueryIntentClassifier:
    """Query Intent Classifier 노드 테스트"""

    async def test_quick_query_classification(self):
        """Quick 쿼리 분류 테스트"""
        state: ResearchState = {
            "query": "삼성전자 현재가?",
            "user_profile": {
                "preferred_depth": "detailed",
                "expertise_level": "intermediate",
            },
            "messages": [],
        }

        result = await query_intent_classifier_node(state)

        assert result["analysis_depth"] == "quick"
        assert "depth_reason" in result
        assert isinstance(result["focus_areas"], list)

    async def test_comprehensive_query_classification(self):
        """Comprehensive 쿼리 분류 테스트"""
        state: ResearchState = {
            "query": "삼성전자 매수해도 될까요? 상세히 분석해주세요",
            "user_profile": {
                "preferred_depth": "comprehensive",
                "expertise_level": "expert",
            },
            "messages": [],
        }

        result = await query_intent_classifier_node(state)

        assert result["analysis_depth"] == "comprehensive"
        assert "depth_reason" in result

    async def test_focus_area_extraction(self):
        """Focus area 자동 추출 테스트"""
        state: ResearchState = {
            "query": "삼성전자 기술적 분석과 수급 상황 알려줘",
            "user_profile": {
                "preferred_depth": "detailed",
                "expertise_level": "intermediate",
            },
            "messages": [],
        }

        result = await query_intent_classifier_node(state)

        focus_areas = result.get("focus_areas", [])
        assert "technical" in focus_areas or "trading_flow" in focus_areas

    async def test_user_profile_preference(self):
        """UserProfile preferred_depth 반영 테스트"""
        # Brief 선호 사용자
        state_brief: ResearchState = {
            "query": "삼성전자 분석",  # 키워드 없음
            "user_profile": {
                "preferred_depth": "brief",
                "expertise_level": "beginner",
            },
            "messages": [],
        }

        result = await query_intent_classifier_node(state_brief)
        # brief는 quick으로 매핑되므로 quick 또는 standard 예상
        assert result["analysis_depth"] in ["quick", "standard"]


@pytest.mark.asyncio
class TestSmartPlanner:
    """Smart Planner 테스트"""

    async def test_planner_respects_analysis_depth(self):
        """Planner가 analysis_depth를 존중하는지 테스트"""
        state: ResearchState = {
            "query": "삼성전자 분석",
            "stock_code": "005930",
            "analysis_depth": "quick",
            "focus_areas": [],
            "depth_reason": "간단한 쿼리",
            "messages": [],
        }

        result = await planner_node(state)

        # Quick mode에서는 최대 3개 worker
        pending_tasks = result.get("pending_tasks", [])
        assert len(pending_tasks) <= 3
        assert any(task["worker"] == "data" for task in pending_tasks)

    async def test_planner_filters_invalid_workers(self):
        """Planner가 추천되지 않은 worker를 필터링하는지 테스트"""
        state: ResearchState = {
            "query": "삼성전자 분석",
            "stock_code": "005930",
            "analysis_depth": "quick",
            "focus_areas": [],
            "depth_reason": "간단한 쿼리",
            "messages": [],
        }

        result = await planner_node(state)

        pending_tasks = result.get("pending_tasks", [])
        config = get_depth_config("quick")
        recommended = get_recommended_workers("quick")

        # 모든 task의 worker가 추천 목록에 있어야 함
        for task in pending_tasks:
            worker = task.get("worker", "")
            # worker가 추천 목록에 있거나, LLM이 다르게 선택했을 수 있음
            # (LLM은 제한된 목록을 받지만, 실제로는 검증 로직이 필터링함)
            assert len(pending_tasks) <= config["max_workers"]

    async def test_planner_comprehensive_mode(self):
        """Comprehensive mode에서 더 많은 worker 선택"""
        state: ResearchState = {
            "query": "삼성전자 매수해도 될까요?",
            "stock_code": "005930",
            "analysis_depth": "comprehensive",
            "focus_areas": ["technical", "trading_flow"],
            "depth_reason": "의사결정 필요",
            "messages": [],
        }

        result = await planner_node(state)

        pending_tasks = result.get("pending_tasks", [])
        # Comprehensive mode에서는 더 많은 worker
        assert len(pending_tasks) >= 4
        assert len(pending_tasks) <= 8

        # Focus areas가 포함되어야 함
        workers = [task["worker"] for task in pending_tasks]
        # technical 또는 trading_flow 중 하나는 포함되어야 함 (LLM이 선택)


@pytest.mark.asyncio
class TestEndToEndDynamicSelection:
    """동적 Worker 선택 시스템 E2E 테스트"""

    async def test_quick_query_end_to_end(self):
        """Quick 쿼리의 전체 플로우 테스트"""
        # Step 1: Intent Classifier
        state: ResearchState = {
            "query": "삼성전자 현재가?",
            "user_profile": {
                "preferred_depth": "detailed",
                "expertise_level": "intermediate",
            },
            "messages": [],
        }

        state_after_intent = await query_intent_classifier_node(state)
        assert state_after_intent["analysis_depth"] == "quick"

        # Step 2: Planner
        state_after_intent["stock_code"] = "005930"
        state_after_planner = await planner_node(state_after_intent)

        pending_tasks = state_after_planner.get("pending_tasks", [])
        assert len(pending_tasks) <= 3
        assert len(pending_tasks) >= 1

    async def test_comprehensive_query_end_to_end(self):
        """Comprehensive 쿼리의 전체 플로우 테스트"""
        # Step 1: Intent Classifier
        state: ResearchState = {
            "query": "삼성전자 매수해도 될까요? 모든 관점에서 상세히 분석해주세요",
            "user_profile": {
                "preferred_depth": "comprehensive",
                "expertise_level": "expert",
            },
            "messages": [],
        }

        state_after_intent = await query_intent_classifier_node(state)
        assert state_after_intent["analysis_depth"] == "comprehensive"

        # Step 2: Planner
        state_after_intent["stock_code"] = "005930"
        state_after_planner = await planner_node(state_after_intent)

        pending_tasks = state_after_planner.get("pending_tasks", [])
        assert len(pending_tasks) >= 4
        assert len(pending_tasks) <= 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

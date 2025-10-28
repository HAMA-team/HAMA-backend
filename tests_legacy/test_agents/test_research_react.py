"""
Research Agent ReAct 패턴 테스트

depth_level별 동작 확인 및 기존 서브그래프와 비교
"""
import asyncio
import logging

from src.agents.research.react_interface import run_research_react

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestResearchReAct:
    """Research Agent ReAct 테스트"""

    async def test_brief_depth(self):
        """
        brief: 간단한 질문, 최소 도구 사용

        기대:
        - get_stock_price, get_basic_ratios 정도만 사용
        - 1-2문장 응답
        """
        logger.info("\n" + "=" * 60)
        logger.info("테스트 1: brief depth (간단한 질문)")
        logger.info("=" * 60)

        result = await run_research_react(
            query="삼성전자 PER이 어때?",
            stock_code="005930",
            depth_level="brief",
            user_profile={
                "expertise_level": "beginner",
                "technical_level": "basic"
            }
        )

        assert result["success"], f"실행 실패: {result.get('error')}"
        logger.info(f"\n📊 결과:\n{result['analysis']}\n")

        # 응답이 간결한지 확인 (대략 200자 이하 목표)
        assert len(result["analysis"]) < 500, "응답이 너무 길음 (brief 모드)"

        logger.info("✅ brief depth 테스트 통과")

    async def test_detailed_depth(self):
        """
        detailed: 상세 분석, 적절한 도구 조합

        기대:
        - get_stock_price + get_basic_ratios + get_financial_statement
        - 3-5개 지표 포함
        - 근거 포함
        """
        logger.info("\n" + "=" * 60)
        logger.info("테스트 2: detailed depth (상세 분석)")
        logger.info("=" * 60)

        result = await run_research_react(
            query="삼성전자 분석해줘",
            stock_code="005930",
            depth_level="detailed",
            user_profile={
                "expertise_level": "intermediate",
                "investment_style": "aggressive",
                "preferred_sectors": ["반도체"],
                "technical_level": "intermediate"
            }
        )

        assert result["success"], f"실행 실패: {result.get('error')}"
        logger.info(f"\n📊 결과:\n{result['analysis']}\n")

        # 상세한 응답 확인
        assert len(result["analysis"]) > 200, "응답이 너무 짧음 (detailed 모드)"
        assert "PER" in result["analysis"] or "PBR" in result["analysis"], "주요 지표 미포함"

        logger.info("✅ detailed depth 테스트 통과")

    async def test_comprehensive_depth(self):
        """
        comprehensive: 전문가 수준 심층 분석

        기대:
        - 모든 도구 활용 (DCF 포함)
        - 재무제표 분석
        - 계산 과정 포함
        """
        logger.info("\n" + "=" * 60)
        logger.info("테스트 3: comprehensive depth (심층 분석)")
        logger.info("=" * 60)

        result = await run_research_react(
            query="삼성전자 DCF 밸류에이션 포함해서 분석해줘",
            stock_code="005930",
            depth_level="comprehensive",
            user_profile={
                "expertise_level": "expert",
                "technical_level": "advanced",
                "wants_explanations": False
            }
        )

        assert result["success"], f"실행 실패: {result.get('error')}"
        logger.info(f"\n📊 결과:\n{result['analysis']}\n")

        # 심층 분석 확인
        assert len(result["analysis"]) > 500, "응답이 너무 짧음 (comprehensive 모드)"

        logger.info("✅ comprehensive depth 테스트 통과")

    async def test_with_sector_preference(self):
        """
        선호 섹터가 있을 때 섹터 비교 도구 사용

        기대:
        - get_sector_comparison 도구 사용
        - 업종 평균과 비교
        """
        logger.info("\n" + "=" * 60)
        logger.info("테스트 4: 선호 섹터 비교")
        logger.info("=" * 60)

        result = await run_research_react(
            query="삼성전자가 반도체 업종에서 어떤 위치야?",
            stock_code="005930",
            depth_level="detailed",
            user_profile={
                "preferred_sectors": ["반도체", "배터리"],
                "expertise_level": "intermediate"
            }
        )

        assert result["success"], f"실행 실패: {result.get('error')}"
        logger.info(f"\n📊 결과:\n{result['analysis']}\n")

        logger.info("✅ 선호 섹터 비교 테스트 통과")

    async def test_tool_efficiency(self):
        """
        도구 사용 효율성 테스트

        기대:
        - brief: 최소 도구만 (1-2개)
        - detailed: 적절한 도구 (3-4개)
        - comprehensive: 많은 도구 (5개+)
        """
        logger.info("\n" + "=" * 60)
        logger.info("테스트 5: 도구 사용 효율성 비교")
        logger.info("=" * 60)

        test_cases = [
            ("brief", "현재가 알려줘"),
            ("detailed", "분석해줘"),
            ("comprehensive", "DCF 밸류에이션 해줘")
        ]

        for depth, query in test_cases:
            result = await run_research_react(
                query=query,
                stock_code="005930",
                depth_level=depth,
                user_profile={}
            )

            logger.info(f"\n📊 {depth}: {len(result.get('messages', []))} 메시지")

        logger.info("✅ 도구 사용 효율성 테스트 완료")


async def main():
    """전체 테스트 실행"""
    tester = TestResearchReAct()

    logger.info("\n🧪 Research Agent ReAct 패턴 테스트 시작\n")

    try:
        await tester.test_brief_depth()
        await tester.test_detailed_depth()
        await tester.test_comprehensive_depth()
        await tester.test_with_sector_preference()
        await tester.test_tool_efficiency()

        logger.info("\n" + "=" * 60)
        logger.info("🎉 모든 테스트 통과!")
        logger.info("=" * 60 + "\n")

    except AssertionError as e:
        logger.error(f"\n❌ 테스트 실패: {e}\n")
        raise
    except Exception as e:
        logger.error(f"\n❌ 에러 발생: {e}\n")
        raise


if __name__ == "__main__":
    """독립 실행"""
    asyncio.run(main())

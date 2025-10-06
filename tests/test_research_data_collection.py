"""
Research Agent의 데이터 수집 노드 테스트

Legacy data_collection_agent 제거 후 서비스 직접 호출 검증
"""
import pytest
from src.agents.research.nodes import collect_data_node


class TestResearchDataCollection:
    """Research Agent 데이터 수집 노드 테스트"""

    @pytest.mark.asyncio
    async def test_collect_data_with_stock_code(self):
        """종목 코드로 데이터 수집 테스트"""
        state = {
            "stock_code": "005930",
            "messages": [],
        }

        result = await collect_data_node(state)

        # 결과 검증
        assert result is not None
        assert "stock_code" in result
        assert result["stock_code"] == "005930"
        assert "price_data" in result
        assert "error" not in result

        # 주가 데이터 검증
        assert result["price_data"] is not None
        assert "latest_close" in result["price_data"]
        assert "source" in result["price_data"]
        assert result["price_data"]["source"] == "FinanceDataReader"

        print(f"\n✅ 주가 데이터 조회 성공")
        print(f"   종목: {result['stock_code']}")
        print(f"   최종 종가: {result['price_data']['latest_close']:,}원")

    @pytest.mark.asyncio
    async def test_collect_data_with_dart_info(self):
        """DART 데이터 포함 테스트"""
        state = {
            "stock_code": "005930",
            "messages": [],
        }

        result = await collect_data_node(state)

        # DART 데이터는 선택적 (고유번호 변환 실패 시 None)
        if result.get("financial_data") is not None:
            print(f"\n✅ 재무제표 데이터 조회 성공")
            print(f"   고유번호: {result['financial_data'].get('corp_code')}")

        if result.get("company_data") is not None:
            print(f"\n✅ 기업 정보 조회 성공")
            print(f"   고유번호: {result['company_data'].get('corp_code')}")

    @pytest.mark.asyncio
    async def test_legacy_agent_removed(self):
        """Legacy data_collection_agent가 제거되었는지 확인"""
        import src.agents.research.nodes as nodes_module

        # data_collection_agent import가 없어야 함
        source_code = open(nodes_module.__file__).read()
        assert "from src.agents.legacy.data_collection import data_collection_agent" not in source_code
        assert "data_collection_agent.process" not in source_code

        # 대신 서비스들이 import되어야 함
        assert "from src.services.stock_data_service import stock_data_service" in source_code
        assert "from src.services.dart_service import dart_service" in source_code

        print("\n✅ Legacy agent 제거 확인 완료")
        print("   - data_collection_agent import 제거됨")
        print("   - stock_data_service, dart_service 사용 중")


if __name__ == "__main__":
    """직접 실행"""
    import asyncio

    async def run_tests():
        test_suite = TestResearchDataCollection()

        print("=" * 60)
        print("Research Agent 데이터 수집 테스트")
        print("=" * 60)

        try:
            print("\n[테스트 1] 종목 코드로 데이터 수집")
            await test_suite.test_collect_data_with_stock_code()

            print("\n[테스트 2] DART 데이터 포함")
            await test_suite.test_collect_data_with_dart_info()

            print("\n[테스트 3] Legacy Agent 제거 확인")
            await test_suite.test_legacy_agent_removed()

            print("\n" + "=" * 60)
            print("✅ 모든 테스트 통과!")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ 테스트 실패: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())

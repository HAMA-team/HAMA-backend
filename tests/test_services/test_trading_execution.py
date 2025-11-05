"""
Trading 실제 실행 테스트

KIS API 연동 및 에러 처리 검증
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.trading_service import trading_service
from src.services.kis_service import KISAPIError


class TestTradingExecution:
    """Trading Service 실제 실행 테스트"""

    @pytest.mark.asyncio
    async def test_execute_order_kis_success(self, monkeypatch):
        """
        KIS API 성공 시나리오

        실제 주문이 KIS API를 통해 전송되고 성공하는 경우
        """
        print("\n[Test] KIS API 주문 성공")

        # Mock 준비
        order_id = str(uuid4())
        stock_code = "005930"

        # 1. _fetch_order Mock
        mock_order_summary = {
            "order_id": order_id,
            "portfolio_id": str(uuid4()),
            "stock_code": stock_code,
            "order_type": "BUY",
            "order_quantity": 10,
            "order_price": 70000,
        }
        monkeypatch.setattr(
            trading_service,
            "_fetch_order",
            AsyncMock(return_value=mock_order_summary)
        )

        # 2. _fetch_market_price Mock
        monkeypatch.setattr(
            trading_service,
            "_fetch_market_price",
            AsyncMock(return_value=72000.0)
        )

        # 3. KIS API Mock (성공) - 실제 place_order 메서드 패치
        mock_kis_result = {
            "order_no": "KIS123456",
            "order_time": "150530",
            "status": "접수",
        }

        # 실제 kis_service 객체의 place_order 메서드 패치
        from src.services import kis_service
        original_place_order = kis_service.place_order
        kis_service.place_order = AsyncMock(return_value=mock_kis_result)

        try:
            # 4. DB 업데이트 Mock
            with patch.object(trading_service, "_session_factory") as mock_session_factory:
                mock_session = MagicMock()
                mock_order_obj = MagicMock()
                mock_order_obj.order_id = order_id
                mock_order_obj.order_quantity = 10

                mock_session.get.return_value = mock_order_obj
                mock_session.__enter__.return_value = mock_session
                mock_session.__exit__.return_value = None
                mock_session_factory.return_value = mock_session

                # 5. Portfolio 반영 Mock
                with patch("src.services.trading_service.portfolio_service") as mock_portfolio:
                    mock_portfolio.apply_trade = AsyncMock()
                    mock_portfolio.get_portfolio_snapshot = AsyncMock(return_value=None)

                    # 실행
                    result = await trading_service.execute_order(
                        order_id=order_id,
                        execution_price=72000.0,
                        automation_level=2
                    )

            # 검증
            assert result["status"] == "executed"
            assert result["kis_executed"] is True
            assert result["kis_order_no"] == "KIS123456"
            assert result["price"] == 72000.0
            assert result["quantity"] == 10

            print(f"  ✅ KIS 주문 성공: {result['kis_order_no']}")

        finally:
            # 원래 메서드 복원
            kis_service.place_order = original_place_order

    @pytest.mark.asyncio
    async def test_execute_order_kis_failure(self, monkeypatch):
        """
        KIS API 실패 시나리오

        KIS API 호출이 실패하면 Order를 rejected로 업데이트하고 에러 발생
        """
        print("\n[Test] KIS API 주문 실패")

        order_id = str(uuid4())

        # Mock 준비
        mock_order_summary = {
            "order_id": order_id,
            "portfolio_id": str(uuid4()),
            "stock_code": "005930",
            "order_type": "BUY",
            "order_quantity": 10,
            "order_price": 70000,
        }
        monkeypatch.setattr(
            trading_service,
            "_fetch_order",
            AsyncMock(return_value=mock_order_summary)
        )

        monkeypatch.setattr(
            trading_service,
            "_fetch_market_price",
            AsyncMock(return_value=72000.0)
        )

        # mark_order_status Mock
        monkeypatch.setattr(
            trading_service,
            "mark_order_status",
            AsyncMock(return_value=mock_order_summary)
        )

        # KIS API Mock (실패)
        from src.services import kis_service
        original_place_order = kis_service.place_order
        kis_service.place_order = AsyncMock(side_effect=KISAPIError("주문 실패: API 키 오류"))

        try:
            # 실행 및 예외 검증
            with pytest.raises(RuntimeError) as exc_info:
                await trading_service.execute_order(
                    order_id=order_id,
                    execution_price=72000.0,
                    automation_level=2
                )

            # 검증
            assert "KIS API 주문 실패" in str(exc_info.value)

            # mark_order_status 호출 확인
            trading_service.mark_order_status.assert_called_once()
            call_args = trading_service.mark_order_status.call_args
            assert call_args[0][0] == order_id
            assert call_args[1]["status"] == "rejected"

            print(f"  ✅ KIS 실패 시 에러 발생 및 Order rejected 처리 확인")

        finally:
            kis_service.place_order = original_place_order

    @pytest.mark.asyncio
    async def test_execute_order_insufficient_holdings(self, monkeypatch):
        """
        보유 수량 부족 시나리오

        매도 주문 시 보유 수량이 부족하면 에러 반환
        """
        print("\n[Test] 보유 수량 부족")

        order_id = str(uuid4())

        mock_order_summary = {
            "order_id": order_id,
            "portfolio_id": str(uuid4()),
            "stock_code": "005930",
            "order_type": "SELL",
            "order_quantity": 100,  # 100주 매도 시도
            "order_price": 70000,
        }
        monkeypatch.setattr(
            trading_service,
            "_fetch_order",
            AsyncMock(return_value=mock_order_summary)
        )

        monkeypatch.setattr(
            trading_service,
            "_fetch_market_price",
            AsyncMock(return_value=72000.0)
        )

        # KIS API Mock (성공이지만 Portfolio 반영에서 실패)
        from src.services import kis_service
        original_place_order = kis_service.place_order
        kis_service.place_order = AsyncMock(return_value={"order_no": "KIS999"})

        try:
            with patch.object(trading_service, "_session_factory") as mock_session_factory:
                mock_session = MagicMock()
                mock_order_obj = MagicMock()
                mock_order_obj.order_quantity = 100
                mock_session.get.return_value = mock_order_obj
                mock_session.__enter__.return_value = mock_session
                mock_session.__exit__.return_value = None
                mock_session_factory.return_value = mock_session

                # Portfolio 반영 시 InsufficientHoldingsError 발생
                from src.services.portfolio_service import InsufficientHoldingsError
                with patch("src.services.trading_service.portfolio_service") as mock_portfolio:
                    mock_portfolio.apply_trade = AsyncMock(
                        side_effect=InsufficientHoldingsError("보유 수량 부족")
                    )

                    # mark_order_status Mock
                    monkeypatch.setattr(
                        trading_service,
                        "mark_order_status",
                        AsyncMock(return_value=mock_order_summary)
                    )

                    # 실행
                    result = await trading_service.execute_order(
                        order_id=order_id,
                        execution_price=72000.0,
                        automation_level=2
                    )

            # 검증
            assert result["status"] == "rejected"
            assert "보유 수량 부족" in result["error"]

            print(f"  ✅ 보유 수량 부족 시 rejected 처리 확인")

        finally:
            kis_service.place_order = original_place_order


if __name__ == "__main__":
    """직접 실행 시"""
    import asyncio

    async def run_tests():
        test_suite = TestTradingExecution()

        print("=" * 80)
        print("Trading 실제 실행 테스트 시작")
        print("=" * 80)

        try:
            await test_suite.test_execute_order_kis_success({})
            await test_suite.test_execute_order_kis_failure({})
            await test_suite.test_execute_order_insufficient_holdings({})

            print("\n" + "=" * 80)
            print("✅ 모든 테스트 통과!")
            print("=" * 80)

        except AssertionError as e:
            print(f"\n❌ 테스트 실패: {e}")
        except Exception as e:
            print(f"\n❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())

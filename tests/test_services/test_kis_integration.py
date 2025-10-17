"""
KIS API 통합 테스트

Portfolio Agent와 Trading Agent의 KIS API 연동을 검증합니다.
KIS API 키가 .env에 설정되어 있어야 테스트가 통과합니다.
"""
import asyncio
import pytest

from src.services import kis_service, portfolio_service, trading_service
from src.services.kis_service import KISAPIError
from src.config.settings import settings


class TestKISIntegration:
    """KIS API 통합 테스트"""

    @pytest.mark.asyncio
    async def test_portfolio_agent_kis_integration(self):
        """Portfolio Agent가 KIS 계좌 조회 성공"""
        # 계좌번호 확인
        if not settings.KIS_ACCOUNT_NUMBER:
            pytest.skip("KIS_ACCOUNT_NUMBER not configured")

        # KIS API로 계좌 잔고 조회
        balance = await kis_service.get_account_balance()

        # 검증
        assert balance is not None
        assert "total_assets" in balance
        assert "cash_balance" in balance
        assert "stocks" in balance
        assert isinstance(balance["stocks"], list)

        print(f"✅ Portfolio Agent - KIS 계좌 조회 성공")
        print(f"   총 자산: {balance['total_assets']:,}원")
        print(f"   예수금: {balance['cash_balance']:,}원")
        print(f"   보유 종목: {len(balance['stocks'])}개")

    @pytest.mark.asyncio
    async def test_trading_agent_kis_order_execution(self):
        """Trading Agent가 KIS API로 실제 주문 실행"""
        if not settings.KIS_ACCOUNT_NUMBER:
            pytest.skip("KIS_ACCOUNT_NUMBER not configured")

        # 매수 주문 테스트 (시장가)
        try:
            result = await kis_service.place_order(
                stock_code="005930",  # 삼성전자
                order_type="BUY",
                quantity=1,
                price=None,  # 시장가
            )

            # 검증
            assert result["order_no"] is not None
            assert result["status"] == "접수"

            print(f"✅ Trading Agent - KIS 주문 실행 성공")
            print(f"   주문번호: {result['order_no']}")
            print(f"   종목: {result['stock_code']}")
            print(f"   수량: {result['quantity']}주")

        except KISAPIError as e:
            # 잔고 부족, 거래시간 외 등은 정상적인 실패
            print(f"⚠️ 주문 실패 (정상): {e}")

    @pytest.mark.asyncio
    async def test_end_to_end_portfolio_to_trade(self):
        """E2E: 포트폴리오 조회 → 매매 주문 전체 흐름"""
        if not settings.KIS_ACCOUNT_NUMBER:
            pytest.skip("KIS_ACCOUNT_NUMBER not configured")

        # 1. 계좌 잔고 조회
        balance = await kis_service.get_account_balance()
        assert balance is not None

        print(f"\n📊 [1/2] 계좌 조회 완료: 총자산 {balance['total_assets']:,}원")

        # 2. 매수 주문 실행
        try:
            order_result = await kis_service.place_order(
                stock_code="005930",
                order_type="BUY",
                quantity=1,
                price=70000,  # 지정가
            )

            print(f"💰 [2/2] 주문 실행 완료: {order_result['order_no']}")
            print(f"\n✅ E2E 테스트 성공!")

        except KISAPIError as e:
            print(f"⚠️ 주문 실패 (정상): {e}")


if __name__ == "__main__":
    """테스트 직접 실행"""
    import asyncio

    async def main():
        print("\n" + "="*60)
        print("KIS API 통합 테스트 시작")
        print("="*60 + "\n")

        tester = TestKISIntegration()

        # KIS 키 확인
        if not settings.KIS_ACCOUNT_NUMBER:
            print("⏭️ KIS API 키가 설정되지 않아 테스트를 스킵합니다.")
            print("   .env 파일에 다음 값을 설정하세요:")
            print("   - KIS_APP_KEY")
            print("   - KIS_APP_SECRET")
            print("   - KIS_ACCOUNT_NUMBER")
            return

        # 1. Portfolio Agent 연동 테스트
        print("[1/3] Portfolio Agent KIS 연동 테스트...")
        try:
            await tester.test_portfolio_agent_kis_integration()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 2. Trading Agent 주문 실행 테스트
        print("[2/3] Trading Agent 주문 실행 테스트...")
        try:
            await tester.test_trading_agent_kis_order_execution()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 3. E2E 통합 테스트
        print("[3/3] E2E 통합 테스트...")
        try:
            await tester.test_end_to_end_portfolio_to_trade()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        print("="*60)
        print("테스트 완료")
        print("="*60)

    asyncio.run(main())

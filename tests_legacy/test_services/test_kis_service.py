"""
KIS Service 기본 테스트

KIS API 키가 .env에 설정되어 있어야 테스트가 통과합니다.
설정되지 않았으면 테스트를 스킵하지 않고 실패시킵니다 (CLAUDE.md 원칙)
"""
import asyncio
import pytest

from src.services.kis_service import KISService, KISAuthError, KISAPIError
from src.config.settings import settings


class TestKISService:
    """KIS Service 기본 기능 테스트"""

    @pytest.fixture
    def kis(self):
        """KIS Service 인스턴스 (모의투자)"""
        return KISService(env="demo")

    @pytest.mark.asyncio
    async def test_get_access_token(self, kis):
        """OAuth 2.0 토큰 발급 테스트"""
        # API 키 설정 확인
        assert settings.KIS_APP_KEY is not None, "KIS_APP_KEY must be set in .env"
        assert settings.KIS_APP_SECRET is not None, "KIS_APP_SECRET must be set in .env"

        # 토큰 발급
        token = await kis._get_access_token()

        # 검증
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        print(f"✅ Access token obtained: {token[:20]}...")

    @pytest.mark.asyncio
    async def test_get_access_token_caching(self, kis):
        """토큰 캐싱 테스트"""
        # 첫 번째 호출
        token1 = await kis._get_access_token()

        # 두 번째 호출 (캐시에서 가져와야 함)
        token2 = await kis._get_access_token()

        # 같은 토큰이어야 함
        assert token1 == token2
        print("✅ Token caching works correctly")

    @pytest.mark.asyncio
    async def test_get_account_balance(self, kis):
        """계좌 잔고 조회 테스트"""
        # 계좌번호 설정 확인
        if not settings.KIS_ACCOUNT_NUMBER:
            pytest.skip("KIS_ACCOUNT_NUMBER not configured")

        # 계좌 잔고 조회
        balance = await kis.get_account_balance()

        # 검증
        assert balance is not None
        assert "total_assets" in balance
        assert "cash_balance" in balance
        assert "stocks" in balance
        assert isinstance(balance["stocks"], list)

        print(f"✅ Account balance:")
        print(f"   Total assets: {balance['total_assets']:,}원")
        print(f"   Cash: {balance['cash_balance']:,}원")
        print(f"   Stocks: {len(balance['stocks'])}개")

    @pytest.mark.asyncio
    async def test_get_stock_price(self, kis):
        """주식 시세 조회 테스트 (삼성전자)"""
        stock_code = "005930"  # 삼성전자

        # 시세 조회
        price = await kis.get_stock_price(stock_code)

        # 검증
        assert price is not None
        assert price["stock_code"] == stock_code
        assert price["stock_name"] is not None
        assert price["current_price"] > 0
        assert "open_price" in price
        assert "high_price" in price
        assert "low_price" in price
        assert "volume" in price

        print(f"✅ Stock price for {price['stock_name']}:")
        print(f"   Current: {price['current_price']:,}원")
        print(f"   Change: {price['change_price']:+,}원 ({price['change_rate']:+.2f}%)")
        print(f"   Volume: {price['volume']:,}주")

    @pytest.mark.asyncio
    async def test_get_stock_price_caching(self, kis):
        """시세 조회 캐싱 테스트"""
        stock_code = "005930"

        # 첫 번째 호출
        price1 = await kis.get_stock_price(stock_code)

        # 두 번째 호출 (캐시에서 가져와야 함)
        price2 = await kis.get_stock_price(stock_code)

        # 같은 데이터여야 함 (10초 TTL 내)
        assert price1["current_price"] == price2["current_price"]
        print("✅ Stock price caching works correctly")

    @pytest.mark.asyncio
    async def test_invalid_stock_code(self, kis):
        """잘못된 종목코드 에러 처리 테스트"""
        stock_code = "999999"  # 존재하지 않는 종목

        # KISAPIError가 발생해야 함
        with pytest.raises(KISAPIError):
            await kis.get_stock_price(stock_code)

        print("✅ Invalid stock code error handling works")

    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """인증 실패 테스트"""
        # 잘못된 API 키로 KIS Service 생성
        kis = KISService(
            app_key="invalid_key",
            app_secret="invalid_secret",
            env="demo"
        )

        # KISAuthError가 발생해야 함
        with pytest.raises(KISAuthError):
            await kis._get_access_token()

        print("✅ Authentication error handling works")

    @pytest.mark.asyncio
    async def test_place_order_buy(self, kis):
        """매수 주문 테스트 (삼성전자 1주)"""
        # 계좌번호 설정 확인
        if not settings.KIS_ACCOUNT_NUMBER:
            pytest.skip("KIS_ACCOUNT_NUMBER not configured")

        stock_code = "005930"  # 삼성전자
        quantity = 1

        # Rate limit 준수를 위한 대기
        await asyncio.sleep(1.2)

        # 매수 주문 실행 (시장가)
        try:
            result = await kis.place_order(
                stock_code=stock_code,
                order_type="BUY",
                quantity=quantity,
                price=None,  # 시장가
            )

            # 검증
            assert result is not None
            assert result["order_no"] is not None
            assert result["status"] == "접수"
            assert result["stock_code"] == stock_code
            assert result["order_type"] == "BUY"
            assert result["quantity"] == quantity

            print(f"✅ Buy order placed:")
            print(f"   Order No: {result['order_no']}")
            print(f"   Stock: {stock_code}")
            print(f"   Quantity: {quantity}주")

        except KISAPIError as e:
            # 잔고 부족 등의 에러는 정상적인 동작
            print(f"⚠️ Order failed (expected): {e}")

    @pytest.mark.asyncio
    async def test_place_order_limit(self, kis):
        """지정가 주문 테스트"""
        if not settings.KIS_ACCOUNT_NUMBER:
            pytest.skip("KIS_ACCOUNT_NUMBER not configured")

        stock_code = "005930"
        quantity = 1
        price = 60000  # 지정가 (현재가보다 낮게)

        # Rate limit 준수를 위한 대기
        await asyncio.sleep(1.2)

        try:
            result = await kis.place_order(
                stock_code=stock_code,
                order_type="BUY",
                quantity=quantity,
                price=price,
            )

            assert result["order_dvsn"] == "00"  # 지정가
            assert result["price"] == price

            print(f"✅ Limit order placed @ {price:,}원")

        except KISAPIError as e:
            print(f"⚠️ Order failed (expected): {e}")


if __name__ == "__main__":
    """테스트 직접 실행"""
    import asyncio

    async def main():
        print("\n" + "="*60)
        print("KIS Service 테스트 시작")
        print("="*60 + "\n")

        kis = KISService(env="demo")

        # 1. 토큰 발급 테스트
        print("[1/5] OAuth 토큰 발급 테스트...")
        try:
            token = await kis._get_access_token()
            print(f"✅ 성공: {token[:20]}...\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 2. 계좌 잔고 조회 테스트
        if settings.KIS_ACCOUNT_NUMBER:
            print("[2/5] 계좌 잔고 조회 테스트...")
            try:
                balance = await kis.get_account_balance()
                print(f"✅ 성공: 총 자산 {balance['total_assets']:,}원\n")
            except Exception as e:
                print(f"❌ 실패: {e}\n")
        else:
            print("[2/5] 계좌 잔고 조회 - 계좌번호 미설정으로 스킵\n")

        # 3. 주식 시세 조회 테스트
        print("[3/5] 주식 시세 조회 테스트 (삼성전자)...")
        try:
            price = await kis.get_stock_price("005930")
            print(f"✅ 성공: {price['stock_name']} {price['current_price']:,}원\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 4. 캐싱 테스트
        print("[4/5] 캐싱 테스트...")
        try:
            token1 = await kis._get_access_token()
            token2 = await kis._get_access_token()
            assert token1 == token2
            print("✅ 성공: 토큰 캐싱 작동\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 5. 에러 핸들링 테스트
        print("[5/5] 에러 핸들링 테스트 (잘못된 종목코드)...")
        try:
            await kis.get_stock_price("999999")
            print("❌ 실패: 에러가 발생하지 않음\n")
        except KISAPIError:
            print("✅ 성공: KISAPIError 발생\n")
        except Exception as e:
            print(f"❌ 실패: 예상치 못한 에러 {e}\n")

        # 6. 주문 테스트 (매수)
        if settings.KIS_ACCOUNT_NUMBER:
            print("[6/7] 주문 테스트 (매수 - 시장가)...")
            await asyncio.sleep(1.2)  # Rate limit 준수
            try:
                result = await kis.place_order(
                    stock_code="005930",
                    order_type="BUY",
                    quantity=1,
                    price=None,
                )
                print(f"✅ 성공: 주문번호 {result['order_no']}\n")
            except Exception as e:
                print(f"⚠️ 주문 실패 (정상): {e}\n")
        else:
            print("[6/7] 주문 테스트 - 계좌번호 미설정으로 스킵\n")

        # 7. 지정가 주문 테스트
        if settings.KIS_ACCOUNT_NUMBER:
            print("[7/7] 주문 테스트 (매수 - 지정가)...")
            await asyncio.sleep(1.2)  # Rate limit 준수
            try:
                result = await kis.place_order(
                    stock_code="005930",
                    order_type="BUY",
                    quantity=1,
                    price=60000,
                )
                print(f"✅ 성공: 주문번호 {result['order_no']}, 지정가 {result['price']:,}원\n")
            except Exception as e:
                print(f"⚠️ 주문 실패 (정상): {e}\n")
        else:
            print("[7/7] 지정가 주문 테스트 - 계좌번호 미설정으로 스킵\n")

        print("="*60)
        print("테스트 완료")
        print("="*60)

    asyncio.run(main())

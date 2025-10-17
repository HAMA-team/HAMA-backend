"""
한국투자증권 Open Trading API 서비스

KIS API 연동:
- OAuth 2.0 인증 토큰 발급 및 자동 갱신
- 계좌 정보 조회 (잔고, 보유 종목)
- 실시간 시세 조회
- 주문 실행

참고: https://github.com/koreainvestment/open-trading-api
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal

import requests
from requests.exceptions import RequestException

from src.config.settings import settings
from src.services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class RateLimiter:
    """API 호출 제한 관리 (초당 1회)"""

    def __init__(self, calls_per_second: float = 1.0):
        """
        Args:
            calls_per_second: 초당 허용 호출 수 (기본 1회)
        """
        self.min_interval = 1.0 / calls_per_second  # 최소 간격 (초)
        self.last_call_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """
        Rate limit을 준수하며 API 호출 허가를 얻음.
        필요시 대기.
        """
        async with self._lock:
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time

            if time_since_last_call < self.min_interval:
                # 최소 간격이 지나지 않았으면 대기
                wait_time = self.min_interval - time_since_last_call
                logger.debug(f"⏳ Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            self.last_call_time = time.time()


class KISAPIError(Exception):
    """KIS API 호출 중 발생한 에러"""
    pass


class KISAuthError(Exception):
    """KIS API 인증 에러"""
    pass


class KISService:
    """한국투자증권 Open Trading API 서비스"""

    # API 엔드포인트
    PROD_BASE_URL = "https://openapi.koreainvestment.com:9443"
    DEMO_BASE_URL = "https://openapivts.koreainvestment.com:29443"

    # API URL
    AUTH_TOKEN_URL = "/oauth2/tokenP"
    BALANCE_URL = "/uapi/domestic-stock/v1/trading/inquire-balance"
    ACCOUNT_BALANCE_URL = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
    STOCK_PRICE_URL = "/uapi/domestic-stock/v1/quotations/inquire-price"

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        account_number: Optional[str] = None,
        env: str = "demo",  # "real" or "demo"
    ):
        """
        KIS 서비스 초기화

        Args:
            app_key: KIS 앱 키 (None이면 settings에서 가져옴)
            app_secret: KIS 앱 시크릿 (None이면 settings에서 가져옴)
            account_number: 계좌번호 (8-2 형식, None이면 settings에서 가져옴)
            env: 환경 ("real": 실전, "demo": 모의투자)
        """
        self.app_key = app_key or settings.KIS_APP_KEY
        self.app_secret = app_secret or settings.KIS_APP_SECRET
        self.account_number = account_number or settings.KIS_ACCOUNT_NUMBER
        self.env = env

        # 계좌번호 파싱 (8-2 형식)
        if self.account_number:
            parts = self.account_number.split("-")
            if len(parts) == 2:
                self.cano = parts[0]  # 종합계좌번호 (앞 8자리)
                self.acnt_prdt_cd = parts[1]  # 계좌상품코드 (뒤 2자리)
            else:
                self.cano = self.account_number[:8] if len(self.account_number) >= 8 else ""
                self.acnt_prdt_cd = self.account_number[8:10] if len(self.account_number) >= 10 else ""
        else:
            self.cano = ""
            self.acnt_prdt_cd = ""

        # Base URL 설정
        self.base_url = self.PROD_BASE_URL if env == "real" else self.DEMO_BASE_URL

        # 토큰 관리
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # Rate Limiter 설정 (초당 1회)
        self._rate_limiter = RateLimiter(calls_per_second=1.0)

        logger.info(f"✅ KIS Service initialized (env={env}, base_url={self.base_url})")

    # ==================== 인증 ====================

    async def _get_access_token(self) -> str:
        """
        OAuth 2.0 액세스 토큰 발급 (캐싱)

        Returns:
            access_token: 액세스 토큰

        Raises:
            KISAuthError: 인증 실패 시
        """
        # 캐시에서 토큰 확인
        cache_key = f"kis_token:{self.env}:{self.app_key}"
        cached_token = await cache_manager.get(cache_key)

        if cached_token:
            logger.debug("✅ Using cached KIS access token")
            return cached_token

        # 토큰이 유효한지 확인
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                logger.debug("✅ Using existing KIS access token")
                return self._access_token

        # 새 토큰 발급
        logger.info("🔑 Requesting new KIS access token...")

        if not self.app_key or not self.app_secret:
            raise KISAuthError("KIS_APP_KEY and KIS_APP_SECRET must be configured in .env")

        url = f"{self.base_url}{self.AUTH_TOKEN_URL}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8"
        }
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            # 비동기로 실행
            response = await asyncio.to_thread(
                requests.post, url, json=data, headers=headers, timeout=10
            )

            if response.status_code != 200:
                logger.error(f"❌ KIS auth failed: {response.status_code} - {response.text}")
                raise KISAuthError(f"Token request failed: {response.status_code}")

            result = response.json()
            access_token = result.get("access_token")
            expires_in = result.get("expires_in", 86400)  # 기본 24시간

            if not access_token:
                raise KISAuthError("No access_token in response")

            # 토큰 저장
            self._access_token = access_token
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Redis 캐싱 (TTL: expires_in - 5분)
            await cache_manager.set(cache_key, access_token, ttl=max(expires_in - 300, 60))

            logger.info(f"✅ KIS access token obtained (expires in {expires_in}s)")
            return access_token

        except RequestException as e:
            logger.error(f"❌ KIS auth request failed: {e}")
            raise KISAuthError(f"Request failed: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"❌ KIS auth response parsing failed: {e}")
            raise KISAuthError(f"JSON decode failed: {e}") from e

    async def _api_call(
        self,
        url_path: str,
        tr_id: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        tr_cont: str = "",
    ) -> Dict[str, Any]:
        """
        KIS API 공통 호출 함수

        Args:
            url_path: API 경로 (ex. /uapi/domestic-stock/v1/trading/inquire-balance)
            tr_id: 거래ID (ex. TTTC8434R)
            params: 쿼리 파라미터 또는 Body 데이터
            method: HTTP 메서드 ("GET" or "POST")
            tr_cont: 연속거래여부 ("" or "N" or "M" or "F")

        Returns:
            API 응답 딕셔너리

        Raises:
            KISAPIError: API 호출 실패 시
        """
        # Rate Limit 적용
        await self._rate_limiter.acquire()

        access_token = await self._get_access_token()
        url = f"{self.base_url}{url_path}"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",  # 개인
        }

        if tr_cont:
            headers["tr_cont"] = tr_cont

        try:
            if method == "GET":
                response = await asyncio.to_thread(
                    requests.get, url, params=params, headers=headers, timeout=10
                )
            else:  # POST
                response = await asyncio.to_thread(
                    requests.post, url, json=params, headers=headers, timeout=10
                )

            if response.status_code != 200:
                logger.error(f"❌ KIS API failed: {response.status_code} - {response.text}")
                raise KISAPIError(f"API call failed: {response.status_code} - {response.text}")

            result = response.json()

            # 에러 확인
            rt_cd = result.get("rt_cd", "")
            if rt_cd != "0":
                msg = result.get("msg1", "Unknown error")
                logger.error(f"❌ KIS API error: {rt_cd} - {msg}")
                raise KISAPIError(f"API error: {rt_cd} - {msg}")

            return result

        except RequestException as e:
            logger.error(f"❌ KIS API request failed: {e}")
            raise KISAPIError(f"Request failed: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"❌ KIS API response parsing failed: {e}")
            raise KISAPIError(f"JSON decode failed: {e}") from e

    # ==================== 계좌 정보 ====================

    async def get_account_balance(self) -> Dict[str, Any]:
        """
        투자계좌 자산 현황 조회

        Returns:
            {
                "total_assets": 총자산,
                "cash_balance": 예수금,
                "stocks": [
                    {
                        "stock_code": "005930",
                        "stock_name": "삼성전자",
                        "quantity": 10,
                        "avg_price": 70000,
                        "current_price": 72000,
                        "eval_amount": 720000,
                        "profit_loss": 20000,
                        "profit_rate": 2.86
                    },
                    ...
                ]
            }
        """
        if not self.cano or not self.acnt_prdt_cd:
            raise KISAPIError("Account number not configured")

        logger.info(f"📊 Fetching account balance: {self.cano}-{self.acnt_prdt_cd}")

        # TR ID: 실전/모의 구분
        tr_id = "TTTC8434R" if self.env == "real" else "VTTC8434R"

        params = {
            "CANO": self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",  # 시간외단일가 여부
            "OFL_YN": "",
            "INQR_DVSN": "02",  # 조회구분 (02: 종목별)
            "UNPR_DVSN": "01",  # 단가구분
            "FUND_STTL_ICLD_YN": "N",  # 펀드결제분 포함여부
            "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액 자동상환여부
            "PRCS_DVSN": "00",  # 처리구분 (00: 전일매매포함)
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        result = await self._api_call(self.BALANCE_URL, tr_id, params, method="GET")

        # output1: 보유 종목 리스트
        stocks_data = result.get("output1", [])

        # output2: 계좌 요약 정보 (리스트로 올 수도 있음)
        output2 = result.get("output2", {})
        if isinstance(output2, list):
            # 리스트인 경우 첫 번째 항목 사용
            summary_data = output2[0] if len(output2) > 0 else {}
        else:
            summary_data = output2

        stocks = []
        for item in stocks_data:
            stock_code = item.get("pdno", "")
            quantity = int(item.get("hldg_qty", 0))

            # 수량이 0인 종목은 제외 (전량 매도 후 D-2 이전)
            if quantity == 0:
                continue

            stocks.append({
                "stock_code": stock_code,
                "stock_name": item.get("prdt_name", ""),
                "quantity": quantity,
                "avg_price": float(item.get("pchs_avg_pric", 0)),
                "current_price": float(item.get("prpr", 0)),  # 현재가
                "eval_amount": int(item.get("evlu_amt", 0)),  # 평가금액
                "profit_loss": int(item.get("evlu_pfls_amt", 0)),  # 평가손익
                "profit_rate": float(item.get("evlu_pfls_rt", 0)),  # 평가손익률
            })

        response = {
            "total_assets": int(summary_data.get("tot_evlu_amt", 0)),  # 총평가금액
            "cash_balance": int(summary_data.get("dnca_tot_amt", 0)),  # 예수금총액
            "stocks": stocks,
            "evlu_pfls_smtl_amt": int(summary_data.get("evlu_pfls_smtl_amt", 0)),  # 평가손익합계
            "nass_amt": int(summary_data.get("nass_amt", 0)),  # 순자산액
        }

        logger.info(f"✅ Account balance fetched: {len(stocks)} stocks, total={response['total_assets']:,}원")
        return response

    # ==================== 시세 조회 ====================

    async def get_stock_price(self, stock_code: str) -> Dict[str, Any]:
        """
        주식 현재가 시세 조회

        Args:
            stock_code: 종목코드 (ex. "005930")

        Returns:
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "current_price": 72000,
                "change_price": 1000,
                "change_rate": 1.41,
                "open_price": 71000,
                "high_price": 72500,
                "low_price": 70500,
                "volume": 15234567,
                "per": 15.2,
                "pbr": 1.8,
                ...
            }
        """
        logger.info(f"📈 Fetching stock price: {stock_code}")

        # 캐싱 (10초 TTL)
        cache_key = f"kis_stock_price:{stock_code}"
        cached = await cache_manager.get(cache_key)
        if cached:
            logger.debug(f"✅ Using cached price for {stock_code}")
            return cached

        tr_id = "FHKST01010100"  # 주식현재가 시세

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 시장 분류 코드 (J: 주식)
            "FID_INPUT_ISCD": stock_code,  # 종목코드
        }

        result = await self._api_call(self.STOCK_PRICE_URL, tr_id, params, method="GET")

        output = result.get("output", {})

        response = {
            "stock_code": stock_code,
            "stock_name": output.get("hts_kor_isnm", ""),  # HTS 한글 종목명
            "current_price": int(output.get("stck_prpr", 0)),  # 주식 현재가
            "change_price": int(output.get("prdy_vrss", 0)),  # 전일 대비
            "change_rate": float(output.get("prdy_ctrt", 0)),  # 전일 대비율
            "open_price": int(output.get("stck_oprc", 0)),  # 시가
            "high_price": int(output.get("stck_hgpr", 0)),  # 최고가
            "low_price": int(output.get("stck_lwpr", 0)),  # 최저가
            "volume": int(output.get("acml_vol", 0)),  # 누적 거래량
            "per": float(output.get("per", 0)) if output.get("per") else None,  # PER
            "pbr": float(output.get("pbr", 0)) if output.get("pbr") else None,  # PBR
            "market_cap": int(output.get("hts_avls", 0)) if output.get("hts_avls") else None,  # 시가총액
        }

        # 캐싱 (10초 TTL)
        await cache_manager.set(cache_key, response, ttl=10)

        logger.info(f"✅ Stock price fetched: {stock_code} = {response['current_price']:,}원")
        return response

    # ==================== 주문 실행 ====================

    async def place_order(
        self,
        stock_code: str,
        order_type: str,  # "BUY" or "SELL"
        quantity: int,
        price: Optional[float] = None,  # None이면 시장가
        order_dvsn: str = "01",  # 01: 시장가, 00: 지정가
    ) -> Dict[str, Any]:
        """
        주식 현금 주문 실행

        Args:
            stock_code: 종목코드 (ex. "005930")
            order_type: 주문 구분 ("BUY": 매수, "SELL": 매도)
            quantity: 주문 수량
            price: 주문 단가 (None이면 시장가, 지정가면 가격 필수)
            order_dvsn: 주문구분 (01: 시장가, 00: 지정가)

        Returns:
            {
                "order_no": "주문번호",
                "order_time": "주문시간",
                "status": "접수",
                "stock_code": stock_code,
                "order_type": order_type,
                "quantity": quantity,
                "price": price or 0,
            }

        Raises:
            KISAPIError: 주문 실패 시
        """
        if not self.cano or not self.acnt_prdt_cd:
            raise KISAPIError("Account number not configured")

        order_type = order_type.upper()
        if order_type not in ("BUY", "SELL"):
            raise ValueError("order_type must be 'BUY' or 'SELL'")

        logger.info(f"💰 [KIS] 주문 실행: {order_type} {stock_code} {quantity}주 @ {price or '시장가'}")

        # TR ID 설정 (실전/모의, 매수/매도)
        if self.env == "real":
            tr_id = "TTTC0012U" if order_type == "BUY" else "TTTC0011U"
        else:  # demo
            tr_id = "VTTC0012U" if order_type == "BUY" else "VTTC0011U"

        # 주문구분 설정
        if price is None:
            # 시장가
            order_dvsn = "01"
            order_price = "0"
        else:
            # 지정가
            order_dvsn = "00"
            order_price = str(int(price))

        params = {
            "CANO": self.cano,  # 종합계좌번호
            "ACNT_PRDT_CD": self.acnt_prdt_cd,  # 계좌상품코드
            "PDNO": stock_code,  # 종목코드
            "ORD_DVSN": order_dvsn,  # 주문구분
            "ORD_QTY": str(quantity),  # 주문수량
            "ORD_UNPR": order_price,  # 주문단가
            "EXCG_ID_DVSN_CD": "KRX",  # 거래소ID구분코드
            "SLL_TYPE": "",  # 매도유형 (일반 매도는 빈 문자열)
            "CNDT_PRIC": "",  # 조건가격
        }

        result = await self._api_call(
            "/uapi/domestic-stock/v1/trading/order-cash",
            tr_id,
            params,
            method="POST"
        )

        # output 파싱
        output = result.get("output", {})
        order_no = output.get("ORD_NO") or output.get("ODNO")  # 주문번호
        order_time = output.get("ORD_TMD") or output.get("ORD_TIME")  # 주문시간

        response = {
            "order_no": order_no,
            "order_time": order_time,
            "status": "접수",  # 실제로는 체결 확인 필요
            "stock_code": stock_code,
            "order_type": order_type,
            "quantity": quantity,
            "price": price or 0,
            "order_dvsn": order_dvsn,
        }

        logger.info(f"✅ [KIS] 주문 접수 완료: {order_no} ({order_type} {quantity}주)")
        return response


# 전역 인스턴스
kis_service = KISService(env="demo")  # 기본은 모의투자


# ==================== 헬퍼 함수 ====================

async def init_kis_service(env: str = "demo") -> None:
    """
    KIS 서비스 초기화 (앱 시작 시 호출)

    Args:
        env: 환경 ("real" or "demo")
    """
    global kis_service
    kis_service = KISService(env=env)

    # 토큰 미리 발급 (검증)
    try:
        await kis_service._get_access_token()
        logger.info("✅ KIS Service initialized and authenticated")
    except KISAuthError as e:
        logger.warning(f"⚠️ KIS authentication failed: {e}")
        logger.info("KIS API will be unavailable. Please check KIS_APP_KEY and KIS_APP_SECRET in .env")

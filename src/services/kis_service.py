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
import sys
import time
import types
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from requests.exceptions import RequestException

from src.config.settings import settings
from src.constants.kis_constants import KIS_BASE_URLS, KIS_ENDPOINTS, KIS_TR_IDS, INDEX_CODES

logger = logging.getLogger(__name__)


class _KISServiceModule(types.ModuleType):
    """`src.services.kis_service.kis_service` 임포트가 전역 인스턴스에 위임되도록 하는 모듈 프록시."""

    def __init__(self, name: str, service: "KISService") -> None:
        super().__init__(name)
        super().__setattr__("_service", service)

    def __getattr__(self, item: str):
        if item == "kis_service":
            return self._service
        return getattr(self._service, item)

    def __setattr__(self, key: str, value) -> None:
        if key in {"_service", "__dict__", "__spec__", "__loader__", "__package__", "__path__", "__file__"}:
            super().__setattr__(key, value)
        elif hasattr(self._service, key):
            setattr(self._service, key, value)
        else:
            super().__setattr__(key, value)


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

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        account_number: Optional[str] = None,
        env: str = "demo",  # "real" or "demo"
        token_cache_path: Optional[str | Path] = None,
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
        self.base_url = KIS_BASE_URLS["prod"] if env == "real" else KIS_BASE_URLS["demo"]

        # 캐시 경로 설정
        resolved_cache = token_cache_path or settings.kis_token_cache_path
        self._token_cache_path = Path(resolved_cache).expanduser() if resolved_cache else None

        # 토큰 관리
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._token_lock = asyncio.Lock()  # 토큰 발급 동시성 제어

        # Rate Limiter 설정 (초당 1회)
        self._rate_limiter = RateLimiter(calls_per_second=1.0)

        logger.info(f"✅ KIS Service initialized (env={env}, base_url={self.base_url})")

        # 캐시된 토큰이 있다면 초기화 시 불러옵니다.
        self._load_cached_token()

    # ==================== 인증 ====================

    def _load_cached_token(self) -> bool:
        """디스크에서 저장된 토큰을 가져옵니다."""
        path = self._token_cache_path
        if not path or not path.exists():
            return False

        try:
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("⚠️ KIS 토큰 캐시를 읽는 동안 오류가 발생했습니다: %s", exc)
            return False

        cached_env = payload.get("env")
        if cached_env and cached_env != self.env:
            logger.debug("🔁 KIS 캐시 엔트리(env=%s)가 현재 env(%s)와 다릅니다.", cached_env, self.env)
            return False

        access_token = payload.get("access_token")
        expires_at_raw = payload.get("expires_at")
        if not access_token or not expires_at_raw:
            return False

        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError as exc:
            logger.warning("⚠️ KIS 토큰 만료시간 파싱에 실패했습니다: %s", exc)
            return False

        if datetime.now() >= expires_at - timedelta(minutes=5):
            return False

        self._access_token = access_token
        self._token_expires_at = expires_at
        logger.info("✅ 캐시된 KIS 액세스 토큰을 불러왔습니다 (%s)", path)
        return True

    def _persist_token_cache(self) -> None:
        """유효한 토큰을 디스크에 저장합니다."""
        path = self._token_cache_path
        if not path or not self._access_token or not self._token_expires_at:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "env": self.env,
                "access_token": self._access_token,
                "expires_at": self._token_expires_at.isoformat(),
            }
            with path.open("w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)
        except OSError as exc:
            logger.warning("⚠️ KIS 토큰 캐시 저장 실패: %s", exc)

    @staticmethod
    def _try_parse_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if cleaned in ("", "-", "--"):  # 빈값 인식
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _trend_from_net(net: Optional[float]) -> str:
        if net is None:
            return "데이터없음"
        if net > 0:
            return "순매수"
        if net < 0:
            return "순매도"
        return "보합"

    @staticmethod
    def _strength_from_net(net: Optional[float]) -> int:
        if net is None or net == 0:
            return 1
        magnitude = abs(net)
        level = int(magnitude // 100_000_000) + 1
        return min(5, max(1, level))

    @staticmethod
    def _supply_strength(total_net: Optional[float]) -> str:
        if total_net is None:
            return "데이터없음"
        magnitude = abs(total_net)
        if magnitude >= 1_000_000_000:
            return "강함"
        if magnitude <= 200_000_000:
            return "약함"
        return "보통"

    @staticmethod
    def _extract_value(record: Dict[str, Any], candidates: List[str]) -> Optional[float]:
        for candidate in candidates:
            value = record.get(candidate)
            result = KISService._try_parse_number(value)
            if result is not None:
                return result
        return None

    @staticmethod
    def _determine_leading_investor(amounts: Dict[str, Optional[float]]) -> str:
        max_leader = None
        max_value = 0.0
        for label, value in amounts.items():
            if value is None:
                continue
            magnitude = abs(value)
            if magnitude > max_value:
                max_value = magnitude
                max_leader = label
        if max_leader is None or max_value == 0.0:
            return "혼재"
        return max_leader

    @staticmethod
    def _select_numeric(record: Dict[str, Any], keywords: List[str]) -> Optional[float]:
        best_value: Optional[float] = None
        best_score = -1
        for key, raw in record.items():
            lower = key.lower()
            if not any(keyword in lower for keyword in keywords):
                continue
            value = KISService._try_parse_number(raw)
            if value is None:
                continue
            score = sum(5 for keyword in keywords if keyword in lower)
            if "net" in lower:
                score += 3
            if "amt" in lower or "value" in lower:
                score += 1
            if "buy" in lower or "sell" in lower:
                score -= 1
            if score <= 0:
                score = 1
            if score > best_score:
                best_score = score
                best_value = value
        return best_value

    def _build_investor_segment(self, stock_code: str, label: str, net_value: Optional[float]) -> Dict[str, Any]:
        magnitude = abs(net_value) if net_value is not None else 0
        formatted_amount = f"{int(magnitude):,}" if net_value is not None else "데이터없음"
        trend = self._trend_from_net(net_value)
        strength = self._strength_from_net(net_value)
        if net_value is None:
            analysis = f"{label} 거래 데이터가 부족하여 추세를 판단할 수 없습니다."
        else:
            direction = "매수" if trend == "순매수" else "매도" if trend == "순매도" else "보합"
            analysis = (
                f"{stock_code}에서 {label}은 {trend}이며, 순{direction}금액 {formatted_amount}원 수준입니다."
            )

        return {
            "trend": trend,
            "strength": strength,
            "net_amount": int(net_value) if net_value is not None else None,
            "analysis": analysis,
        }

    def _build_investor_payload(self, stock_code: str, record: Dict[str, Any]) -> Dict[str, Any]:
        normalized_record = {}
        for key, value in record.items():
            if isinstance(value, Decimal):
                normalized_record[key] = float(value)
            else:
                normalized_record[key] = value

        foreign_net = self._select_numeric(normalized_record, ["frgn", "foreign"])
        institutional_net = self._select_numeric(normalized_record, ["inst", "institution"])
        individual_net = self._select_numeric(normalized_record, ["indv", "individual", "private"])

        segments = {
            "외국인": foreign_net,
            "기관": institutional_net,
            "개인": individual_net,
        }

        total_net = sum(value for value in segments.values() if value is not None)

        supply_strength = self._supply_strength(total_net)
        outlook = (
            "긍정적" if total_net and total_net > 0 else "부정적" if total_net and total_net < 0 else "중립"
        )
        leading = self._determine_leading_investor(segments)
        if leading == "혼재":
            forecast = "세부 투자자 흐름이 혼조라 뚜렷한 방향성을 판단하기 어렵습니다."
        else:
            forecast = f"{leading} 중심으로 {outlook} 수급 흐름이 지속될 가능성이 높습니다."

        return {
            "foreign_investor": self._build_investor_segment(stock_code, "외국인", foreign_net),
            "institutional_investor": self._build_investor_segment(
                stock_code, "기관", institutional_net
            ),
            "individual_investor": self._build_investor_segment(
                stock_code, "개인", individual_net
            ),
            "supply_demand_analysis": {
                "leading_investor": leading,
                "supply_strength": supply_strength,
                "outlook": outlook,
                "forecast": forecast,
            },
            "raw_output": normalized_record,
            "timestamp": datetime.now().isoformat(),
            "source": "KIS",
        }

    async def _get_access_token(self) -> str:
        """
        OAuth 2.0 액세스 토큰 발급 (캐싱 + Race Condition 방지)

        Returns:
            access_token: 액세스 토큰

        Raises:
            KISAuthError: 인증 실패 시
        """
        # Lock 없이 빠른 체크 (대부분의 경우)
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                logger.debug("✅ Using existing KIS access token")
                return self._access_token

        # Lock을 획득하여 동시 발급 방지
        async with self._token_lock:
            # Lock 내부에서 다시 한번 체크 (다른 요청이 이미 발급했을 수 있음)
            if self._access_token and self._token_expires_at:
                if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                    logger.debug("✅ Using existing KIS access token (after lock)")
                    return self._access_token

            # 새 토큰 발급
            logger.info("🔑 Requesting new KIS access token...")

            if not self.app_key or not self.app_secret:
                raise KISAuthError("KIS_APP_KEY and KIS_APP_SECRET must be configured in .env")

            url = f"{self.base_url}{KIS_ENDPOINTS['auth']}"
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

                # 토큰 저장 (발급 시점 기준으로 유효 기간 관리)
                self._access_token = access_token
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                logger.info(f"✅ KIS access token obtained (expires in {expires_in}s)")
                self._persist_token_cache()
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
        tr_id = KIS_TR_IDS["balance"]["real"] if self.env == "real" else KIS_TR_IDS["balance"]["demo"]

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

        result = await self._api_call(KIS_ENDPOINTS["balance"], tr_id, params, method="GET")

        # output1: 보유 종목 리스트
        stocks_data = result.get("output1", [])

        # output2: 계좌 요약 정보 (리스트로 올 수도 있음)
        output2 = result.get("output2", {})
        if isinstance(output2, list):
            # 리스트인 경우 첫 번째 항목 사용
            summary_data = output2[0] if len(output2) > 0 else {}
        else:
            summary_data = output2

        # 🔍 디버깅: Output2 전체 구조 로깅
        logger.info(f"🔍 [KIS Debug] output2 타입: {type(output2)}")
        logger.info(f"🔍 [KIS Debug] summary_data 전체: {summary_data}")

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

        def _get_int_from_summary(keys: List[str], default: int = 0) -> int:
            """여러 키 중 첫 번째로 존재하는 값을 int로 변환."""

            for key in keys:
                raw = summary_data.get(key)
                if raw in (None, ""):
                    continue
                try:
                    return int(str(raw).replace(",", ""))
                except (TypeError, ValueError):
                    logger.debug("[KIS Debug] %s 값을 정수로 변환하지 못했습니다: %s", key, raw)
            return default

        # 예수금 필드 추출 (문서와 실제 응답 모두 지원)
        cash_balance = _get_int_from_summary(
            [
                "dncl_amt",  # 예수금액
                "tot_dncl_amt",  # 총예수금액
                "dnca_tot_amt",  # 실거래 예수금합계
                "nxdy_excc_amt",  # 익일 출금가능액
                "prvs_rcdl_excc_amt",  # 전일 출금가능액
            ],
            default=0,
        )

        # 평가금액 합계 (필드명이 상황별로 다름)
        evlu_amt_smtl = _get_int_from_summary(
            [
                "evlu_amt_smtl",  # 평가금액합계
                "evlu_amt_smtl_amt",  # 평가금액합계 (다른 응답)
                "scts_evlu_amt",  # 주식 평가금액 합
            ],
            default=0,
        )

        # 순자산 총액 / 총 자산
        nass_amt = _get_int_from_summary(
            [
                "nass_tot_amt",  # 순자산총금액
                "nass_amt",  # 응답에 따라 '_tot' 빠진 키 사용
                "tot_evlu_amt",  # 총 평가금액
            ],
            default=0,
        )

        total_assets = nass_amt if nass_amt > 0 else (evlu_amt_smtl + cash_balance)

        response = {
            "total_assets": total_assets,
            "cash_balance": cash_balance,
            "stocks": stocks,
            "evlu_pfls_smtl_amt": _get_int_from_summary(["evlu_pfls_smtl_amt"], default=0),
            "nass_amt": nass_amt,
        }

        # 🔍 디버깅: 주요 필드 확인
        logger.info("🔍 [KIS Debug] Output2 주요 필드:")
        logger.info(f"  - evlu_amt_smtl (평가금액합계): {evlu_amt_smtl:,}원")
        logger.info(f"  - cash candidates (dncl_amt/dnca_tot_amt 등): {cash_balance:,}원")
        logger.info(f"  - nass_amt (순자산총금액): {nass_amt:,}원")
        logger.info(f"  - 최종 total_assets: {total_assets:,}원")
        logger.info(f"  - 최종 cash_balance: {cash_balance:,}원")

        logger.info(f"✅ Account balance fetched: {len(stocks)} stocks, total={total_assets:,}원, cash={cash_balance:,}원")
        return response

    async def get_investor_flow(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """투자자별 매매 흐름 조회"""

        logger.info("📡 [KIS] 투자자 흐름 조회: %s", stock_code)

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }

        try:
            result = await self._api_call(
                KIS_ENDPOINTS["investor_flow"],
                KIS_TR_IDS["investor_flow"],
                params,
                method="GET",
            )

            output = result.get("output") or result.get("output1") or result.get("output2") or {}
            record = output[0] if isinstance(output, list) and output else output or {}

            if not record:
                logger.warning("⚠️ [KIS] 투자자 흐름 데이터 없음: %s", stock_code)
                return {}

            return self._build_investor_payload(stock_code, record)

        except Exception as exc:
            logger.warning("⚠️ [KIS] 투자자 흐름 조회 실패: %s", exc)
            return {}

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

        tr_id = KIS_TR_IDS["stock_price"]

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 시장 분류 코드 (J: 주식)
            "FID_INPUT_ISCD": stock_code,  # 종목코드
        }

        result = await self._api_call(KIS_ENDPOINTS["stock_price"], tr_id, params, method="GET")

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

        logger.info(f"✅ Stock price fetched: {stock_code} = {response['current_price']:,}원")
        return response

    async def get_stock_daily_price(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        period: str = "D"
    ) -> Optional[pd.DataFrame]:
        """
        국내주식 일자별 시세 조회 (OHLCV)

        Args:
            stock_code: 종목코드 (ex. "005930")
            start_date: 시작일자 (YYYYMMDD)
            end_date: 종료일자 (YYYYMMDD)
            period: 기간 분류 코드 (D: 일봉, W: 주봉, M: 월봉, Y: 년봉)

        Returns:
            pd.DataFrame with columns: Date, Open, High, Low, Close, Volume
            또는 None (조회 실패 시)
        """
        logger.info(f"📊 [KIS] 일자별 주가 조회: {stock_code} ({start_date} ~ {end_date})")

        tr_id = KIS_TR_IDS["stock_daily_price"]

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 시장 분류 코드 (J: 주식)
            "FID_INPUT_ISCD": stock_code,  # 종목코드
            "FID_INPUT_DATE_1": start_date,  # 시작일자
            "FID_INPUT_DATE_2": end_date,  # 종료일자
            "FID_PERIOD_DIV_CODE": period,  # 기간 분류 코드
            "FID_ORG_ADJ_PRC": "0",  # 수정주가 원주가 가격 구분 (0: 수정주가, 1: 원주가)
        }

        try:
            result = await self._api_call(
                KIS_ENDPOINTS["stock_daily_price"],
                tr_id,
                params,
                method="GET"
            )

            output = result.get("output2", [])  # output2가 일자별 데이터 리스트

            if not output:
                logger.warning(f"⚠️ [KIS] 일자별 주가 데이터 없음: {stock_code}")
                return None

            # DataFrame 생성
            data = []
            for item in output:
                data.append({
                    "Date": item.get("stck_bsop_date", ""),  # 주식 영업 일자
                    "Open": int(item.get("stck_oprc", 0)),  # 시가
                    "High": int(item.get("stck_hgpr", 0)),  # 최고가
                    "Low": int(item.get("stck_lwpr", 0)),  # 최저가
                    "Close": int(item.get("stck_clpr", 0)),  # 종가
                    "Volume": int(item.get("acml_vol", 0)),  # 누적 거래량
                })

            df = pd.DataFrame(data)

            # Date를 datetime으로 변환하고 인덱스로 설정
            df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d")
            df.set_index("Date", inplace=True)

            # 날짜 오름차순 정렬
            df.sort_index(inplace=True)

            logger.info(f"✅ [KIS] 일자별 주가 조회 완료: {stock_code} ({len(df)}일)")
            return df

        except Exception as e:
            logger.error(f"❌ [KIS] 일자별 주가 조회 실패: {stock_code} - {e}")
            return None

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
        if order_type == "BUY":
            tr_id = KIS_TR_IDS["order_buy"]["real"] if self.env == "real" else KIS_TR_IDS["order_buy"]["demo"]
        else:  # SELL
            tr_id = KIS_TR_IDS["order_sell"]["real"] if self.env == "real" else KIS_TR_IDS["order_sell"]["demo"]

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

    # ==================== 지수 조회 ====================

    async def get_index_price(self, index_code: str) -> Optional[Dict[str, Any]]:
        """
        국내업종 현재지수 조회

        Args:
            index_code: 지수 코드 (ex. "0001": KOSPI, "1001": KOSDAQ, "2001": KOSPI200)

        Returns:
            {
                "index_code": "0001",
                "index_name": "KOSPI",
                "current_price": 2500.12,
                "change": 10.5,
                "change_rate": 0.42,
                "volume": 500000000,
                "timestamp": "2025-11-06T..."
            }

        Raises:
            KISAPIError: API 호출 실패 시
        """
        logger.info(f"📊 [KIS] 지수 조회: {index_code}")

        # API 호출
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",  # 업종
            "FID_INPUT_ISCD": index_code,
        }

        result = await self._api_call(
            KIS_ENDPOINTS["index_price"],
            KIS_TR_IDS["index_price"],
            params
        )

        # output 파싱
        output = result.get("output")
        if not output:
            logger.error(f"❌ [KIS] 지수 데이터 없음: {index_code}")
            return None

        # 응답 데이터 변환
        response = {
            "index_code": index_code,
            "index_name": output.get("hts_kor_isnm", ""),  # 지수명
            "current_price": float(output.get("bstp_nmix_prpr", 0)),  # 현재가
            "change": float(output.get("bstp_nmix_prdy_vrss", 0)),  # 전일대비
            "change_rate": float(output.get("prdy_vrss_sign", 0)),  # 등락률
            "volume": int(output.get("acml_vol", 0)),  # 누적거래량
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"✅ [KIS] 지수 조회 완료: {index_code} = {response['current_price']}")
        return response

    async def get_index_daily_price(
        self,
        index_code: str,
        period: str = "D",  # D: 일별, W: 주별, M: 월별
        start_date: Optional[str] = None,
        days: int = 60,
    ) -> Optional[pd.DataFrame]:
        """
        국내업종 일자별지수 조회 (OHLCV)

        Args:
            index_code: 지수 코드 (ex. "0001": KOSPI)
            period: 기간 구분 (D: 일별, W: 주별, M: 월별)
            start_date: 시작일 (YYYYMMDD), None이면 days 기준
            days: 조회 일수 (start_date가 None일 때)

        Returns:
            DataFrame with columns: Date, Open, High, Low, Close, Volume

        Raises:
            KISAPIError: API 호출 실패 시
        """
        logger.info(f"📊 [KIS] 지수 일자별 조회: {index_code} (period={period}, days={days})")

        # 날짜 계산
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        # API 호출
        params = {
            "FID_PERIOD_DIV_CODE": period,  # D: 일별
            "FID_COND_MRKT_DIV_CODE": "U",  # 업종
            "FID_INPUT_ISCD": index_code,
            "FID_INPUT_DATE_1": start_date,
        }

        result = await self._api_call(
            KIS_ENDPOINTS["index_daily_price"],
            KIS_TR_IDS["index_daily_price"],
            params
        )

        # output2 파싱 (일자별 데이터)
        output2 = result.get("output2")
        if not output2:
            logger.error(f"❌ [KIS] 지수 일자별 데이터 없음: {index_code}")
            return None

        # DataFrame 변환
        records = []
        for item in output2:
            try:
                records.append({
                    "Date": pd.to_datetime(item.get("stck_bsop_date", ""), format="%Y%m%d"),
                    "Open": float(item.get("bstp_nmix_oprc", 0)),
                    "High": float(item.get("bstp_nmix_hgpr", 0)),
                    "Low": float(item.get("bstp_nmix_lwpr", 0)),
                    "Close": float(item.get("bstp_nmix_prpr", 0)),
                    "Volume": int(item.get("acml_vol", 0)),
                })
            except Exception as e:
                logger.warning(f"⚠️ [KIS] 지수 데이터 파싱 오류: {item} - {e}")
                continue

        if not records:
            logger.error(f"❌ [KIS] 유효한 지수 데이터 없음: {index_code}")
            return None

        df = pd.DataFrame(records)
        df = df.sort_values("Date")
        df = df.set_index("Date")

        logger.info(f"✅ [KIS] 지수 일자별 조회 완료: {index_code} ({len(df)}일)")
        return df


    async def get_financial_ratios(
        self, stock_code: str, date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """재무비율을 조회하여 표준화된 dict로 반환합니다."""

        logger.info("📋 [KIS] 재무비율 조회: %s", stock_code)

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": date or datetime.now().strftime("%Y%m%d"),
        }

        try:
            result = await self._api_call(
                KIS_ENDPOINTS["financial_ratio"],
                KIS_TR_IDS["financial_ratio"],
                params,
                method="GET",
            )

            output = result.get("output") or {}
            record = output[0] if isinstance(output, list) and output else output

            if not record:
                logger.warning("⚠️ [KIS] 재무비율 응답 없음: %s", stock_code)
                return {}

            normalized = {k.lower(): v for k, v in record.items()}

            ratio_data = {
                "per": self._extract_value(normalized, ["per", "priceearningsratio"]),
                "pbr": self._extract_value(normalized, ["pbr", "pricebookratio"]),
                "eps": self._extract_value(normalized, ["eps", "earningspershare"]),
                "bps": self._extract_value(normalized, ["bps", "bookvaluepershare"]),
                "roe": self._extract_value(normalized, ["roe", "returnonequity"]),
                "roa": self._extract_value(normalized, ["roa", "returnonassets"]),
                "dps": self._extract_value(normalized, ["dps", "dividendper"]),
                "dividend_yield": self._extract_value(
                    normalized, ["dividend_yield", "dividendyield", "dividendratio"]
                ),
                "raw_output": normalized,
            }

            logger.info("✅ [KIS] 재무비율 조회 완료: %s", stock_code)
            return ratio_data

        except Exception as exc:
            logger.warning("⚠️ [KIS] 재무비율 조회 실패: %s", exc)
            return {}


# 전역 인스턴스
kis_service = KISService(env="demo")  # 기본은 모의투자
# 테스트에서 `src.services.kis_service.kis_service.kis_service` 체인 접근을 허용하기 위해 self alias 설정
setattr(kis_service, "kis_service", kis_service)

_kis_proxy_module = _KISServiceModule(f"{__name__}.kis_service", kis_service)
_kis_proxy_module.__file__ = __file__
_kis_proxy_module.__package__ = __name__
sys.modules[f"{__name__}.kis_service"] = _kis_proxy_module


# ==================== 헬퍼 함수 ====================

async def init_kis_service(env: str = "demo") -> None:
    """
    KIS 서비스 초기화 (앱 시작 시 호출)

    기존 인스턴스를 재사용하고 환경 설정만 업데이트합니다.
    이렇게 하면 이미 import된 모듈들이 같은 인스턴스를 계속 사용할 수 있습니다.

    Args:
        env: 환경 ("real" or "demo")
    """
    global kis_service

    # 기존 인스턴스의 설정 업데이트 (새 인스턴스를 만들지 않음!)
    kis_service.env = env
    kis_service.base_url = KIS_BASE_URLS["prod"] if env == "real" else KIS_BASE_URLS["demo"]

    # 토큰 초기화 (새로운 환경에서는 토큰도 새로 발급)
    kis_service._access_token = None
    kis_service._token_expires_at = None

    logger.info(f"🔄 [KIS] 환경 변경: {env}, base_url={kis_service.base_url}")

    # 토큰 미리 발급 (검증)
    if not kis_service._load_cached_token():
        try:
            await kis_service._get_access_token()
            logger.info("✅ KIS Service initialized and authenticated")
        except KISAuthError as e:
            logger.warning(f"⚠️ KIS authentication failed: {e}")
            logger.info("KIS API will be unavailable. Please check KIS_APP_KEY and KIS_APP_SECRET in .env")

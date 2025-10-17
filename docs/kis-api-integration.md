# KIS API 통합 가이드

**작성일**: 2025-10-03
**상태**: Phase 1 데이터 모델 설계 완료 ✅

---

## 📋 개요

한국투자증권(Korea Investment & Securities, KIS) Open Trading API와의 통합을 위한 데이터 모델 매핑 및 구현 가이드입니다.

**Phase 1 목표**: KIS API 응답 구조에 호환되는 데이터 모델 설계
**Phase 2 목표**: 실제 API 연동 및 데이터 수집 구현

---

## 🗂️ 추가된 데이터 모델

### 1. StockQuote (실시간 호가)

**파일**: `src/models/stock.py`
**테이블**: `stock_quotes`

#### KIS API 매핑

| HAMA 필드 | KIS API 필드 | 설명 |
|-----------|--------------|------|
| `ask_price_1~10` | `askp1~10` | 매도호가 1~10단계 |
| `ask_volume_1~10` | `askp_rsqn1~10` | 매도잔량 1~10단계 |
| `bid_price_1~10` | `bidp1~10` | 매수호가 1~10단계 |
| `bid_volume_1~10` | `bidp_rsqn1~10` | 매수잔량 1~10단계 |
| `total_ask_volume` | `total_askp_rsqn` | 총 매도잔량 |
| `total_bid_volume` | `total_bidp_rsqn` | 총 매수잔량 |
| `quote_time` | `stck_bsop_date` + `stck_bsop_time` | 호가 시간 |

#### 예시 데이터
```python
{
    "stock_code": "005930",
    "quote_time": "2025-10-03 09:30:00",
    "ask_price_1": 76050,
    "ask_volume_1": 1000,
    "bid_price_1": 76000,
    "bid_volume_1": 1200,
    # ... (10단계)
    "total_ask_volume": 15000,
    "total_bid_volume": 18000
}
```

---

### 2. RealtimePrice (실시간 현재가)

**파일**: `src/models/stock.py`
**테이블**: `realtime_prices`

#### KIS API 매핑

| HAMA 필드 | KIS API 필드 | 설명 |
|-----------|--------------|------|
| `current_price` | `stck_prpr` | 현재가 |
| `open_price` | `stck_oprc` | 시가 |
| `high_price` | `stck_hgpr` | 고가 |
| `low_price` | `stck_lwpr` | 저가 |
| `prev_close` | `stck_sdpr` | 전일 종가 |
| `change_amount` | `prdy_vrss` | 전일 대비 |
| `change_rate` | `prdy_vrss_rate` | 등락률 |
| `change_sign` | `prdy_vrss_sign` | 전일 대비 부호 |
| `volume` | `acml_vol` | 누적 거래량 |
| `trading_value` | `acml_tr_pbmn` | 누적 거래대금 |
| `market_cap` | `hts_avls` | 시가총액 |
| `per` | `per` | PER |
| `pbr` | `pbr` | PBR |

#### 변동 부호 (change_sign)

| 값 | 의미 |
|----|------|
| `1` | 상한 |
| `2` | 상승 |
| `3` | 보합 |
| `4` | 하한 |
| `5` | 하락 |

#### 예시 데이터
```python
{
    "stock_code": "005930",
    "timestamp": "2025-10-03 09:35:27",
    "current_price": 76100,
    "open_price": 76000,
    "high_price": 76200,
    "low_price": 75800,
    "prev_close": 76000,
    "change_amount": 100,
    "change_rate": 0.001316,
    "change_sign": "2",  # 상승
    "volume": 1234567,
    "market_cap": 453700000000000,
    "per": 12.5,
    "pbr": 1.1
}
```

---

### 3. Order (주문 관리)

**파일**: `src/models/portfolio.py`
**테이블**: `orders`

#### KIS API 매핑

| HAMA 필드 | KIS API 필드 | 설명 |
|-----------|--------------|------|
| `kis_order_number` | `odno` | 주문번호 |
| `order_price_type` | `ord_dvsn` | 주문구분 (00:지정가, 01:시장가 등) |
| `order_quantity` | `ord_qty` | 주문수량 |
| `filled_quantity` | `tot_ccld_qty` | 총 체결수량 |
| `unfilled_quantity` | `rmn_qty` | 잔여수량 |
| `filled_avg_price` | `avg_prvs` | 평균 체결가 |
| `order_status` | `ord_stts` | 주문상태 |

#### 주문 상태 (order_status)

| HAMA 값 | KIS 값 | 설명 |
|---------|--------|------|
| `pending` | `02` | 접수 |
| `accepted` | `03` | 확인 |
| `partially_filled` | `04` | 부분 체결 |
| `filled` | `10` | 체결 완료 |
| `cancelled` | `11` | 취소 완료 |
| `rejected` | `99` | 거부 |

#### 예시 데이터
```python
{
    "order_id": "uuid-123...",
    "portfolio_id": "uuid-456...",
    "stock_code": "005930",
    "order_type": "BUY",
    "order_price_type": "LIMIT",  # 지정가
    "order_price": 76000,
    "order_quantity": 100,
    "filled_quantity": 50,
    "unfilled_quantity": 50,
    "filled_avg_price": 76000,
    "order_status": "partially_filled",
    "kis_order_number": "0000123456",
    "ordered_at": "2025-10-03 09:35:00"
}
```

---

### 4. Stock 모델 확장

**파일**: `src/models/stock.py`
**테이블**: `stocks`

#### 추가된 필드

| 필드 | 타입 | 설명 | KIS API 참조 |
|------|------|------|--------------|
| `market_cap` | BigInteger | 시가총액 | `hts_avls` |
| `week52_high` | DECIMAL(15, 2) | 52주 최고가 | `w52_hgpr` |
| `week52_low` | DECIMAL(15, 2) | 52주 최저가 | `w52_lwpr` |
| `dividend_yield` | DECIMAL(5, 4) | 배당수익률 | `stck_divi` |
| `is_managed` | String(1) | 관리종목 여부 | `iscd_stat_cls_code` |

---

## 🔌 Phase 2 구현 가이드

### 1. KIS API 인증

```python
# src/services/kis_auth.py (Phase 2에서 생성)

import httpx
from src.config.settings import settings

class KISAuth:
    """KIS API 인증 관리"""

    BASE_URL = "https://openapi.koreainvestment.com:9443"

    async def get_access_token(self):
        """Access Token 발급"""
        url = f"{self.BASE_URL}/oauth2/tokenP"

        payload = {
            "grant_type": "client_credentials",
            "appkey": settings.KIS_APP_KEY,
            "appsecret": settings.KIS_APP_SECRET
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            data = response.json()

            return data["access_token"]
```

### 2. 실시간 호가 조회

```python
# src/services/kis_market.py (Phase 2에서 생성)

async def get_stock_quote(stock_code: str):
    """실시간 호가 조회

    API: /uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn
    """
    url = f"{KISAuth.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"

    headers = {
        "authorization": f"Bearer {access_token}",
        "appkey": settings.KIS_APP_KEY,
        "appsecret": settings.KIS_APP_SECRET,
        "tr_id": "FHKST01010200"  # 주식 현재가 호가
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # 시장 구분
        "FID_INPUT_ISCD": stock_code
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        data = response.json()

        # KIS API 응답을 StockQuote 모델로 변환
        return transform_to_stock_quote(data)


def transform_to_stock_quote(kis_data: dict) -> dict:
    """KIS API 응답을 StockQuote 모델로 변환"""
    output = kis_data["output"]

    return {
        "stock_code": output["stck_shrn_iscd"],
        "quote_time": datetime.now(),
        "ask_price_1": float(output["askp1"]),
        "ask_price_2": float(output["askp2"]),
        # ... 10단계
        "ask_volume_1": int(output["askp_rsqn1"]),
        "ask_volume_2": int(output["askp_rsqn2"]),
        # ... 10단계
        "bid_price_1": float(output["bidp1"]),
        "bid_price_2": float(output["bidp2"]),
        # ... 10단계
        "bid_volume_1": int(output["bidp_rsqn1"]),
        "bid_volume_2": int(output["bidp_rsqn2"]),
        # ... 10단계
        "total_ask_volume": int(output["total_askp_rsqn"]),
        "total_bid_volume": int(output["total_bidp_rsqn"])
    }
```

### 3. 주문 실행 (Phase 3)

```python
# src/services/kis_trading.py (Phase 3에서 생성)

async def place_order(
    stock_code: str,
    order_type: str,  # "BUY" or "SELL"
    quantity: int,
    price: float = None  # None이면 시장가
):
    """주식 주문

    API: /uapi/domestic-stock/v1/trading/order-cash
    """
    # 실제 매매는 Phase 3에서 구현
    # Phase 1-2에서는 시뮬레이션만
    pass
```

---

## 📦 Mock 데이터 생성

현재 Phase 1에서는 실제 API 대신 Mock 데이터를 사용합니다.

### scripts/seed_kis_mock_data.py

```python
# 실시간 호가 Mock 생성
def generate_quote_data(stock_code: str, base_price: float):
    tick = calculate_tick_size(base_price)  # 호가 단위

    # 매도 호가: 현재가 기준 위쪽
    for i in range(1, 11):
        ask_price = base_price + (tick * i)
        ask_volume = random.randint(100, 10000)
        # ...

    # 매수 호가: 현재가 기준 아래쪽
    for i in range(1, 11):
        bid_price = base_price - (tick * i)
        bid_volume = random.randint(100, 10000)
        # ...
```

---

## 🔄 마이그레이션

### scripts/migrate_kis_compatible.py

기존 19개 테이블에서 22개 테이블로 확장:

```bash
python scripts/migrate_kis_compatible.py
```

**작업 내용**:
1. `stocks` 테이블에 5개 컬럼 추가
2. `stock_quotes` 테이블 생성 (호가 10단계)
3. `realtime_prices` 테이블 생성
4. `orders` 테이블 생성

---

## 🧪 테스트

Mock 데이터 기반으로 E2E 테스트 작성 완료:

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# E2E 테스트만
python -m pytest tests/test_e2e_*.py -v
```

**결과**: 25/25 테스트 100% 통과 ✅

---

## 📚 참고 자료

### KIS Open API 문서
- **API 포털**: https://apiportal.koreainvestment.com
- **GitHub**: https://github.com/koreainvestment/open-trading-api

### 주요 API 엔드포인트

| 기능 | TR ID | URL |
|------|-------|-----|
| 주식 현재가 시세 | FHKST01010100 | /uapi/domestic-stock/v1/quotations/inquire-price |
| 주식 호가 | FHKST01010200 | /uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn |
| 일별 시세 | FHKST01010400 | /uapi/domestic-stock/v1/quotations/inquire-daily-price |
| 주문 (매수/매도) | TTTC0802U / TTTC0801U | /uapi/domestic-stock/v1/trading/order-cash |

---

## 🎯 다음 단계 (Phase 2)

### 우선순위
1. **KIS API 인증 구현** (1주)
   - Access Token 발급
   - Token 갱신 로직
   - 에러 핸들링

2. **실시간 시세 조회** (1주)
   - 현재가 조회
   - 호가 조회
   - 캐싱 전략

3. **데이터 수집 자동화** (1주)
   - 스케줄링 (Celery 또는 APScheduler)
   - DB 저장
   - 에러 복구

4. **주문 시뮬레이션** (Phase 3)
   - 가상 주문 실행
   - 포트폴리오 업데이트

---

**작성자**: Claude Code
**최종 업데이트**: 2025-10-03
**상태**: ✅ Phase 1 데이터 모델 설계 완료

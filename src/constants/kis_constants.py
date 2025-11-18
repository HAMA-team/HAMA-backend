"""
한국투자증권 API 상수 정의
"""

# KIS API 기본 URL (환경별)
KIS_BASE_URLS = {
    "prod": "https://openapi.koreainvestment.com:9443",
    "demo": "https://openapivts.koreainvestment.com:29443",
}

# KIS API 엔드포인트
KIS_ENDPOINTS = {
    "auth": "/oauth2/tokenP",
    "balance": "/uapi/domestic-stock/v1/trading/inquire-balance",
    "account_balance": "/uapi/domestic-stock/v1/trading/inquire-account-balance",
    "stock_price": "/uapi/domestic-stock/v1/quotations/inquire-price",
    "stock_daily_price": "/uapi/domestic-stock/v1/quotations/inquire-daily-price",  # 국내주식 일자별 시세
    "investor_flow": "/uapi/domestic-stock/v1/quotations/inquire-investor",
    "financial_ratio": "/uapi/domestic-stock/v1/finance/financial-ratio",
    "order": "/uapi/domestic-stock/v1/trading/order-cash",
    # 지수 조회 관련
    "index_price": "/uapi/domestic-stock/v1/quotations/inquire-index-price",
    "index_daily_price": "/uapi/domestic-stock/v1/quotations/inquire-index-daily-price",
}

# KIS API TR ID (거래 ID)
KIS_TR_IDS = {
    "balance": {
        "real": "TTTC8434R",
        "demo": "VTTC8434R",
    },
    "stock_price": "FHKST01010100",
    "stock_daily_price": "FHKST03010100",  # 국내주식 일자별 시세
    "investor_flow": "FHKST01010900",
    "financial_ratio": "FHKST66430300",
    "order_buy": {
        "real": "TTTC0012U",
        "demo": "VTTC0012U",
    },
    "order_sell": {
        "real": "TTTC0011U",
        "demo": "VTTC0011U",
    },
    # 지수 조회 TR ID
    "index_price": "FHPUP02100000",  # 국내업종 현재지수
    "index_daily_price": "FHPUP02120000",  # 국내업종 일자별지수
}

# 지수 코드 매핑 (지수명 → KIS 코드)
INDEX_CODES = {
    "KOSPI": "0001",      # 코스피 지수
    "KOSDAQ": "1001",     # 코스닥 지수
    "KOSPI200": "2001",   # 코스피200
    "KRX100": "1028",     # KRX100 (기존 매핑과 다를 수 있으니 확인 필요)
}

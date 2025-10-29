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
    "order": "/uapi/domestic-stock/v1/trading/order-cash",
}

# KIS API TR ID (거래 ID)
KIS_TR_IDS = {
    "balance": {
        "real": "TTTC8434R",
        "demo": "VTTC8434R",
    },
    "stock_price": "FHKST01010100",
    "order_buy": {
        "real": "TTTC0012U",
        "demo": "VTTC0012U",
    },
    "order_sell": {
        "real": "TTTC0011U",
        "demo": "VTTC0011U",
    },
}

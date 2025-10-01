# 데이터 소스 통합 가이드

**버전**: 1.0
**작성일**: 2025-10-01
**목적**: Phase 1에서 사용할 모든 데이터 소스의 통합 방법을 구체적으로 명시

---

## 목차

1. [데이터 소스 개요](#데이터-소스-개요)
2. [pykrx - 주가 데이터](#1-pykrx---주가-데이터)
3. [DART API - 공시 및 재무제표](#2-dart-api---공시-및-재무제표)
4. [한국투자증권 API - 실시간 시세](#3-한국투자증권-api---실시간-시세)
5. [네이버 금융 - 뉴스 크롤링](#4-네이버-금융---뉴스-크롤링)
6. [통합 데이터 수집 에이전트](#5-통합-데이터-수집-에이전트)

---

## 데이터 소스 개요

### 필요한 데이터 유형

| 데이터 유형 | 소스 | 업데이트 주기 | 용도 |
|-----------|------|--------------|-----|
| **주가 데이터** | pykrx, 한투 API | 실시간 ~ 일봉 | 기술적 분석, 차트 |
| **재무제표** | DART API | 분기별 | 기업 분석, 가치 평가 |
| **공시 정보** | DART API | 실시간 | 중요 이벤트 감지 |
| **실시간 시세** | 한투 API | 실시간 | 현재가, 호가 |
| **뉴스** | 네이버 금융 | 실시간 | 센티먼트, 이벤트 |

### 우선순위

**Phase 1 필수 (P0)**:
1. pykrx (무료, 설치 즉시 사용)
2. DART API (무료, API 키 필요)

**Phase 1 권장 (P1)**:
3. 한국투자증권 API (무료, 계좌 필요)
4. 네이버 금융 크롤링 (무료, 제약 있음)

---

## 1. pykrx - 주가 데이터

### 개요

**라이브러리**: [sharebook-kr/pykrx](https://github.com/sharebook-kr/pykrx)

**장점**:
- ✅ 무료, API 키 불필요
- ✅ KRX 공식 데이터 (신뢰도 높음)
- ✅ 과거 데이터 20년 이상 제공
- ✅ 설치 즉시 사용 가능

**단점**:
- ⚠️ 실시간 아님 (당일 종가까지)
- ⚠️ 스크래핑 방식 (속도 느림: 20년 데이터 = 1분)

**추천 용도**:
- 기술적 지표 계산 (이동평균, RSI, MACD 등)
- 과거 데이터 백테스팅
- 종목 스크리닝

### 설치

```bash
pip install pykrx
```

### 기본 사용법

#### 1) 종목 코드 조회

```python
from pykrx import stock

# 특정 날짜의 KOSPI 전체 종목
tickers = stock.get_market_ticker_list("20251001", market="KOSPI")
print(tickers)
# ['005930', '000660', '051910', ...]

# 종목명으로 검색
ticker = stock.get_market_ticker_name("005930")
print(ticker)  # "삼성전자"

# 전체 종목명 매핑
ticker_names = {ticker: stock.get_market_ticker_name(ticker) for ticker in tickers}
```

#### 2) 주가 데이터 조회

```python
import pandas as pd

# 일봉 데이터 (OHLCV)
df = stock.get_market_ohlcv("20240101", "20251001", "005930")
print(df.head())
#             시가    고가    저가    종가      거래량
# 날짜
# 2024-01-02  74600  75000  74000  74500  15234567
# 2024-01-03  74500  75500  74200  75300  18456789
# ...

# 여러 종목 한번에
tickers = ["005930", "000660", "051910"]
all_data = {}
for ticker in tickers:
    all_data[ticker] = stock.get_market_ohlcv("20240101", "20251001", ticker)
```

#### 3) 투자자별 거래 데이터

```python
# 기관/외국인 매매 동향
df_investor = stock.get_market_trading_by_investor(
    "20240101", "20251001", "005930"
)
print(df_investor.head())
#             기관계    외국인    개인
# 날짜
# 2024-01-02  -123456  234567  -111111
# ...
```

#### 4) 시가총액 및 거래대금

```python
# 시가총액 TOP 종목
df_cap = stock.get_market_cap("20251001", market="KOSPI")
df_cap_sorted = df_cap.sort_values("시가총액", ascending=False).head(10)
print(df_cap_sorted)
```

### 실전 활용 예시

#### 기술적 지표 계산

```python
import pandas as pd
from pykrx import stock

def calculate_moving_averages(ticker: str, start: str, end: str):
    """이동평균선 계산"""
    df = stock.get_market_ohlcv(start, end, ticker)

    # 5일, 20일, 60일 이동평균
    df['MA5'] = df['종가'].rolling(window=5).mean()
    df['MA20'] = df['종가'].rolling(window=20).mean()
    df['MA60'] = df['종가'].rolling(window=60).mean()

    return df

def calculate_rsi(ticker: str, start: str, end: str, period: int = 14):
    """RSI 계산"""
    df = stock.get_market_ohlcv(start, end, ticker)

    delta = df['종가'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    df['RSI'] = rsi
    return df
```

### 캐싱 전략

pykrx는 속도가 느리므로 **반드시 캐싱 필요**

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=256)
def get_cached_ohlcv(ticker: str, start: str, end: str):
    """캐싱된 주가 데이터 조회"""
    return stock.get_market_ohlcv(start, end, ticker)

# 일별 캐시 (매일 자정 갱신)
def get_daily_cache_key():
    return datetime.now().strftime("%Y%m%d")

def get_today_ohlcv(ticker: str):
    cache_key = get_daily_cache_key()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    return get_cached_ohlcv(ticker, start_date, end_date)
```

### 제약사항 및 해결책

| 제약사항 | 해결책 |
|---------|--------|
| 느린 속도 | 캐싱 전략, 비동기 처리 |
| 실시간 아님 | 한투 API와 병행 사용 |
| 스크래핑 차단 가능성 | 요청 간격 조절, User-Agent |

---

## 2. DART API - 공시 및 재무제표

### 개요

**공식 사이트**: [https://opendart.fss.or.kr/](https://opendart.fss.or.kr/)

**추천 라이브러리**:
1. **OpenDartReader** (FinanceData) - 추천 ⭐
2. **dart-fss** (josw123) - 재무제표 특화

**장점**:
- ✅ 무료, 공식 API
- ✅ 재무제표, 공시 문서 전체 제공
- ✅ pandas DataFrame 반환 (OpenDartReader)
- ✅ 하루 10,000건 호출 가능

**단점**:
- ⚠️ API 키 발급 필요 (무료, 즉시 발급)
- ⚠️ 분기 데이터 (실시간 아님)

### API 키 발급

1. [OpenDART 회원가입](https://opendart.fss.or.kr/)
2. 로그인 → 인증키 신청/관리
3. API 키 즉시 발급 (이메일 전송)

### 설치

#### OpenDartReader (추천)

```bash
pip install opendart-reader
```

#### dart-fss (재무제표 특화)

```bash
pip install dart-fss
```

### OpenDartReader 사용법

#### 1) 초기화

```python
from opendart import OpenDartReader

# API 키 설정
api_key = "your-api-key-here"
dart = OpenDartReader(api_key)
```

#### 2) 기업 검색

```python
# 회사명으로 종목코드(corp_code) 찾기
# OpenDartReader는 자동 변환 지원

# 재무제표 조회 (종목코드 자동 변환)
df = dart.finstate("삼성전자", 2023)
print(df.head())
```

#### 3) 재무제표 조회

```python
# 연간 재무제표
df_annual = dart.finstate("005930", 2023, reprt_code="11011")
# reprt_code:
# - 11011: 사업보고서 (연간)
# - 11012: 반기보고서
# - 11013: 1분기보고서
# - 11014: 3분기보고서

# 분기 재무제표
df_q1 = dart.finstate("005930", 2024, reprt_code="11013")
```

#### 4) 주요 재무 지표 추출

```python
def get_financial_metrics(ticker: str, year: int):
    """주요 재무 지표 추출"""
    df = dart.finstate(ticker, year, reprt_code="11011")

    # 계정과목 필터링
    metrics = {}

    # 매출액
    revenue = df[df['account_nm'].str.contains('매출액')]['thstrm_amount'].iloc[0]
    metrics['revenue'] = int(revenue)

    # 영업이익
    op_profit = df[df['account_nm'].str.contains('영업이익')]['thstrm_amount'].iloc[0]
    metrics['operating_profit'] = int(op_profit)

    # 당기순이익
    net_income = df[df['account_nm'].str.contains('당기순이익')]['thstrm_amount'].iloc[0]
    metrics['net_income'] = int(net_income)

    # 총자산
    assets = df[df['account_nm'].str.contains('자산총계')]['thstrm_amount'].iloc[0]
    metrics['total_assets'] = int(assets)

    # 부채
    liabilities = df[df['account_nm'].str.contains('부채총계')]['thstrm_amount'].iloc[0]
    metrics['total_liabilities'] = int(liabilities)

    # 자본
    equity = df[df['account_nm'].str.contains('자본총계')]['thstrm_amount'].iloc[0]
    metrics['equity'] = int(equity)

    return metrics

# 사용 예시
metrics = get_financial_metrics("005930", 2023)
print(metrics)
# {
#   'revenue': 302231158000000,
#   'operating_profit': 35545401000000,
#   'net_income': 26950784000000,
#   ...
# }
```

#### 5) 재무 비율 계산

```python
def calculate_financial_ratios(metrics: dict):
    """재무 비율 계산"""
    ratios = {}

    # ROE (자기자본이익률)
    ratios['roe'] = metrics['net_income'] / metrics['equity']

    # ROA (총자산이익률)
    ratios['roa'] = metrics['net_income'] / metrics['total_assets']

    # 영업이익률
    ratios['operating_margin'] = metrics['operating_profit'] / metrics['revenue']

    # 순이익률
    ratios['net_margin'] = metrics['net_income'] / metrics['revenue']

    # 부채비율
    ratios['debt_ratio'] = metrics['total_liabilities'] / metrics['equity']

    return ratios

ratios = calculate_financial_ratios(metrics)
print(ratios)
# {'roe': 0.0857, 'roa': 0.0543, ...}
```

#### 6) 공시 검색

```python
# 최근 공시 조회
disclosures = dart.list(
    corp="005930",  # 삼성전자
    start="20240101",
    end="20241001"
)
print(disclosures.head())

# 특정 키워드 공시
important_disclosures = dart.list(
    corp="005930",
    start="20240101",
    end="20241001",
    kind="A",  # 정기공시
    final=False  # 정정 제외
)
```

### dart-fss 사용법 (재무제표 특화)

```python
import dart_fss as dart

# API 키 설정
api_key = "your-api-key-here"
dart.set_api_key(api_key)

# 기업 정보 검색
samsung = dart.crp_list.find_by_corp_name("삼성전자")[0]
print(samsung.corp_name)  # "삼성전자"
print(samsung.corp_code)  # "00126380"

# 재무제표 추출
fs = samsung.extract_fs(bgn_de="20230101", end_de="20231231")

# 손익계산서
income_statement = fs['income_statement']
print(income_statement)

# 재무상태표
balance_sheet = fs['balance_sheet']
print(balance_sheet)

# 현금흐름표
cashflow = fs['cashflow']
print(cashflow)
```

### 실전 활용 예시

#### 리서치 에이전트에서 사용

```python
from opendart import OpenDartReader
from dataclasses import dataclass

@dataclass
class FinancialAnalysis:
    ticker: str
    year: int
    profitability: dict
    growth: dict
    stability: dict
    valuation: dict

class ResearchAgent:
    def __init__(self, dart_api_key: str):
        self.dart = OpenDartReader(dart_api_key)

    def analyze_financials(self, ticker: str, year: int) -> FinancialAnalysis:
        # 재무제표 조회
        metrics = get_financial_metrics(ticker, year)
        ratios = calculate_financial_ratios(metrics)

        # 전년도 데이터로 성장률 계산
        prev_metrics = get_financial_metrics(ticker, year - 1)
        growth = {
            'revenue_growth': (metrics['revenue'] - prev_metrics['revenue']) / prev_metrics['revenue'],
            'profit_growth': (metrics['net_income'] - prev_metrics['net_income']) / prev_metrics['net_income']
        }

        return FinancialAnalysis(
            ticker=ticker,
            year=year,
            profitability={
                'roe': ratios['roe'],
                'roa': ratios['roa'],
                'net_margin': ratios['net_margin']
            },
            growth=growth,
            stability={
                'debt_ratio': ratios['debt_ratio']
            },
            valuation={}  # TODO: 주가 데이터와 결합
        )
```

### 캐싱 전략

재무제표는 분기별 업데이트이므로 **긴 캐시 유효기간**

```python
from functools import lru_cache
from datetime import datetime

@lru_cache(maxsize=512)
def get_cached_finstate(ticker: str, year: int, quarter: int):
    """분기별 재무제표 캐싱 (90일)"""
    reprt_code = {
        1: "11013",  # 1분기
        2: "11012",  # 반기
        3: "11014",  # 3분기
        4: "11011"   # 사업보고서
    }[quarter]

    return dart.finstate(ticker, year, reprt_code=reprt_code)
```

### 제약사항 및 해결책

| 제약사항 | 해결책 |
|---------|--------|
| 10,000건/일 제한 | 캐싱 (분기별 데이터는 변하지 않음) |
| 분기별 업데이트 | 실시간 데이터는 다른 소스 사용 |
| 계정과목명 표준화 안됨 | 정규표현식으로 유연하게 추출 |

---

## 3. 한국투자증권 API - 실시간 시세

### 개요

**공식 GitHub**: [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api)

**추천 라이브러리**:
1. **pykis** (pjueon) - 추천 ⭐
2. **python-kis** (Soju06) - 고급 기능

**장점**:
- ✅ 실시간 시세 (체결가, 호가)
- ✅ 주문 기능 (Phase 2에서 사용)
- ✅ 무료 (계좌 개설 필요)

**단점**:
- ⚠️ 한국투자증권 계좌 필요
- ⚠️ API 키 발급 절차 복잡
- ⚠️ 분당 요청 제한

**Phase 1 필요성**:
- P1 (선택 사항)
- pykrx로도 충분하나, 실시간 시세 필요 시 사용

### API 키 발급

1. [한국투자증권 계좌 개설](https://www.koreainvestment.com/)
2. [KIS Developers](https://apiportal.koreainvestment.com/) 접속
3. 앱 등록 → App Key, App Secret 발급
4. 모의투자 or 실전투자 선택

### 설치

```bash
pip install pykis
```

### pykis 기본 사용법

#### 1) 초기화

```python
from pykis import Api

# 모의투자 계좌
api = Api(
    account_no="모의계좌번호",
    app_key="YOUR_APP_KEY",
    app_secret="YOUR_APP_SECRET",
    virtual_account=True  # 모의투자
)

# 실전투자 계좌
api_real = Api(
    account_no="실전계좌번호",
    app_key="YOUR_APP_KEY",
    app_secret="YOUR_APP_SECRET",
    virtual_account=False
)
```

#### 2) 현재가 조회

```python
# 현재가
current_price = api.get_price("005930")
print(current_price)
# {
#   'stck_prpr': '74500',  # 현재가
#   'prdy_vrss': '500',    # 전일대비
#   'prdy_ctrt': '0.68',   # 등락률
#   'acml_vol': '15234567' # 누적거래량
# }
```

#### 3) 호가 조회

```python
# 실시간 호가
orderbook = api.get_orderbook("005930")
print(orderbook)
# {
#   'askp1': '74600',  # 매도호가1
#   'askp_rsqn1': '1234',  # 매도잔량1
#   'bidp1': '74500',  # 매수호가1
#   'bidp_rsqn1': '5678',  # 매수잔량1
#   ...
# }
```

#### 4) 일봉/분봉 데이터

```python
# 일봉 (최근 100일)
daily = api.get_ohlcv("005930", period="D", count=100)
print(daily.head())

# 분봉
minute = api.get_ohlcv("005930", period="m", count=100)
```

### 실전 활용 예시

#### 데이터 수집 에이전트에서 사용

```python
from pykis import Api
from functools import lru_cache
import time

class KISDataCollector:
    def __init__(self, app_key: str, app_secret: str, account_no: str):
        self.api = Api(
            account_no=account_no,
            app_key=app_key,
            app_secret=app_secret,
            virtual_account=True
        )
        self.last_request_time = {}

    def _rate_limit(self, ticker: str):
        """분당 요청 제한 (20회)"""
        now = time.time()
        if ticker in self.last_request_time:
            elapsed = now - self.last_request_time[ticker]
            if elapsed < 3:  # 3초 간격
                time.sleep(3 - elapsed)
        self.last_request_time[ticker] = time.time()

    def get_realtime_price(self, ticker: str) -> dict:
        """실시간 현재가"""
        self._rate_limit(ticker)
        return self.api.get_price(ticker)

    def get_realtime_orderbook(self, ticker: str) -> dict:
        """실시간 호가"""
        self._rate_limit(ticker)
        return self.api.get_orderbook(ticker)
```

### 제약사항 및 해결책

| 제약사항 | 해결책 |
|---------|--------|
| 분당 20회 제한 | Rate limiter 구현 |
| 계좌 필요 | 모의투자 계좌 사용 |
| Phase 1에서 선택사항 | pykrx로 대체 가능 |

---

## 4. 네이버 금융 - 뉴스 크롤링

### 개요

**참고 프로젝트**: [INVESTAR/StockAnalysisInPython](https://github.com/INVESTAR/StockAnalysisInPython)

**장점**:
- ✅ 무료
- ✅ 뉴스 데이터 풍부

**단점**:
- ⚠️ 공식 API 없음 (크롤링 필요)
- ⚠️ 2021년부터 스크래핑 차단 강화
- ⚠️ User-Agent 필수
- ⚠️ 법적 그레이존

**Phase 1 필요성**:
- P1 (선택 사항)
- 뉴스 센티먼트 분석에 사용

### 설치

```bash
pip install requests beautifulsoup4 lxml
```

### 기본 사용법

#### 1) 종목 뉴스 크롤링

```python
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def crawl_naver_stock_news(ticker: str, max_pages: int = 5):
    """네이버 금융 종목 뉴스 크롤링"""
    news_list = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    for page in range(1, max_pages + 1):
        url = f"https://finance.naver.com/item/news_news.naver?code={ticker}&page={page}"

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'lxml')

        # 뉴스 목록 파싱
        news_table = soup.select('table.type5 tr')

        for row in news_table:
            link = row.select_one('a.tit')
            if link:
                title = link.text.strip()
                news_url = "https://finance.naver.com" + link['href']
                date = row.select_one('td.date').text.strip()

                news_list.append({
                    'title': title,
                    'url': news_url,
                    'date': date
                })

        # 요청 간격 (차단 방지)
        import time
        time.sleep(1)

    return news_list

# 사용 예시
news = crawl_naver_stock_news("005930", max_pages=3)
for n in news[:5]:
    print(n['title'])
```

#### 2) 뉴스 본문 크롤링

```python
def crawl_news_content(news_url: str):
    """뉴스 본문 크롤링"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(news_url, headers=headers)
    soup = BeautifulSoup(response.text, 'lxml')

    # 네이버 뉴스 본문 추출
    content = soup.select_one('div#news_read') or soup.select_one('div#articleBody')

    if content:
        return content.text.strip()
    return ""
```

### 실전 활용 예시

#### 뉴스 모니터링 에이전트에서 사용

```python
from typing import List
import time

class NaverNewsCollector:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_recent_news(self, ticker: str, days: int = 7) -> List[dict]:
        """최근 N일 뉴스 조회"""
        news = crawl_naver_stock_news(ticker, max_pages=5)

        # 날짜 필터링 (간단 버전)
        recent_news = []
        for item in news:
            # TODO: 날짜 파싱 및 필터링
            recent_news.append(item)

        return recent_news

    def analyze_sentiment(self, news_list: List[dict]) -> dict:
        """뉴스 센티먼트 분석 (간단 버전)"""
        # TODO: LLM 기반 센티먼트 분석
        positive_keywords = ['상승', '호조', '성장', '개선']
        negative_keywords = ['하락', '부진', '감소', '악화']

        positive_count = 0
        negative_count = 0

        for news in news_list:
            title = news['title']
            if any(kw in title for kw in positive_keywords):
                positive_count += 1
            if any(kw in title for kw in negative_keywords):
                negative_count += 1

        total = positive_count + negative_count
        if total == 0:
            return {'sentiment': 'neutral', 'score': 0.5}

        score = positive_count / total
        sentiment = 'positive' if score > 0.6 else ('negative' if score < 0.4 else 'neutral')

        return {'sentiment': sentiment, 'score': score}
```

### 주의사항

**법적 리스크**:
- 네이버 이용약관 확인 필요
- 과도한 크롤링 금지
- 상업적 이용 제한 가능

**대안**:
- Phase 1에서는 뉴스 기능 최소화
- Phase 2에서 뉴스 API 서비스 고려 (예: 뉴스 API, Naver Search API)

### 제약사항 및 해결책

| 제약사항 | 해결책 |
|---------|--------|
| 스크래핑 차단 | User-Agent, 요청 간격 |
| 법적 리스크 | Phase 1에서는 최소화 |
| 구조 변경 가능성 | 파싱 로직 모듈화 |

---

## 5. 통합 데이터 수집 에이전트

### 설계

모든 데이터 소스를 통합 관리하는 **단일 진입점**

```python
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

@dataclass
class StockData:
    ticker: str
    price: dict
    financials: dict
    news: List[dict]
    technical_indicators: dict
    timestamp: str

class DataCollectionAgent:
    """통합 데이터 수집 에이전트"""

    def __init__(
        self,
        dart_api_key: str,
        kis_app_key: Optional[str] = None,
        kis_app_secret: Optional[str] = None,
        kis_account_no: Optional[str] = None
    ):
        # pykrx (설치만으로 사용 가능)
        self.pykrx = None  # import 시점에 초기화

        # DART API
        from opendart import OpenDartReader
        self.dart = OpenDartReader(dart_api_key)

        # 한국투자증권 API (선택)
        if kis_app_key:
            from pykis import Api
            self.kis = Api(
                account_no=kis_account_no,
                app_key=kis_app_key,
                app_secret=kis_app_secret,
                virtual_account=True
            )
        else:
            self.kis = None

        # 네이버 뉴스 크롤러 (선택)
        self.naver_news = NaverNewsCollector()

    async def collect_all_data(self, ticker: str) -> StockData:
        """모든 데이터 소스에서 데이터 수집 (병렬)"""
        import asyncio

        # 병렬 수집
        tasks = [
            self._get_price_data(ticker),
            self._get_financial_data(ticker),
            self._get_news_data(ticker),
            self._get_technical_indicators(ticker)
        ]

        price, financials, news, technical = await asyncio.gather(*tasks)

        return StockData(
            ticker=ticker,
            price=price,
            financials=financials,
            news=news,
            technical_indicators=technical,
            timestamp=pd.Timestamp.now().isoformat()
        )

    async def _get_price_data(self, ticker: str) -> dict:
        """가격 데이터 (pykrx or KIS API)"""
        if self.kis:
            # 실시간 데이터 (KIS API)
            return self.kis.get_price(ticker)
        else:
            # 당일 종가까지 (pykrx)
            from pykrx import stock
            today = pd.Timestamp.now().strftime("%Y%m%d")
            df = stock.get_market_ohlcv(today, today, ticker)
            return df.iloc[-1].to_dict() if not df.empty else {}

    async def _get_financial_data(self, ticker: str) -> dict:
        """재무 데이터 (DART API)"""
        year = pd.Timestamp.now().year
        try:
            metrics = get_financial_metrics(ticker, year)
            ratios = calculate_financial_ratios(metrics)
            return {**metrics, **ratios}
        except Exception as e:
            return {"error": str(e)}

    async def _get_news_data(self, ticker: str) -> List[dict]:
        """뉴스 데이터 (네이버 크롤링)"""
        try:
            return self.naver_news.get_recent_news(ticker, days=7)
        except Exception as e:
            return []

    async def _get_technical_indicators(self, ticker: str) -> dict:
        """기술적 지표 (pykrx)"""
        from pykrx import stock
        today = pd.Timestamp.now().strftime("%Y%m%d")
        start = (pd.Timestamp.now() - pd.Timedelta(days=120)).strftime("%Y%m%d")

        df = stock.get_market_ohlcv(start, today, ticker)

        # 이동평균
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['MA60'] = df['종가'].rolling(window=60).mean()

        # RSI
        delta = df['종가'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        latest = df.iloc[-1]
        return {
            'current_price': latest['종가'],
            'ma20': latest['MA20'],
            'ma60': latest['MA60'],
            'rsi': rsi.iloc[-1]
        }
```

### 사용 예시

```python
# 초기화
agent = DataCollectionAgent(
    dart_api_key="YOUR_DART_KEY",
    # KIS API는 선택사항
    # kis_app_key="YOUR_KIS_KEY",
    # kis_app_secret="YOUR_KIS_SECRET",
    # kis_account_no="YOUR_ACCOUNT_NO"
)

# 데이터 수집
import asyncio
data = asyncio.run(agent.collect_all_data("005930"))

print(data.price)
print(data.financials)
print(data.technical_indicators)
```

---

## 우선순위 요약

### Phase 1 구현 순서

1. **pykrx** (1일) - 즉시 사용 가능
2. **DART API** (2-3일) - API 키 발급 후
3. **통합 에이전트** (2일) - 1+2 통합
4. **한국투자증권 API** (3일, 선택) - 실시간 필요 시
5. **네이버 크롤링** (2일, 선택) - 뉴스 기능 필요 시

### 최소 구성 (P0)

- ✅ pykrx
- ✅ DART API (OpenDartReader)

### 권장 구성 (P0 + P1)

- ✅ pykrx
- ✅ DART API
- ✅ 한국투자증권 API (실시간 시세)
- ⚠️ 네이버 크롤링 (법적 검토 필요)

---

## 환경 변수 설정

`.env` 파일 예시:

```bash
# DART API
DART_API_KEY=your_dart_api_key_here

# 한국투자증권 API (선택)
KIS_APP_KEY=your_kis_app_key
KIS_APP_SECRET=your_kis_app_secret
KIS_ACCOUNT_NO=your_account_number

# 환경 설정
ENVIRONMENT=development  # development, production
CACHE_TTL=3600  # 캐시 유효시간 (초)
```

Python에서 로드:

```python
from dotenv import load_dotenv
import os

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")
KIS_APP_KEY = os.getenv("KIS_APP_KEY")
```

---

**문서 끝**

**다음 문서**: [에이전트 구현 상세](./agent-implementation-details.md)
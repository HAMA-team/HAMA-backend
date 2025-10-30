# Repository 기반 시장 데이터 로컬화

## 개요
- `StockRepository`, `StockPriceRepository`를 추가해 SQLAlchemy 세션 로직을 캡슐화했습니다.
- `StockDataService`는 조회 순서를 **DB → 캐시 → 외부 API**로 변경하고, pykrx 응답을 자동으로 DB에 적재합니다.
- `scripts/seed_market_data.py` CLI를 통해 시장/기간을 지정해 초기 데이터를 일괄 수집할 수 있습니다.

## 동작 흐름
1. `get_stock_listing` 호출 시
   - Repository에서 기존 종목 목록을 조회하고 있으면 바로 캐싱하여 반환
   - 없으면 pykrx API로 가져온 뒤 DB/캐시에 동시 저장
2. `get_stock_price` 호출 시
   - 최근 요청 기간보다 넉넉한 범위를 DB에서 조회
   - 데이터가 없을 때만 pykrx 호출 후 DB/캐시에 저장
3. `seed_market_data`는 종목 목록을 순회하며 지정한 일수만큼의 시세를 저장하며, 진행 상황을 로그로 남깁니다.

## 사용 예시
```bash
python scripts/seed_market_data.py --market KOSPI --days 90
python scripts/seed_market_data.py --market ALL --days 30 --limit 200
```

## 주의 사항
- Financial Statement/DART 관련 필드는 이번 작업 범위에서 제외했습니다.
- DB 스키마 변경이 없으므로 별도 마이그레이션이 필요하지 않습니다.
- `.env`의 `DATABASE_URL`과 pykrx 네트워크 접근이 정상인지 확인하세요.

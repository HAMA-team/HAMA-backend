# Repository 기반 시장 데이터 로컬화

## 개요
- `StockRepository`, `StockPriceRepository`, `StockIndicatorRepository` 등 Repository 계층을 확장했습니다.
- `StockDataService`는 조회 순서를 **DB → 캐시 → 외부 API**로 변경하고, pykrx 응답을 자동으로 DB와 기술적 지표 테이블에 적재합니다.
- `MacroDataService`를 통해 한국은행(BOK) 지표를 로컬 DB(`macro_indicators`)에 저장하고 재사용합니다.
- `scripts/seed_market_data.py`, `scripts/seed_macro_data.py` CLI로 초기 데이터를 일괄 수집할 수 있습니다.

## 동작 흐름
1. `get_stock_listing` 호출 시
   - Repository에서 기존 종목 목록을 조회하고 있으면 바로 캐싱하여 반환
   - 없으면 pykrx API로 가져온 뒤 DB/캐시에 동시 저장
2. `get_stock_price` 호출 시
   - 최근 요청 기간보다 넉넉한 범위를 DB에서 조회
   - 데이터가 없을 때만 pykrx 호출 후 DB/캐시에 저장
   - 최신 데이터를 기반으로 `stock_indicators`에 RSI/MACD/이동평균 등 기술적 지표를 저장
3. `MacroDataService`는 BOK API 호출 결과를 `macro_indicators`에 저장하며, 이후 조회는 DB를 우선합니다.
4. `seed_market_data`와 `seed_macro_data`는 종목/거시 지표를 일괄 적재하고 진행 상황을 출력합니다.

## 사용 예시
```bash
python scripts/seed_market_data.py --market KOSPI --days 90
python scripts/seed_market_data.py --market ALL --days 30 --limit 200
python scripts/seed_macro_data.py
```

## 주의 사항
- Financial Statement/DART 관련 필드는 이번 작업 범위에서 제외했습니다.
- 새 테이블(`stock_indicators`, `macro_indicators`)은 `init_db()` 실행 시 자동 생성됩니다. 운영 환경에서는 Alembic 등의 마이그레이션 도입을 권장합니다.
- `.env`의 `DATABASE_URL`, `BOK_API_KEY`와 pykrx/BOK 네트워크 접근이 정상인지 확인하세요.

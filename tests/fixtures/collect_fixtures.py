"""
실제 API를 호출하여 Fixture 데이터를 수집하는 스크립트

사용법:
    PYTHONPATH=. python tests/fixtures/collect_fixtures.py
"""
import asyncio
import json
from pathlib import Path

from src.services.dart_service import dart_service
from src.services.stock_data_service import stock_data_service


async def collect_dart_fixtures():
    """DART API 응답 수집"""
    print("📊 DART API Fixture 수집 중...")

    fixtures = {
        "corp_code_samsung": None,
        "financial_statement_samsung": None,
        "company_info_samsung": None,
        "corp_code_skhynix": None,
    }

    try:
        # 1. 삼성전자 종목코드 → 고유번호 매핑
        fixtures["corp_code_samsung"] = await dart_service.search_corp_code("005930")
        print(f"  ✅ 삼성전자 고유번호: {fixtures['corp_code_samsung']}")

        # 2. 삼성전자 재무제표 (최근 연간)
        if fixtures["corp_code_samsung"]:
            fixtures["financial_statement_samsung"] = await dart_service.get_financial_statement(
                corp_code=fixtures["corp_code_samsung"],
                bsns_year="2023",
                reprt_code="11011"  # 사업보고서
            )
            print(f"  ✅ 삼성전자 재무제표: {len(fixtures['financial_statement_samsung'])}개 항목")

        # 3. 삼성전자 기업 정보
        if fixtures["corp_code_samsung"]:
            fixtures["company_info_samsung"] = await dart_service.get_company_info(
                corp_code=fixtures["corp_code_samsung"]
            )
            print(f"  ✅ 삼성전자 기업정보: {fixtures['company_info_samsung'].get('corp_name', 'N/A')}")

        # 4. SK하이닉스 종목코드
        fixtures["corp_code_skhynix"] = await dart_service.search_corp_code("000660")
        print(f"  ✅ SK하이닉스 고유번호: {fixtures['corp_code_skhynix']}")

    except Exception as e:
        print(f"  ⚠️ DART API 오류: {e}")

    return fixtures


async def collect_fdr_fixtures():
    """FinanceDataReader 응답 수집"""
    print("\n📈 FinanceDataReader Fixture 수집 중...")

    fixtures = {
        "stock_price_samsung_1y": None,
        "stock_price_skhynix_1y": None,
        "kospi_stocks_list": None,
    }

    try:
        # 1. 삼성전자 1년 주가 데이터
        samsung_price = await stock_data_service.get_stock_price(
            stock_code="005930",
            days=365
        )
        if samsung_price is not None:
            # DataFrame → dict 변환
            fixtures["stock_price_samsung_1y"] = {
                "columns": samsung_price.columns.tolist(),
                "data": samsung_price.tail(30).to_dict('records'),  # 최근 30일만
                "shape": samsung_price.shape
            }
            print(f"  ✅ 삼성전자 주가: {samsung_price.shape[0]}일")

        # 2. SK하이닉스 1년 주가 데이터
        skhynix_price = await stock_data_service.get_stock_price(
            stock_code="000660",
            days=365
        )
        if skhynix_price is not None:
            fixtures["stock_price_skhynix_1y"] = {
                "columns": skhynix_price.columns.tolist(),
                "data": skhynix_price.tail(30).to_dict('records'),  # 최근 30일만
                "shape": skhynix_price.shape
            }
            print(f"  ✅ SK하이닉스 주가: {skhynix_price.shape[0]}일")

        # 3. KOSPI 종목 리스트 (샘플)
        kospi_list = await stock_data_service.get_kospi_stocks()
        if kospi_list is not None:
            fixtures["kospi_stocks_list"] = kospi_list.head(10).to_dict('records')
            print(f"  ✅ KOSPI 종목 리스트: {len(kospi_list)}개 (샘플 10개 저장)")

    except Exception as e:
        print(f"  ⚠️ FDR 오류: {e}")

    return fixtures


def create_portfolio_fixtures():
    """샘플 포트폴리오 데이터 생성"""
    print("\n💼 포트폴리오 Fixture 생성 중...")

    fixtures = {
        "portfolio_balanced": {
            "portfolio_id": "test-portfolio-001",
            "user_id": "test-user-001",
            "total_value": 10000000,
            "cash_balance": 2000000,
            "invested_amount": 8000000,
            "holdings": [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 50,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 3750000,
                    "weight": 0.375,
                    "profit_loss": 250000,
                    "profit_rate": 0.0714
                },
                {
                    "stock_code": "000660",
                    "stock_name": "SK하이닉스",
                    "quantity": 30,
                    "avg_price": 90000,
                    "current_price": 95000,
                    "market_value": 2850000,
                    "weight": 0.285,
                    "profit_loss": 150000,
                    "profit_rate": 0.0556
                },
                {
                    "stock_code": "035420",
                    "stock_name": "NAVER",
                    "quantity": 10,
                    "avg_price": 140000,
                    "current_price": 140000,
                    "market_value": 1400000,
                    "weight": 0.14,
                    "profit_loss": 0,
                    "profit_rate": 0.0
                }
            ]
        },
        "portfolio_concentrated": {
            "portfolio_id": "test-portfolio-002",
            "user_id": "test-user-001",
            "total_value": 5000000,
            "cash_balance": 500000,
            "invested_amount": 4500000,
            "holdings": [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 60,
                    "avg_price": 75000,
                    "current_price": 75000,
                    "market_value": 4500000,
                    "weight": 0.9,  # 90% 집중 → 고위험
                    "profit_loss": 0,
                    "profit_rate": 0.0
                }
            ]
        },
        "portfolio_empty": {
            "portfolio_id": "test-portfolio-003",
            "user_id": "test-user-001",
            "total_value": 10000000,
            "cash_balance": 10000000,
            "invested_amount": 0,
            "holdings": []
        }
    }

    print("  ✅ 균형 포트폴리오 (3종목, 분산)")
    print("  ✅ 집중 포트폴리오 (1종목, 90% 비중)")
    print("  ✅ 빈 포트폴리오 (현금 100%)")

    return fixtures


async def main():
    """Fixture 수집 메인 함수"""
    print("="*60)
    print("HAMA 테스트 Fixture 수집 시작")
    print("="*60)

    # 1. DART Fixture 수집
    dart_fixtures = await collect_dart_fixtures()

    # 2. FDR Fixture 수집
    fdr_fixtures = await collect_fdr_fixtures()

    # 3. Portfolio Fixture 생성
    portfolio_fixtures = create_portfolio_fixtures()

    # 4. JSON 파일로 저장
    print("\n💾 Fixture 파일 저장 중...")

    fixtures_dir = Path(__file__).parent

    # DART
    dart_path = fixtures_dir / "dart_responses.json"
    with open(dart_path, "w", encoding="utf-8") as f:
        json.dump(dart_fixtures, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✅ {dart_path}")

    # FDR
    fdr_path = fixtures_dir / "fdr_responses.json"
    with open(fdr_path, "w", encoding="utf-8") as f:
        json.dump(fdr_fixtures, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✅ {fdr_path}")

    # Portfolio
    portfolio_path = fixtures_dir / "portfolio_snapshots.json"
    with open(portfolio_path, "w", encoding="utf-8") as f:
        json.dump(portfolio_fixtures, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {portfolio_path}")

    print("\n" + "="*60)
    print("✅ Fixture 수집 완료!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

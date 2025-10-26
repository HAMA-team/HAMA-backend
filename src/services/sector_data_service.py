"""
섹터 데이터 서비스

10개 주요 섹터별 대표 종목 성과 수집
"""

import FinanceDataReader as fdr
from datetime import datetime, timedelta
from typing import Dict, List
from src.services.cache_manager import cache_manager


class SectorDataService:
    """섹터 데이터 서비스 - 대표 종목 기반"""

    # 10개 주요 섹터 및 대표 종목
    SECTORS = {
        "IT/전기전자": ["005930", "000660", "035420"],  # 삼성전자, SK하이닉스, NAVER
        "반도체": ["000660", "005930"],  # SK하이닉스, 삼성전자
        "헬스케어": ["207940", "068270"],  # 삼성바이오, 셀트리온
        "금융": ["055550", "086790"],  # 신한지주, KB금융
        "자동차": ["005380", "000270"],  # 현대차, 기아
        "화학": ["051910", "009830"],  # LG화학, 한화솔루션
        "철강": ["005490"],  # POSCO홀딩스
        "에너지": ["096770"],  # SK이노베이션
        "건설": ["000720", "047040"],  # 현대건설, 대우건설
        "소비재": ["271560", "097950"],  # 오리온, CJ제일제당
    }

    def __init__(self):
        pass

    def get_sector_performance(
        self,
        days: int = 30
    ) -> Dict[str, Dict]:
        """
        섹터별 성과 데이터 수집

        Args:
            days: 분석 기간 (일)

        Returns:
            {
                "IT/전기전자": {
                    "return": 15.5,  # 수익률 (%)
                    "stocks": ["005930", "000660"],
                    "top_stock": "000660",
                    "top_return": 20.3
                },
                ...
            }
        """
        cache_key = f"sector:performance:{days}"
        cached = cache_manager.get(cache_key)
        if cached:
            return cached

        end = datetime.now()
        start = end - timedelta(days=days)

        sector_data = {}

        for sector, stocks in self.SECTORS.items():
            sector_returns = []
            stock_returns = {}

            for stock_code in stocks[:3]:  # 최대 3개 종목
                try:
                    df = fdr.DataReader(stock_code, start, end)
                    if not df.empty and len(df) > 1:
                        # 수익률 계산
                        first_price = df.iloc[0]['Close']
                        last_price = df.iloc[-1]['Close']
                        returns = ((last_price - first_price) / first_price) * 100

                        sector_returns.append(returns)
                        stock_returns[stock_code] = returns
                except Exception as e:
                    print(f"⚠️ [Sector Service] {stock_code} error: {str(e)[:50]}")

            # 섹터 평균 수익률
            if sector_returns:
                avg_return = sum(sector_returns) / len(sector_returns)

                # 최고 수익 종목
                top_stock = max(stock_returns.items(), key=lambda x: x[1])

                sector_data[sector] = {
                    "return": round(avg_return, 2),
                    "stocks": list(stock_returns.keys()),
                    "stock_returns": stock_returns,
                    "top_stock": top_stock[0],
                    "top_return": round(top_stock[1], 2)
                }

        # 캐싱 (1시간)
        cache_manager.set(cache_key, sector_data, ttl=3600)

        return sector_data

    def get_sector_ranking(self, days: int = 30) -> List[Dict]:
        """
        섹터 성과 순위

        Args:
            days: 분석 기간

        Returns:
            [
                {"sector": "반도체", "return": 44.61, "rank": 1},
                ...
            ]
        """
        sector_perf = self.get_sector_performance(days)

        # 순위 정렬
        ranking = []
        for sector, data in sector_perf.items():
            ranking.append({
                "sector": sector,
                "return": data["return"],
                "top_stock": data["top_stock"],
            })

        ranking.sort(key=lambda x: x["return"], reverse=True)

        # 순위 추가
        for i, item in enumerate(ranking, 1):
            item["rank"] = i

        return ranking

    def get_overweight_sectors(
        self,
        days: int = 30,
        threshold: float = 5.0
    ) -> List[str]:
        """
        비중 확대 추천 섹터 (Overweight)

        Args:
            days: 분석 기간
            threshold: 기준 수익률 (%)

        Returns:
            비중 확대 섹터 리스트
        """
        sector_perf = self.get_sector_performance(days)

        overweight = []
        for sector, data in sector_perf.items():
            if data["return"] > threshold:
                overweight.append(sector)

        return overweight

    def get_underweight_sectors(
        self,
        days: int = 30,
        threshold: float = -3.0
    ) -> List[str]:
        """
        비중 축소 추천 섹터 (Underweight)

        Args:
            days: 분석 기간
            threshold: 기준 수익률 (%)

        Returns:
            비중 축소 섹터 리스트
        """
        sector_perf = self.get_sector_performance(days)

        underweight = []
        for sector, data in sector_perf.items():
            if data["return"] < threshold:
                underweight.append(sector)

        return underweight


# Global instance
sector_data_service = SectorDataService()

"""
섹터 데이터 서비스

Note: 현재 미구현 상태
실제 구현 시 DART API 또는 자체 DB에서 섹터-종목 매핑을 조회해야 함
"""

from typing import Dict, List


class SectorDataService:
    """
    섹터 데이터 서비스

    실제 구현 시:
    - DART API를 통한 업종 분류 조회
    - 자체 DB에 섹터-종목 매핑 테이블 구축
    - 실시간 섹터 성과 계산
    """

    def __init__(self):
        pass

    def get_sector_performance(
        self,
        days: int = 30
    ) -> Dict[str, Dict]:
        """
        섹터별 성과 데이터 수집 (미구현)
        """
        raise NotImplementedError("섹터 데이터는 실제 DB 또는 API에서 조회해야 합니다.")

    def get_sector_ranking(self, days: int = 30) -> List[Dict]:
        """
        섹터 성과 순위 (미구현)
        """
        raise NotImplementedError("섹터 데이터는 실제 DB 또는 API에서 조회해야 합니다.")

    def get_overweight_sectors(
        self,
        days: int = 30,
        threshold: float = 5.0
    ) -> List[str]:
        """
        비중 확대 추천 섹터 (미구현)
        """
        raise NotImplementedError("섹터 데이터는 실제 DB 또는 API에서 조회해야 합니다.")

    def get_underweight_sectors(
        self,
        days: int = 30,
        threshold: float = -3.0
    ) -> List[str]:
        """
        비중 축소 추천 섹터 (미구현)
        """
        raise NotImplementedError("섹터 데이터는 실제 DB 또는 API에서 조회해야 합니다.")


# Global instance
sector_data_service = SectorDataService()

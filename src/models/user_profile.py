"""
사용자 프로파일 모델

사용자의 투자 성향, 경험 수준, 행동 패턴 등을 저장
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from src.models.database import Base


class UserProfile(Base):
    """사용자 프로파일 테이블"""

    __tablename__ = "user_profiles"

    # Primary Key
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 투자 경험
    expertise_level = Column(
        String(50), nullable=False, default="intermediate"
    )  # beginner | intermediate | expert

    # 투자 성향 (스크리닝 결과)
    investment_style = Column(
        String(50), nullable=False, default="moderate"
    )  # conservative | moderate | aggressive
    risk_tolerance = Column(
        String(50), nullable=False, default="medium"
    )  # low | medium | high

    # 행동 패턴 (LLM 분석)
    avg_trades_per_day = Column(Float, nullable=True, default=1.0)
    preferred_sectors = Column(JSON, nullable=True, default=list)  # ["반도체", "배터리"]
    trading_style = Column(
        String(50), nullable=True, default="long_term"
    )  # short_term | long_term
    portfolio_concentration = Column(
        Float, nullable=True, default=0.5
    )  # 0.0-1.0 (집중도)

    # 기술적 이해도
    technical_level = Column(
        String(50), nullable=False, default="intermediate"
    )  # basic | intermediate | advanced

    # 선호 설정
    preferred_depth = Column(
        String(50), nullable=False, default="detailed"
    )  # brief | detailed | comprehensive
    wants_explanations = Column(Boolean, nullable=False, default=True)
    wants_analogies = Column(Boolean, nullable=False, default=False)

    # AI 생성 프로파일 (LLM)
    llm_generated_profile = Column(String, nullable=True)

    # 메타
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_updated = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "user_id": str(self.user_id),
            "expertise_level": self.expertise_level,
            "investment_style": self.investment_style,
            "risk_tolerance": self.risk_tolerance,
            "avg_trades_per_day": self.avg_trades_per_day,
            "preferred_sectors": self.preferred_sectors or [],
            "trading_style": self.trading_style,
            "portfolio_concentration": self.portfolio_concentration,
            "technical_level": self.technical_level,
            "preferred_depth": self.preferred_depth,
            "wants_explanations": self.wants_explanations,
            "wants_analogies": self.wants_analogies,
            "llm_generated_profile": self.llm_generated_profile,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat()
            if self.last_updated
            else None,
        }

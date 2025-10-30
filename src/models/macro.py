"""
매크로 경제 지표 모델
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, TIMESTAMP, Date, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.database import Base


class MacroIndicator(Base):
    """한국은행 등에서 수집한 거시 지표"""

    __tablename__ = "macro_indicators"

    indicator_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator_code = Column(String(50), nullable=False, index=True)  # 예: base_rate, cpi, usdkrw
    indicator_name = Column(String(200), nullable=False)
    frequency = Column(String(10), nullable=False)  # D, M, Q 등
    unit = Column(String(50))
    source = Column(String(50), default="BOK")
    country = Column(String(10), default="KR")

    reference_date = Column(Date, nullable=False, index=True)
    value = Column(DECIMAL(20, 6), nullable=False)

    raw_data = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    @property
    def reference_datetime(self) -> datetime:
        return datetime.combine(self.reference_date, datetime.min.time())

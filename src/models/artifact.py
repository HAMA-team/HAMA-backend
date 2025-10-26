"""
Artifact 관련 데이터베이스 모델
"""
from sqlalchemy import Column, String, Text, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.models.database import Base


class Artifact(Base):
    """AI 생성 콘텐츠 저장 (분석 결과, 포트폴리오, 전략 등)"""
    __tablename__ = "artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 기본 정보
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)  # Markdown 형식
    artifact_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # "analysis", "portfolio", "strategy", "research", "risk_report"

    # 메타데이터
    artifact_metadata = Column("metadata", JSON, default={})  # stock_code, created_from_message_id 등

    # 미리보기
    preview = Column(String(200))  # 첫 100자 정도

    # 타임스탬프
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # 소프트 삭제
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return f"<Artifact(id={self.artifact_id}, title={self.title}, type={self.artifact_type})>"

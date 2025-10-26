"""
Artifact 관련 Pydantic 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class ArtifactCreate(BaseModel):
    """Artifact 생성 요청"""
    title: str = Field(..., min_length=1, max_length=500, description="Artifact 제목")
    content: str = Field(..., min_length=1, description="Markdown 형식의 콘텐츠")
    artifact_type: str = Field(
        ...,
        description="Artifact 타입 (analysis, portfolio, strategy, research, risk_report)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="메타데이터 (stock_code, created_from_message_id 등)"
    )

    class Config:
        schema_extra = {
            "example": {
                "title": "삼성전자 분석 결과",
                "content": "## 삼성전자 종합 분석\n\n### 재무 분석\n...",
                "artifact_type": "analysis",
                "metadata": {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "created_from_message_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            }
        }


class ArtifactUpdate(BaseModel):
    """Artifact 수정 요청"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "title": "삼성전자 분석 결과 (수정됨)",
                "content": "## 업데이트된 분석\n...",
            }
        }


class ArtifactResponse(BaseModel):
    """Artifact 응답"""
    artifact_id: UUID
    user_id: UUID
    title: str
    content: str
    artifact_type: str
    metadata: Dict[str, Any]
    preview: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        fields = {
            "metadata": "artifact_metadata"  # ORM 필드 매핑
        }
        schema_extra = {
            "example": {
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "660e8400-e29b-41d4-a716-446655440001",
                "title": "삼성전자 분석 결과",
                "content": "## 삼성전자 종합 분석\n\n### 재무 분석\n...",
                "artifact_type": "analysis",
                "metadata": {
                    "stock_code": "005930",
                    "stock_name": "삼성전자"
                },
                "preview": "삼성전자 종합 분석: 재무 분석 결과...",
                "created_at": "2025-10-26T10:00:00Z",
                "updated_at": "2025-10-26T10:00:00Z"
            }
        }


class ArtifactListItem(BaseModel):
    """Artifact 목록 아이템 (요약 정보)"""
    artifact_id: UUID
    title: str
    artifact_type: str
    preview: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "삼성전자 분석 결과",
                "artifact_type": "analysis",
                "preview": "삼성전자 종합 분석: 재무 분석 결과...",
                "created_at": "2025-10-26T10:00:00Z"
            }
        }


class ArtifactListResponse(BaseModel):
    """Artifact 목록 응답"""
    items: List[ArtifactListItem]
    total: int
    limit: int
    offset: int

    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "삼성전자 분석 결과",
                        "artifact_type": "analysis",
                        "preview": "삼성전자 종합 분석: 재무 분석 결과...",
                        "created_at": "2025-10-26T10:00:00Z"
                    }
                ],
                "total": 42,
                "limit": 20,
                "offset": 0
            }
        }

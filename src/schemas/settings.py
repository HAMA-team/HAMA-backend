"""
Settings API 스키마 정의.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from src.schemas.hitl_config import HITLConfig


class InterventionSettingsResponse(BaseModel):
    """GET /settings/intervention 응답"""

    hitl_config: HITLConfig
    interrupt_points: List[str]


class InterventionSettingsUpdateRequest(BaseModel):
    """PUT /settings/intervention 요청"""

    hitl_config: HITLConfig
    confirm: bool = Field(..., description="사용자 변경 확인")


class InterventionSettingsUpdateResponse(BaseModel):
    """PUT /settings/intervention 응답"""

    success: bool
    message: str
    new_config: HITLConfig
    effective_from: str = "immediate"

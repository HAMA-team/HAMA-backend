"""
Settings API مرتبط 스키마 정의.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from src.schemas.hitl_config import HITLConfig


class AutomationLevelResponse(BaseModel):
    """GET /settings/automation-level 응답"""

    hitl_config: HITLConfig
    interrupt_points: List[str]


class AutomationLevelUpdateRequest(BaseModel):
    """PUT /settings/automation-level 요청"""

    hitl_config: HITLConfig
    confirm: bool = Field(..., description="사용자 변경 확인")


class AutomationLevelUpdateResponse(BaseModel):
    """PUT /settings/automation-level 응답"""

    success: bool
    message: str
    new_config: HITLConfig
    effective_from: str = "immediate"


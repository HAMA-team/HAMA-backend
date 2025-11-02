"""
Settings API مرتبط 스키마 정의.
"""
from __future__ import annotations

from typing import Dict, Any, List

from pydantic import BaseModel, Field

from src.schemas.hitl_config import HITLConfig, PRESET_PILOT, PRESET_COPILOT, PRESET_ADVISOR


class AutomationLevelResponse(BaseModel):
    """GET /settings/automation-level 응답"""

    hitl_config: HITLConfig
    preset_name: str
    description: str
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


class AutomationPresetMetadata(BaseModel):
    """자동화 프리셋 정보"""

    preset: str
    config: HITLConfig
    metadata: Dict[str, Any]


class AutomationPresetsResponse(BaseModel):
    """GET /settings/automation-levels 응답"""

    presets: List[AutomationPresetMetadata]
    custom_available: bool = True


"""
사용자 자동화(HITL) 설정 관련 API.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.database import get_db
from src.repositories.user_settings_repository import UserSettingsRepository
from src.schemas.hitl_config import (
    HITLConfig,
    PRESET_PILOT,
    PRESET_COPILOT,
    PRESET_ADVISOR,
    PRESET_METADATA,
    get_interrupt_points,
)
from src.schemas.settings import (
    AutomationLevelResponse,
    AutomationLevelUpdateRequest,
    AutomationLevelUpdateResponse,
    AutomationPresetsResponse,
    AutomationPresetMetadata,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])

DEMO_USER_ID = uuid.UUID(str(settings.demo_user_uuid))


def _ensure_repo(db: Session) -> UserSettingsRepository:
    """요청 스코프에서 사용할 Repository 생성."""
    return UserSettingsRepository(db)


def _resolve_metadata(config: HITLConfig) -> Dict[str, str]:
    preset_meta = PRESET_METADATA.get(config.preset)
    if preset_meta:
        return preset_meta
    # Custom인 경우 기본 설명 제공
    return {
        "name": "Custom",
        "description": "사용자 정의 프리셋",
        "features": [],
        "recommended_for": "고급 사용자",
    }


def _validate_custom_config(config: HITLConfig) -> None:
    """Custom 프리셋 검증."""
    if config.preset != "custom":
        return

    phases = config.phases
    has_any = any(
        [
            phases.data_collection,
            phases.analysis,
            phases.portfolio,
            phases.risk,
            phases.trade is True or phases.trade == "conditional",
        ]
    )

    if not has_any:
        raise HTTPException(
            status_code=422,
            detail="Custom 모드에서는 최소 한 개 이상의 HITL 단계가 활성화되어야 합니다.",
        )


@router.get("/automation-level", response_model=AutomationLevelResponse)
def get_automation_level(
    db: Session = Depends(get_db),
) -> AutomationLevelResponse:
    """
    현재 사용자의 HITL 설정을 반환한다.
    설정이 없으면 Copilot 프리셋을 기본값으로 사용한다.
    """
    repo = _ensure_repo(db)
    settings_row = repo.get_user_settings(DEMO_USER_ID)

    if settings_row:
        config = settings_row.as_hitl_config()
    else:
        config = PRESET_COPILOT.model_copy()

    metadata = _resolve_metadata(config)
    interrupt_points = get_interrupt_points(config)

    logger.info("📡 [Settings] HITL config 조회 preset=%s", config.preset)

    return AutomationLevelResponse(
        hitl_config=config,
        preset_name=metadata["name"],
        description=metadata["description"],
        interrupt_points=interrupt_points,
    )


@router.put("/automation-level", response_model=AutomationLevelUpdateResponse)
def update_automation_level(
    request: AutomationLevelUpdateRequest,
    db: Session = Depends(get_db),
) -> AutomationLevelUpdateResponse:
    """
    사용자 HITL 설정 저장.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="자동화 레벨 변경을 위해서는 confirm=true가 필요합니다.",
        )

    _validate_custom_config(request.hitl_config)

    repo = _ensure_repo(db)
    repo.upsert_hitl_config(DEMO_USER_ID, request.hitl_config)

    metadata = _resolve_metadata(request.hitl_config)

    logger.info(
        "✅ [Settings] HITL config 저장 완료 preset=%s", request.hitl_config.preset
    )

    return AutomationLevelUpdateResponse(
        success=True,
        message=f"{metadata['name']} 모드로 변경되었습니다",
        new_config=request.hitl_config,
    )


@router.get("/automation-levels", response_model=AutomationPresetsResponse)
def list_automation_levels() -> AutomationPresetsResponse:
    """
    사용 가능한 자동화 프리셋 목록을 반환한다.
    """
    presets = [
        AutomationPresetMetadata(
            preset="pilot",
            config=PRESET_PILOT.model_copy(),
            metadata=PRESET_METADATA["pilot"],
        ),
        AutomationPresetMetadata(
            preset="copilot",
            config=PRESET_COPILOT.model_copy(),
            metadata=PRESET_METADATA["copilot"],
        ),
        AutomationPresetMetadata(
            preset="advisor",
            config=PRESET_ADVISOR.model_copy(),
            metadata=PRESET_METADATA["advisor"],
        ),
    ]

    return AutomationPresetsResponse(presets=presets, custom_available=True)

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
    get_interrupt_points,
)
from src.schemas.settings import (
    AutomationLevelResponse,
    AutomationLevelUpdateRequest,
    AutomationLevelUpdateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])

DEMO_USER_ID = uuid.UUID(str(settings.demo_user_uuid))


def _ensure_repo(db: Session) -> UserSettingsRepository:
    """요청 스코프에서 사용할 Repository 생성."""
    return UserSettingsRepository(db)


def _validate_hitl_config(config: HITLConfig) -> None:
    """HITL 설정 검증."""
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
            detail="최소 한 개 이상의 HITL 단계가 활성화되어야 합니다.",
        )


@router.get("/intervention", response_model=AutomationLevelResponse)
def get_intervention_settings(
    db: Session = Depends(get_db),
) -> AutomationLevelResponse:
    """
    현재 사용자의 HITL 설정을 반환한다.
    설정이 없으면 기본값(모든 phase False)을 사용한다.
    """
    repo = _ensure_repo(db)
    settings_row = repo.get_user_settings(DEMO_USER_ID)

    if settings_row:
        config = settings_row.as_hitl_config()
    else:
        config = HITLConfig()  # 기본값

    interrupt_points = get_interrupt_points(config)

    logger.info("📡 [Settings] HITL config 조회")

    return AutomationLevelResponse(
        hitl_config=config,
        interrupt_points=interrupt_points,
    )


@router.put("/intervention", response_model=AutomationLevelUpdateResponse)
def update_intervention_settings(
    request: AutomationLevelUpdateRequest,
    db: Session = Depends(get_db),
) -> AutomationLevelUpdateResponse:
    """
    사용자 HITL 설정 저장.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="HITL 설정 변경을 위해서는 confirm=true가 필요합니다.",
        )

    _validate_hitl_config(request.hitl_config)

    repo = _ensure_repo(db)
    repo.upsert_hitl_config(DEMO_USER_ID, request.hitl_config)

    logger.info("✅ [Settings] HITL config 저장 완료")

    return AutomationLevelUpdateResponse(
        success=True,
        message="HITL 설정이 저장되었습니다",
        new_config=request.hitl_config,
    )

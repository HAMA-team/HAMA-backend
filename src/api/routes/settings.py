"""
사용자 설정 관련 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from sqlalchemy.orm import Session
from src.models.database import get_db
from src.models.user import User
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

DEMO_USER_UUID = settings.demo_user_uuid


class AutomationLevelResponse(BaseModel):
    """자동화 레벨 조회 응답"""
    level: int = Field(..., ge=1, le=3, description="자동화 레벨 (1=Pilot, 2=Copilot, 3=Advisor)")
    level_name: str = Field(..., description="레벨 명칭")
    description: str = Field(..., description="레벨 설명")
    interrupt_points: List[str] = Field(..., description="HITL 개입 지점")

    class Config:
        schema_extra = {
            "example": {
                "level": 2,
                "level_name": "코파일럿",
                "description": "AI가 제안하고, 중요한 결정만 승인합니다",
                "interrupt_points": ["전략 생성", "포트폴리오 구성", "매매 실행", "리밸런싱"]
            }
        }


class AutomationLevelUpdateRequest(BaseModel):
    """자동화 레벨 변경 요청"""
    level: int = Field(..., ge=1, le=3, description="변경할 자동화 레벨")
    confirm: bool = Field(default=False, description="변경 확인")

    class Config:
        schema_extra = {
            "example": {
                "level": 3,
                "confirm": True
            }
        }


class AutomationLevelUpdateResponse(BaseModel):
    """자동화 레벨 변경 응답"""
    level: int
    message: str

    class Config:
        schema_extra = {
            "example": {
                "level": 3,
                "message": "어드바이저 모드로 변경되었습니다. 향후 모든 결정에 승인이 필요합니다."
            }
        }


# 자동화 레벨 정의
AUTOMATION_LEVELS = {
    1: {
        "name": "파일럿",
        "description": "AI가 거의 모든 것을 처리합니다",
        "interrupt_points": ["고위험 매매", "리밸런싱 (분기 1회)"],
        "detail": "AI 자율성 85% - 월 1회 확인"
    },
    2: {
        "name": "코파일럿",
        "description": "AI가 제안하고, 중요한 결정만 승인합니다",
        "interrupt_points": ["전략 생성", "포트폴리오 구성", "매매 실행", "리밸런싱"],
        "detail": "AI 자율성 50% - 주 1-2회 알림"
    },
    3: {
        "name": "어드바이저",
        "description": "AI는 정보만 제공하고, 모든 결정을 직접 합니다",
        "interrupt_points": ["모든 전략 결정", "모든 매매", "모든 포트폴리오 변경"],
        "detail": "AI 자율성 20% - 일일 검토 가능"
    }
}


@router.get("/automation-level", response_model=AutomationLevelResponse)
async def get_automation_level(db: Session = Depends(get_db)):
    """
    현재 자동화 레벨 조회

    자동화 레벨:
    - 1 (Pilot): AI가 거의 모든 것을 처리
    - 2 (Copilot): AI가 제안, 큰 결정만 승인 (기본값)
    - 3 (Advisor): AI는 정보만 제공, 사용자가 결정
    """
    # Demo 사용자 조회
    user = db.query(User).filter(User.user_id == str(DEMO_USER_UUID)).first()

    if not user:
        # 기본값: 코파일럿 모드
        level = 2
    else:
        level = user.automation_level or 2

    level_info = AUTOMATION_LEVELS.get(level, AUTOMATION_LEVELS[2])

    return AutomationLevelResponse(
        level=level,
        level_name=level_info["name"],
        description=level_info["description"],
        interrupt_points=level_info["interrupt_points"]
    )


@router.put("/automation-level", response_model=AutomationLevelUpdateResponse)
async def update_automation_level(
    request: AutomationLevelUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    자동화 레벨 변경

    Request:
    ```json
    {
        "level": 3,
        "confirm": true
    }
    ```

    변경 영향:
    - Level 1 → 2: 향후 매매 시 승인 필요
    - Level 2 → 1: 향후 매매가 자동 실행 (고위험만 승인)
    - Level 2 → 3: 향후 모든 결정에 승인 필요
    """
    new_level = request.level

    if new_level not in AUTOMATION_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid automation level: {new_level}. Must be 1, 2, or 3."
        )

    # Demo 사용자 조회 또는 생성
    user = db.query(User).filter(User.user_id == str(DEMO_USER_UUID)).first()

    if not user:
        # 사용자 생성
        from src.models.user import InvestmentStyle, RiskTolerance

        user = User(
            user_id=str(DEMO_USER_UUID),
            username="demo_user",
            email="demo@hama.ai",
            investment_style=InvestmentStyle.MODERATE,
            risk_tolerance=RiskTolerance.MEDIUM,
            automation_level=new_level
        )
        db.add(user)
    else:
        # 기존 레벨
        old_level = user.automation_level or 2

        # 레벨 변경
        user.automation_level = new_level

        logger.info(f"Automation level changed: {old_level} → {new_level}")

    db.commit()
    db.refresh(user)

    # 변경 메시지 생성
    level_info = AUTOMATION_LEVELS[new_level]
    message = f"{level_info['name']} 모드로 변경되었습니다. {level_info['description']}"

    return AutomationLevelUpdateResponse(
        level=new_level,
        message=message
    )


@router.get("/automation-levels")
async def list_automation_levels():
    """
    사용 가능한 자동화 레벨 목록

    Response:
    ```json
    {
        "levels": [
            {
                "level": 1,
                "name": "파일럿",
                "description": "...",
                "interrupt_points": [...],
                "detail": "..."
            },
            ...
        ]
    }
    ```
    """
    levels = [
        {
            "level": level,
            "name": info["name"],
            "description": info["description"],
            "interrupt_points": info["interrupt_points"],
            "detail": info["detail"]
        }
        for level, info in AUTOMATION_LEVELS.items()
    ]

    return {"levels": levels}

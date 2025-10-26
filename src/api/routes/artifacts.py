"""
Artifact 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import logging

from src.models.database import get_db
from src.schemas.artifact import (
    ArtifactCreate,
    ArtifactUpdate,
    ArtifactResponse,
    ArtifactListItem,
    ArtifactListResponse
)
from src.services import artifact_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Demo 사용자 UUID (MVP에서는 인증 없이 사용)
DEMO_USER_UUID = settings.demo_user_uuid


@router.post("/", response_model=ArtifactResponse, status_code=201)
async def create_artifact(
    artifact: ArtifactCreate,
    db: Session = Depends(get_db)
):
    """
    Artifact 생성

    **Request Body:**
    ```json
    {
        "title": "삼성전자 분석 결과",
        "content": "## 삼성전자 종합 분석\\n\\n### 재무 분석\\n...",
        "artifact_type": "analysis",
        "metadata": {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "created_from_message_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    }
    ```

    **Artifact Types:**
    - `analysis`: 종목 분석 결과
    - `portfolio`: 포트폴리오 구성
    - `strategy`: 투자 전략
    - `research`: 리서치 보고서
    - `risk_report`: 리스크 분석

    **Response:**
    - 생성된 Artifact 전체 정보
    - `artifact_id`를 저장하여 나중에 조회/수정 가능
    """
    try:
        created_artifact = artifact_service.create_artifact(
            db=db,
            user_id=DEMO_USER_UUID,
            artifact_data=artifact
        )

        logger.info(f"Artifact created: {created_artifact.artifact_id}, type: {created_artifact.artifact_type}")

        return created_artifact

    except Exception as e:
        logger.error(f"Failed to create artifact: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create artifact: {str(e)}"
        )


@router.get("/", response_model=ArtifactListResponse)
async def list_artifacts(
    artifact_type: Optional[str] = Query(None, description="필터링할 타입 (analysis, portfolio, strategy 등)"),
    limit: int = Query(20, ge=1, le=100, description="페이지 크기"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db)
):
    """
    Artifact 목록 조회

    **Query Parameters:**
    - `artifact_type` (선택): 특정 타입만 조회 (예: `analysis`)
    - `limit`: 페이지 크기 (기본값: 20, 최대: 100)
    - `offset`: 오프셋 (기본값: 0)

    **Response:**
    ```json
    {
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
    ```

    **사용 예:**
    - 모든 Artifact: `GET /artifacts`
    - 분석만: `GET /artifacts?artifact_type=analysis`
    - 2페이지: `GET /artifacts?limit=20&offset=20`
    """
    try:
        items, total = artifact_service.list_artifacts(
            db=db,
            user_id=DEMO_USER_UUID,
            artifact_type=artifact_type,
            limit=limit,
            offset=offset
        )

        # ArtifactListItem으로 변환 (ORM 모델 → Pydantic)
        list_items = [
            ArtifactListItem(
                artifact_id=item.artifact_id,
                title=item.title,
                artifact_type=item.artifact_type,
                preview=item.preview,
                created_at=item.created_at
            )
            for item in items
        ]

        return ArtifactListResponse(
            items=list_items,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list artifacts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list artifacts: {str(e)}"
        )


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Artifact 상세 조회

    **Path Parameters:**
    - `artifact_id`: Artifact UUID

    **Response:**
    - Artifact 전체 정보 (title, content, metadata 등)

    **에러:**
    - `404`: Artifact가 존재하지 않거나 삭제됨
    """
    artifact = artifact_service.get_artifact(
        db=db,
        artifact_id=artifact_id,
        user_id=DEMO_USER_UUID
    )

    if not artifact:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {artifact_id}"
        )

    return artifact


@router.put("/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    artifact_id: UUID,
    update_data: ArtifactUpdate,
    db: Session = Depends(get_db)
):
    """
    Artifact 수정

    **Path Parameters:**
    - `artifact_id`: Artifact UUID

    **Request Body:**
    ```json
    {
        "title": "삼성전자 분석 결과 (수정됨)",
        "content": "## 업데이트된 분석\\n...",
        "metadata": {
            "updated_reason": "최신 재무제표 반영"
        }
    }
    ```

    **참고:**
    - 수정하지 않을 필드는 생략 가능
    - `content` 수정 시 `preview`도 자동 업데이트

    **에러:**
    - `404`: Artifact가 존재하지 않음
    """
    updated_artifact = artifact_service.update_artifact(
        db=db,
        artifact_id=artifact_id,
        user_id=DEMO_USER_UUID,
        update_data=update_data
    )

    if not updated_artifact:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {artifact_id}"
        )

    logger.info(f"Artifact updated: {artifact_id}")

    return updated_artifact


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Artifact 삭제 (소프트 삭제)

    **Path Parameters:**
    - `artifact_id`: Artifact UUID

    **참고:**
    - 실제로는 소프트 삭제 (deleted_at 타임스탬프 설정)
    - 목록 조회 시 표시되지 않음

    **에러:**
    - `404`: Artifact가 존재하지 않음
    """
    success = artifact_service.delete_artifact(
        db=db,
        artifact_id=artifact_id,
        user_id=DEMO_USER_UUID
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {artifact_id}"
        )

    logger.info(f"Artifact deleted: {artifact_id}")

    # 204 No Content
    return None

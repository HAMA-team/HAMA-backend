"""
Artifact 관련 비즈니스 로직
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.artifact import Artifact
from src.schemas.artifact import ArtifactCreate, ArtifactUpdate


def create_preview(content: str, max_length: int = 200) -> str:
    """
    콘텐츠에서 미리보기 텍스트 생성

    Args:
        content: Markdown 콘텐츠
        max_length: 최대 길이

    Returns:
        미리보기 텍스트
    """
    # Markdown 헤더 제거 (##, ###)
    lines = content.split("\n")
    text_lines = [line.lstrip("#").strip() for line in lines if line.strip() and not line.strip().startswith("#")]

    # 빈 줄이 아닌 첫 번째 줄 사용
    preview_text = ""
    for line in text_lines:
        if line:
            preview_text = line
            break

    # 길이 제한
    if len(preview_text) > max_length:
        preview_text = preview_text[:max_length - 3] + "..."

    return preview_text


def create_artifact(
    db: Session,
    user_id: UUID,
    artifact_data: ArtifactCreate
) -> Artifact:
    """
    Artifact 생성

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        artifact_data: Artifact 생성 데이터

    Returns:
        생성된 Artifact
    """
    # 미리보기 생성
    preview = create_preview(artifact_data.content)

    # Artifact 생성
    artifact = Artifact(
        user_id=user_id,
        title=artifact_data.title,
        content=artifact_data.content,
        artifact_type=artifact_data.artifact_type,
        artifact_metadata=artifact_data.metadata or {},
        preview=preview
    )

    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return artifact


def get_artifact(
    db: Session,
    artifact_id: UUID,
    user_id: UUID
) -> Optional[Artifact]:
    """
    Artifact 조회

    Args:
        db: 데이터베이스 세션
        artifact_id: Artifact ID
        user_id: 사용자 ID

    Returns:
        Artifact 또는 None
    """
    return db.query(Artifact).filter(
        Artifact.artifact_id == artifact_id,
        Artifact.user_id == user_id,
        Artifact.deleted_at.is_(None)  # 소프트 삭제되지 않은 것만
    ).first()


def list_artifacts(
    db: Session,
    user_id: UUID,
    artifact_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> tuple[List[Artifact], int]:
    """
    Artifact 목록 조회

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        artifact_type: 필터링할 타입 (선택)
        limit: 페이지 크기
        offset: 오프셋

    Returns:
        (Artifact 목록, 전체 개수)
    """
    query = db.query(Artifact).filter(
        Artifact.user_id == user_id,
        Artifact.deleted_at.is_(None)
    )

    # 타입 필터
    if artifact_type:
        query = query.filter(Artifact.artifact_type == artifact_type)

    # 전체 개수
    total = query.count()

    # 최신순 정렬 및 페이징
    items = query.order_by(desc(Artifact.created_at)).limit(limit).offset(offset).all()

    return items, total


def update_artifact(
    db: Session,
    artifact_id: UUID,
    user_id: UUID,
    update_data: ArtifactUpdate
) -> Optional[Artifact]:
    """
    Artifact 수정

    Args:
        db: 데이터베이스 세션
        artifact_id: Artifact ID
        user_id: 사용자 ID
        update_data: 수정 데이터

    Returns:
        수정된 Artifact 또는 None
    """
    artifact = get_artifact(db, artifact_id, user_id)
    if not artifact:
        return None

    # 수정 가능한 필드만 업데이트
    if update_data.title is not None:
        artifact.title = update_data.title

    if update_data.content is not None:
        artifact.content = update_data.content
        # 콘텐츠 변경 시 미리보기도 업데이트
        artifact.preview = create_preview(update_data.content)

    if update_data.metadata is not None:
        artifact.artifact_metadata = update_data.metadata

    db.commit()
    db.refresh(artifact)

    return artifact


def delete_artifact(
    db: Session,
    artifact_id: UUID,
    user_id: UUID
) -> bool:
    """
    Artifact 삭제 (소프트 삭제)

    Args:
        db: 데이터베이스 세션
        artifact_id: Artifact ID
        user_id: 사용자 ID

    Returns:
        삭제 성공 여부
    """
    artifact = get_artifact(db, artifact_id, user_id)
    if not artifact:
        return False

    # 소프트 삭제
    from datetime import datetime
    artifact.deleted_at = datetime.utcnow()

    db.commit()

    return True

"""
Artifact Service 테스트
"""
import pytest
from uuid import UUID
from sqlalchemy.orm import Session

from src.models.database import SessionLocal
from src.models.artifact import Artifact
from src.schemas.artifact import ArtifactCreate, ArtifactUpdate
from src.services import artifact_service
from src.config.settings import settings


DEMO_USER_UUID = settings.demo_user_uuid


class TestArtifactService:
    """Artifact Service 테스트"""

    def setup_method(self):
        """테스트 전 초기화"""
        self.db: Session = SessionLocal()
        # 기존 테스트 데이터 정리
        self.db.query(Artifact).filter(
            Artifact.user_id == DEMO_USER_UUID
        ).delete()
        self.db.commit()

    def teardown_method(self):
        """테스트 후 정리"""
        # 테스트 데이터 정리
        self.db.query(Artifact).filter(
            Artifact.user_id == DEMO_USER_UUID
        ).delete()
        self.db.commit()
        self.db.close()

    def test_create_artifact(self):
        """Artifact 생성 테스트"""
        # Given
        artifact_data = ArtifactCreate(
            title="테스트 분석 보고서",
            content="## 삼성전자 분석\n\n### 재무제표 분석\n매출이 증가하고 있습니다.",
            artifact_type="analysis",
            metadata={"stock_code": "005930", "stock_name": "삼성전자"}
        )

        # When
        artifact = artifact_service.create_artifact(
            db=self.db,
            user_id=DEMO_USER_UUID,
            artifact_data=artifact_data
        )

        # Then
        assert artifact.artifact_id is not None
        assert artifact.title == "테스트 분석 보고서"
        assert artifact.artifact_type == "analysis"
        assert artifact.artifact_metadata["stock_code"] == "005930"
        assert artifact.preview is not None
        assert "매출" in artifact.preview or "증가" in artifact.preview  # 실제 내용 검증
        print(f"✅ Artifact 생성 성공: {artifact.artifact_id}")
        print(f"   미리보기: {artifact.preview}")

    def test_get_artifact(self):
        """Artifact 조회 테스트"""
        # Given: Artifact 먼저 생성
        created = artifact_service.create_artifact(
            db=self.db,
            user_id=DEMO_USER_UUID,
            artifact_data=ArtifactCreate(
                title="조회 테스트",
                content="테스트 콘텐츠",
                artifact_type="portfolio"
            )
        )

        # When
        artifact = artifact_service.get_artifact(
            db=self.db,
            artifact_id=created.artifact_id,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert artifact is not None
        assert artifact.artifact_id == created.artifact_id
        assert artifact.title == "조회 테스트"
        print(f"✅ Artifact 조회 성공: {artifact.artifact_id}")

    def test_get_artifact_not_found(self):
        """존재하지 않는 Artifact 조회 테스트"""
        # Given
        fake_id = UUID("00000000-0000-0000-0000-000000000000")

        # When
        artifact = artifact_service.get_artifact(
            db=self.db,
            artifact_id=fake_id,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert artifact is None
        print("✅ 존재하지 않는 Artifact 조회 성공 (None 반환)")

    def test_list_artifacts(self):
        """Artifact 목록 조회 테스트"""
        # Given: 여러 Artifact 생성
        for i in range(5):
            artifact_service.create_artifact(
                db=self.db,
                user_id=DEMO_USER_UUID,
                artifact_data=ArtifactCreate(
                    title=f"분석 보고서 {i+1}",
                    content=f"내용 {i+1}",
                    artifact_type="analysis" if i % 2 == 0 else "portfolio"
                )
            )

        # When: 전체 조회
        items, total = artifact_service.list_artifacts(
            db=self.db,
            user_id=DEMO_USER_UUID,
            limit=10,
            offset=0
        )

        # Then
        assert total == 5
        assert len(items) == 5
        print(f"✅ 전체 목록 조회 성공: {total}개")

        # When: 타입 필터링 (analysis만)
        items, total = artifact_service.list_artifacts(
            db=self.db,
            user_id=DEMO_USER_UUID,
            artifact_type="analysis",
            limit=10,
            offset=0
        )

        # Then
        assert total == 3  # 0, 2, 4번 인덱스
        assert all(item.artifact_type == "analysis" for item in items)
        print(f"✅ 타입 필터링 성공: {total}개 (analysis)")

        # When: 페이징 (2개씩, 2페이지)
        items_page1, total = artifact_service.list_artifacts(
            db=self.db,
            user_id=DEMO_USER_UUID,
            limit=2,
            offset=0
        )
        items_page2, _ = artifact_service.list_artifacts(
            db=self.db,
            user_id=DEMO_USER_UUID,
            limit=2,
            offset=2
        )

        # Then
        assert len(items_page1) == 2
        assert len(items_page2) == 2
        assert items_page1[0].artifact_id != items_page2[0].artifact_id
        print(f"✅ 페이징 성공: 1페이지={len(items_page1)}개, 2페이지={len(items_page2)}개")

    def test_update_artifact(self):
        """Artifact 수정 테스트"""
        # Given
        created = artifact_service.create_artifact(
            db=self.db,
            user_id=DEMO_USER_UUID,
            artifact_data=ArtifactCreate(
                title="원래 제목",
                content="원래 내용",
                artifact_type="strategy"
            )
        )

        # When
        updated = artifact_service.update_artifact(
            db=self.db,
            artifact_id=created.artifact_id,
            user_id=DEMO_USER_UUID,
            update_data=ArtifactUpdate(
                title="수정된 제목",
                content="수정된 내용입니다. 이제 내용이 더 길어졌습니다."
            )
        )

        # Then
        assert updated is not None
        assert updated.title == "수정된 제목"
        assert updated.content == "수정된 내용입니다. 이제 내용이 더 길어졌습니다."
        assert updated.preview == "수정된 내용입니다. 이제 내용이 더 길어졌습니다."
        print(f"✅ Artifact 수정 성공")
        print(f"   제목: {updated.title}")
        print(f"   미리보기: {updated.preview}")

    def test_delete_artifact(self):
        """Artifact 삭제 테스트 (소프트 삭제)"""
        # Given
        created = artifact_service.create_artifact(
            db=self.db,
            user_id=DEMO_USER_UUID,
            artifact_data=ArtifactCreate(
                title="삭제될 Artifact",
                content="삭제 테스트",
                artifact_type="research"
            )
        )

        # When
        success = artifact_service.delete_artifact(
            db=self.db,
            artifact_id=created.artifact_id,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert success is True
        print(f"✅ Artifact 삭제 성공")

        # Verify: 조회 불가능 (소프트 삭제됨)
        artifact = artifact_service.get_artifact(
            db=self.db,
            artifact_id=created.artifact_id,
            user_id=DEMO_USER_UUID
        )
        assert artifact is None
        print("✅ 삭제된 Artifact 조회 불가 확인 (소프트 삭제)")

        # Verify: 목록에도 표시 안 됨
        items, total = artifact_service.list_artifacts(
            db=self.db,
            user_id=DEMO_USER_UUID
        )
        assert not any(item.artifact_id == created.artifact_id for item in items)
        print("✅ 삭제된 Artifact가 목록에 표시되지 않음 확인")

    def test_create_preview(self):
        """미리보기 생성 테스트"""
        # Test 1: 짧은 텍스트
        short_text = "짧은 내용입니다."
        preview = artifact_service.create_preview(short_text)
        assert preview == short_text
        print(f"✅ 짧은 텍스트 미리보기: {preview}")

        # Test 2: Markdown 헤더 제거
        markdown_text = "## 제목\n\n실제 내용입니다.\n\n### 소제목\n\n추가 내용"
        preview = artifact_service.create_preview(markdown_text)
        assert preview == "실제 내용입니다."
        print(f"✅ Markdown 헤더 제거: {preview}")

        # Test 3: 긴 텍스트 자르기
        long_text = "가" * 300
        preview = artifact_service.create_preview(long_text, max_length=200)
        assert len(preview) <= 200
        assert preview.endswith("...")
        print(f"✅ 긴 텍스트 자르기: {len(preview)}자 (최대 200자)")


if __name__ == "__main__":
    """직접 실행"""
    import asyncio

    tester = TestArtifactService()

    print("\n=== Artifact Service 테스트 시작 ===\n")

    tester.setup_method()
    try:
        tester.test_create_artifact()
        print()

        tester.test_get_artifact()
        print()

        tester.test_get_artifact_not_found()
        print()

        tester.test_list_artifacts()
        print()

        tester.test_update_artifact()
        print()

        tester.test_delete_artifact()
        print()

        tester.test_create_preview()
        print()

        print("=== 모든 테스트 통과 ✅ ===")
    finally:
        tester.teardown_method()

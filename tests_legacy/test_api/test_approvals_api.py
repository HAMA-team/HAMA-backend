"""
Approval History API 통합 테스트
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.models.database import SessionLocal
from src.models.agent import ApprovalRequest, UserDecision
from src.services import approval_service
from src.config.settings import settings

DEMO_USER_UUID = settings.demo_user_uuid


class TestApprovalHistoryAPI:
    """Approval History API 통합 테스트"""

    def setup_method(self):
        """테스트 전 초기화"""
        self.db: Session = SessionLocal()
        # 기존 테스트 데이터 정리
        self.db.query(UserDecision).filter(
            UserDecision.user_id == DEMO_USER_UUID
        ).delete()
        self.db.query(ApprovalRequest).filter(
            ApprovalRequest.user_id == DEMO_USER_UUID
        ).delete()
        self.db.commit()

    def teardown_method(self):
        """테스트 후 정리"""
        # 테스트 데이터 정리
        self.db.query(UserDecision).filter(
            UserDecision.user_id == DEMO_USER_UUID
        ).delete()
        self.db.query(ApprovalRequest).filter(
            ApprovalRequest.user_id == DEMO_USER_UUID
        ).delete()
        self.db.commit()
        self.db.close()

    def test_list_approval_history_empty(self):
        """빈 승인 이력 조회 테스트"""
        # When
        items, total = approval_service.list_approval_history(
            db=self.db,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert total == 0
        assert len(items) == 0
        print("✅ 빈 승인 이력 조회 성공")

    def test_create_and_list_approval_history(self):
        """승인 요청 생성 및 목록 조회 테스트"""
        # Given: 승인 요청 생성
        approval_request = ApprovalRequest(
            request_id=uuid4(),
            user_id=DEMO_USER_UUID,
            request_type="trade",
            request_title="삼성전자 매수 승인 요청",
            request_description="AI가 분석한 매수 기회입니다.",
            proposed_actions={
                "action": "buy",
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 131,
                "price": 76300,
                "total_amount": 10000000
            },
            impact_analysis={
                "current_weight": 0.25,
                "expected_weight": 0.43
            },
            risk_warnings=["단일 종목 집중도가 40%를 초과합니다"],
            status="pending",
            created_at=datetime.utcnow()
        )
        self.db.add(approval_request)
        self.db.commit()

        # When
        items, total = approval_service.list_approval_history(
            db=self.db,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert total == 1
        assert len(items) == 1
        item = items[0]
        assert item["request_type"] == "trade"
        assert item["request_title"] == "삼성전자 매수 승인 요청"
        assert item["status"] == "pending"
        assert item["stock_code"] == "005930"
        assert item["action"] == "buy"
        assert item["amount"] == 10000000
        print(f"✅ 승인 요청 생성 및 조회 성공: {approval_request.request_id}")

    def test_approval_with_decision(self):
        """승인 요청 및 사용자 결정 테스트"""
        # Given: 승인 요청 생성
        approval_request = ApprovalRequest(
            request_id=uuid4(),
            user_id=DEMO_USER_UUID,
            request_type="trade",
            request_title="SK하이닉스 매도 승인 요청",
            proposed_actions={
                "action": "sell",
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "quantity": 50,
                "price": 150000,
                "total_amount": 7500000
            },
            status="approved",
            created_at=datetime.utcnow()
        )
        self.db.add(approval_request)
        self.db.flush()

        # 사용자 결정 생성
        user_decision = UserDecision(
            decision_id=uuid4(),
            request_id=approval_request.request_id,
            user_id=DEMO_USER_UUID,
            decision="approved",
            selected_option="original",
            user_notes="분석 결과가 합리적임",
            decided_at=datetime.utcnow()
        )
        self.db.add(user_decision)
        self.db.commit()

        # When
        items, total = approval_service.list_approval_history(
            db=self.db,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert total == 1
        item = items[0]
        assert item["status"] == "approved"
        assert item["decision"] == "approved"
        assert item["decided_at"] is not None
        print(f"✅ 승인 요청 및 결정 조회 성공")

    def test_filter_by_status(self):
        """상태별 필터링 테스트"""
        # Given: 여러 상태의 승인 요청 생성
        # 1. 대기 중
        pending_request = ApprovalRequest(
            request_id=uuid4(),
            user_id=DEMO_USER_UUID,
            request_type="trade",
            request_title="대기 중 요청",
            proposed_actions={"action": "buy"},
            status="pending",
            created_at=datetime.utcnow()
        )
        self.db.add(pending_request)
        self.db.flush()

        # 2. 승인됨
        approved_request = ApprovalRequest(
            request_id=uuid4(),
            user_id=DEMO_USER_UUID,
            request_type="trade",
            request_title="승인된 요청",
            proposed_actions={"action": "sell"},
            status="approved",
            created_at=datetime.utcnow()
        )
        self.db.add(approved_request)
        self.db.flush()

        approved_decision = UserDecision(
            decision_id=uuid4(),
            request_id=approved_request.request_id,
            user_id=DEMO_USER_UUID,
            decision="approved",
            decided_at=datetime.utcnow()
        )
        self.db.add(approved_decision)
        self.db.commit()

        # When: 대기 중만 조회
        pending_items, pending_total = approval_service.list_approval_history(
            db=self.db,
            user_id=DEMO_USER_UUID,
            status="pending"
        )

        # Then
        assert pending_total == 1
        assert pending_items[0]["request_title"] == "대기 중 요청"
        print(f"✅ 대기 중 필터링 성공: {pending_total}개")

        # When: 승인됨만 조회
        approved_items, approved_total = approval_service.list_approval_history(
            db=self.db,
            user_id=DEMO_USER_UUID,
            status="approved"
        )

        # Then
        assert approved_total == 1
        assert approved_items[0]["request_title"] == "승인된 요청"
        print(f"✅ 승인됨 필터링 성공: {approved_total}개")

    def test_get_approval_detail(self):
        """승인 상세 정보 조회 테스트"""
        # Given
        approval_request = ApprovalRequest(
            request_id=uuid4(),
            user_id=DEMO_USER_UUID,
            request_type="rebalance",
            request_title="포트폴리오 리밸런싱 승인 요청",
            request_description="분기별 리밸런싱입니다.",
            proposed_actions={
                "changes": [
                    {"stock_code": "005930", "action": "sell", "quantity": 10},
                    {"stock_code": "000660", "action": "buy", "quantity": 20}
                ]
            },
            impact_analysis={"sharpe_ratio_change": 0.05},
            risk_warnings=["일시적 변동성 증가 가능"],
            alternatives={"option1": "수량 50% 감축"},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=2)
        )
        self.db.add(approval_request)
        self.db.commit()

        # When
        detail = approval_service.get_approval_detail(
            db=self.db,
            request_id=approval_request.request_id,
            user_id=DEMO_USER_UUID
        )

        # Then
        assert detail is not None
        assert detail["request_type"] == "rebalance"
        assert detail["request_title"] == "포트폴리오 리밸런싱 승인 요청"
        assert detail["request_description"] == "분기별 리밸런싱입니다."
        assert len(detail["risk_warnings"]) == 1
        assert detail["alternatives"] is not None
        assert detail["decision"] is None  # 아직 결정되지 않음
        print(f"✅ 승인 상세 정보 조회 성공")
        print(f"   요청 타입: {detail['request_type']}")
        print(f"   리스크 경고: {detail['risk_warnings']}")


if __name__ == "__main__":
    """직접 실행"""
    tester = TestApprovalHistoryAPI()

    print("\n=== Approval History API 테스트 시작 ===\n")

    tester.setup_method()
    try:
        tester.test_list_approval_history_empty()
        print()

        tester.test_create_and_list_approval_history()
        print()

        tester.setup_method()  # 데이터 정리
        tester.test_approval_with_decision()
        print()

        tester.setup_method()  # 데이터 정리
        tester.test_filter_by_status()
        print()

        tester.setup_method()  # 데이터 정리
        tester.test_get_approval_detail()
        print()

        print("=== 모든 테스트 통과 ✅ ===")
    finally:
        tester.teardown_method()

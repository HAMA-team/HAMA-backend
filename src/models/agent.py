"""
Agent-related database models
"""
from sqlalchemy import Column, String, Integer, TIMESTAMP, DECIMAL, Text, JSON, Boolean, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.models.database import Base


class ResearchReport(Base):
    """AI 분석 리포트"""
    __tablename__ = "research_reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(20), nullable=False, index=True)

    # 리포트 유형
    report_type = Column(String(50), nullable=False, index=True)

    # 분석 결과
    rating = Column(Integer, index=True)
    target_price = Column(DECIMAL(15, 2))
    recommendation = Column(String(20))

    # 상세 분석
    summary = Column(Text)
    bull_case = Column(Text)
    bear_case = Column(Text)
    key_insights = Column(JSON)

    # 지표
    metrics = Column(JSON)

    # AI 메타데이터
    agent_id = Column(String(50))
    model_version = Column(String(50))
    confidence_score = Column(DECIMAL(3, 2))

    generated_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    valid_until = Column(TIMESTAMP)


class TradingSignal(Base):
    """매매 시그널"""
    __tablename__ = "trading_signals"

    signal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(20), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), index=True)

    # 시그널 정보
    action = Column(String(10), nullable=False, index=True)  # BUY, SELL, HOLD
    confidence = Column(DECIMAL(3, 2), nullable=False, index=True)

    # 가격 정보
    current_price = Column(DECIMAL(15, 2))
    target_price = Column(DECIMAL(15, 2))
    stop_loss = Column(DECIMAL(15, 2))

    # 근거
    reasoning = Column(Text, nullable=False)
    bull_case = Column(Text)
    bear_case = Column(Text)

    # Bull/Bear 분석
    bull_confidence = Column(DECIMAL(3, 2))
    bear_confidence = Column(DECIMAL(3, 2))
    consensus = Column(String(50))

    # AI 메타데이터
    agent_id = Column(String(50))
    model_version = Column(String(50))

    # 상태
    status = Column(String(20), default="active", index=True)

    generated_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    expires_at = Column(TIMESTAMP)


class RiskAssessment(Base):
    """리스크 평가"""
    __tablename__ = "risk_assessments"

    assessment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), index=True)
    user_id = Column(UUID(as_uuid=True), index=True)

    # 평가 대상
    assessment_type = Column(String(50))
    related_entity_id = Column(UUID(as_uuid=True))

    # 리스크 지표
    risk_level = Column(String(20), nullable=False, index=True)
    risk_score = Column(DECIMAL(5, 2))

    # 구체적 리스크
    concentration_risk = Column(DECIMAL(3, 2))
    sector_risk = Column(JSON)
    volatility_risk = Column(DECIMAL(10, 6))

    # 시뮬레이션
    var_95 = Column(DECIMAL(10, 6))
    expected_loss = Column(DECIMAL(15, 2))
    max_drawdown_scenario = Column(DECIMAL(10, 6))

    # 경고 및 권고
    warnings = Column(ARRAY(String))
    recommendations = Column(ARRAY(String))

    # AI 메타데이터
    agent_id = Column(String(50))

    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)


class ApprovalRequest(Base):
    """승인 요청 (HITL)"""
    __tablename__ = "approval_requests"

    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 요청 정보
    request_type = Column(String(50), nullable=False, index=True)
    request_title = Column(String(200), nullable=False)
    request_description = Column(Text)

    # 관련 엔티티
    related_signal_id = Column(UUID(as_uuid=True))
    related_portfolio_id = Column(UUID(as_uuid=True))

    # 제안 내용
    proposed_actions = Column(JSON, nullable=False)

    # 영향 분석
    impact_analysis = Column(JSON)

    # 리스크 경고
    risk_warnings = Column(ARRAY(String))

    # 대안 제시
    alternatives = Column(JSON)

    # 상태
    status = Column(String(20), default="pending", index=True)

    # AI 메타데이터
    triggering_agent = Column(String(50))
    urgency = Column(String(20), index=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    responded_at = Column(TIMESTAMP)
    expires_at = Column(TIMESTAMP)


class UserDecision(Base):
    """사용자 결정 이력"""
    __tablename__ = "user_decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 결정 내용
    decision = Column(String(20), nullable=False, index=True)
    selected_option = Column(String(50))

    # 수정 사항
    modifications = Column(JSON)

    # 사용자 피드백
    user_notes = Column(Text)
    confidence_level = Column(Integer)

    # 결정 컨텍스트
    decision_reason = Column(String(500))

    decided_at = Column(TIMESTAMP, server_default=func.now(), index=True)


class AgentLog(Base):
    """에이전트 실행 로그"""
    __tablename__ = "agent_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 에이전트 정보
    agent_id = Column(String(50), nullable=False, index=True)
    agent_action = Column(String(100), nullable=False)

    # 요청 정보
    request_id = Column(UUID(as_uuid=True), index=True)
    user_id = Column(UUID(as_uuid=True), index=True)

    # 입출력
    input_data = Column(JSON)
    output_data = Column(JSON)

    # 실행 정보
    status = Column(String(20))
    error_message = Column(Text)
    execution_time_ms = Column(Integer)

    timestamp = Column(TIMESTAMP, server_default=func.now(), index=True)


class Alert(Base):
    """알림"""
    __tablename__ = "alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 알림 정보
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, index=True)

    # 내용
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    action_required = Column(Boolean, default=False)

    # 관련 엔티티
    related_stock = Column(String(20))
    related_portfolio_id = Column(UUID(as_uuid=True))
    related_request_id = Column(UUID(as_uuid=True))

    # 상태
    status = Column(String(20), default="unread", index=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    read_at = Column(TIMESTAMP)
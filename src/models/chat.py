"""
Chat history database models.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.database import Base


class ChatSession(Base):
    """Chat session metadata."""

    __tablename__ = "chat_sessions"

    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # automation_level 제거됨: hitl_config 사용 (session_metadata 또는 user_settings에서 조회)
    session_metadata = Column(JSON)
    summary = Column(Text)
    last_agent = Column(String(50))
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), index=True)
    last_message_at = Column(TIMESTAMP, server_default=func.now(), index=True)


class ChatMessage(Base):
    """Individual chat messages exchanged within a session."""

    __tablename__ = "chat_messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False, index=True)  # user, assistant, system
    content = Column(Text, nullable=False)
    agent_id = Column(String(50))
    message_metadata = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)

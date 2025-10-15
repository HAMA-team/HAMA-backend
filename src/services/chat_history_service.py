"""
Chat history persistence service.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, Optional, Sequence

from sqlalchemy.orm import Session

from src.models.chat import ChatMessage, ChatSession
from src.models.database import SessionLocal


class ChatHistoryService:
    """Service wrapper around chat session/message persistence."""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    async def upsert_session(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        automation_level: int,
        metadata: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        last_agent: Optional[str] = None,
    ) -> ChatSession:
        """Create or update a chat session row."""

        def _upsert() -> ChatSession:
            with self._session_factory() as session:  # type: Session
                chat_session = (
                    session.query(ChatSession)
                    .filter(ChatSession.conversation_id == conversation_id)
                    .with_for_update(read=True)
                    .first()
                )

                if chat_session is None:
                    chat_session = ChatSession(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        automation_level=automation_level,
                        session_metadata=metadata,
                        summary=summary,
                        last_agent=last_agent,
                    )
                    session.add(chat_session)
                else:
                    chat_session.automation_level = automation_level
                    chat_session.session_metadata = metadata or chat_session.session_metadata
                    chat_session.summary = summary or chat_session.summary
                    chat_session.last_agent = last_agent or chat_session.last_agent

                session.commit()
                session.refresh(chat_session)
                return chat_session

        return await asyncio.to_thread(_upsert)

    async def append_message(
        self,
        *,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
    ) -> ChatMessage:
        """Persist a new chat message."""

        def _append() -> ChatMessage:
            with self._session_factory() as session:  # type: Session
                message = ChatMessage(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    message_metadata=metadata,
                    agent_id=agent_id,
                )
                session.add(message)
                session.flush()

                # Update last message timestamp on session if it exists.
                chat_session = (
                    session.query(ChatSession)
                    .filter(ChatSession.conversation_id == conversation_id)
                    .first()
                )
                if chat_session:
                    chat_session.last_message_at = message.created_at

                session.commit()
                session.refresh(message)
                return message

        return await asyncio.to_thread(_append)

    async def get_history(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Fetch chat session metadata and messages."""

        def _load() -> Dict[str, Any]:
            with self._session_factory() as session:  # type: Session
                chat_session = (
                    session.query(ChatSession)
                    .filter(ChatSession.conversation_id == conversation_id)
                    .first()
                )
                if chat_session is None:
                    return {}

                messages: Sequence[ChatMessage] = (
                    session.query(ChatMessage)
                    .filter(ChatMessage.conversation_id == conversation_id)
                    .order_by(ChatMessage.created_at.asc())
                    .limit(limit)
                    .all()
                )

                return {
                    "session": chat_session,
                    "messages": list(messages),
                }

        return await asyncio.to_thread(_load)

    async def delete_history(self, *, conversation_id: uuid.UUID) -> None:
        """Remove a conversation and its messages."""

        def _delete() -> None:
            with self._session_factory() as session:  # type: Session
                session.query(ChatMessage).filter(
                    ChatMessage.conversation_id == conversation_id
                ).delete(synchronize_session=False)
                session.query(ChatSession).filter(
                    ChatSession.conversation_id == conversation_id
                ).delete(synchronize_session=False)
                session.commit()

        await asyncio.to_thread(_delete)

    async def list_sessions(self, *, limit: int = 50) -> Sequence[Dict[str, Any]]:
        """Return chat session summaries ordered by last activity."""

        def _list() -> Sequence[Dict[str, Any]]:
            with self._session_factory() as session:  # type: Session
                sessions: Sequence[ChatSession] = (
                    session.query(ChatSession)
                    .order_by(ChatSession.last_message_at.desc().nullslast())
                    .limit(limit)
                    .all()
                )

                if not sessions:
                    return []

                conversation_ids = [s.conversation_id for s in sessions]

                messages: Sequence[ChatMessage] = (
                    session.query(ChatMessage)
                    .filter(ChatMessage.conversation_id.in_(conversation_ids))
                    .order_by(ChatMessage.conversation_id.asc(), ChatMessage.created_at.asc())
                    .all()
                )

                grouped_messages: Dict[uuid.UUID, Sequence[ChatMessage]] = {}
                current_conversation = None
                buffer: list[ChatMessage] = []

                for message in messages:
                    if message.conversation_id != current_conversation:
                        if current_conversation is not None:
                            grouped_messages[current_conversation] = list(buffer)
                        current_conversation = message.conversation_id
                        buffer = [message]
                    else:
                        buffer.append(message)

                if current_conversation is not None:
                    grouped_messages[current_conversation] = list(buffer)

                summaries: list[Dict[str, Any]] = []
                for chat_session in sessions:
                    convo_id = chat_session.conversation_id
                    session_messages = grouped_messages.get(convo_id, [])

                    first_user_message = next(
                        (msg for msg in session_messages if msg.role == "user" and msg.content),
                        None,
                    )
                    last_message = session_messages[-1] if session_messages else None
                    message_count = len(session_messages)

                    summaries.append(
                        {
                            "conversation_id": convo_id,
                            "session": chat_session,
                            "first_user_message": first_user_message,
                            "last_message": last_message,
                            "message_count": message_count,
                        }
                    )

                return summaries

        return await asyncio.to_thread(_list)


chat_history_service = ChatHistoryService()

"""
Reasoning trace schemas shared between SSE streamers and history APIs.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReasoningPhase(str, Enum):
    """High-level phases surfaced to the frontend."""

    SUPERVISION = "supervision"
    PLANNING = "planning"
    ROUTING = "routing"
    AGENT_EXECUTION = "agent_execution"
    DATA_COLLECTION = "data_collection"
    TOOL = "tool"
    LLM = "llm"
    HITL = "hitl"
    FINALIZATION = "finalization"
    SYSTEM = "system"


class ReasoningActor(str, Enum):
    """Actor that produced the event."""

    SUPERVISOR = "supervisor"
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    SYSTEM = "system"


class ReasoningStatus(str, Enum):
    """Progress status of the reasoning step."""

    START = "start"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    INFO = "info"
    ERROR = "error"


class ReasoningEvent(BaseModel):
    """
    Normalized reasoning event delivered through SSE or persisted in history.
    """

    event_id: str
    sequence_index: int
    conversation_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_label: str = Field(description="Original SSE event name (e.g. agent_start)")
    phase: ReasoningPhase
    status: ReasoningStatus
    actor: ReasoningActor
    agent: Optional[str] = None
    node: Optional[str] = None
    step: Optional[int] = None
    depth: int = 0
    lineage: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReasoningStreamPayload(BaseModel):
    """
    Wrapper that co-locates an SSE payload with its reasoning meta.
    """

    event: str
    payload: Dict[str, Any]
    reasoning_event: ReasoningEvent

"""
Agent-related Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class AgentInput(BaseModel):
    """Base agent input schema"""
    request_id: str
    user_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3)
    context: Optional[Dict[str, Any]] = None


class AgentOutput(BaseModel):
    """Base agent output schema"""
    status: str  # success, failure, pending
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ResearchRequest(AgentInput):
    """Research agent request"""
    stock_code: str
    analysis_type: Optional[str] = "comprehensive"  # fundamental, technical, comprehensive


class ResearchResponse(AgentOutput):
    """Research agent response"""
    stock_code: str
    rating: Optional[int] = None
    recommendation: Optional[str] = None
    summary: Optional[str] = None
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None


class StrategyRequest(AgentInput):
    """Strategy agent request"""
    query_type: str  # analyze, recommend, screen
    stock_codes: Optional[List[str]] = None
    criteria: Optional[Dict[str, Any]] = None


class StrategyResponse(AgentOutput):
    """Strategy agent response"""
    action: Optional[str] = None  # BUY, SELL, HOLD
    confidence: Optional[Decimal] = None
    reasoning: Optional[str] = None
    bull_confidence: Optional[Decimal] = None
    bear_confidence: Optional[Decimal] = None


class RiskRequest(AgentInput):
    """Risk agent request"""
    assessment_type: str  # portfolio, position, trade
    portfolio_id: Optional[str] = None
    proposed_action: Optional[Dict[str, Any]] = None


class RiskResponse(AgentOutput):
    """Risk agent response"""
    risk_level: str  # low, medium, high, critical
    risk_score: Optional[Decimal] = None
    warnings: List[str] = []
    recommendations: List[str] = []
    should_trigger_hitl: bool = False


class HITLRequest(BaseModel):
    """HITL approval request"""
    request_type: str
    title: str
    description: str
    proposed_actions: List[Dict[str, Any]]
    impact_analysis: Optional[Dict[str, Any]] = None
    risk_warnings: List[str] = []
    alternatives: Optional[List[Dict[str, Any]]] = None
    urgency: str = "medium"


class HITLResponse(BaseModel):
    """HITL approval response"""
    request_id: str
    decision: str  # approved, rejected, modified
    selected_option: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    user_notes: Optional[str] = None
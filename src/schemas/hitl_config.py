"""
HITL (Human-in-the-Loop) 설정 스키마.

단계별 개입 지점을 명시적으로 표현한다.
"""
from __future__ import annotations

from typing import Union, List, Literal

from pydantic import BaseModel, Field


HITLTradeMode = Union[bool, Literal["conditional"]]


class HITLPhases(BaseModel):
    """각 워크플로 단계별 HITL 개입 여부 정의"""

    data_collection: bool = Field(
        default=False,
        description="데이터 수집 단계에서 인간 확인이 필요한지 여부",
    )
    analysis: bool = Field(
        default=False,
        description="투자 전략/분석 단계에서 인간 확인이 필요한지 여부",
    )
    portfolio: bool = Field(
        default=False,
        description="포트폴리오 구성 및 리밸런싱 단계에서 HITL 여부",
    )
    risk: bool = Field(
        default=False,
        description="리스크 평가 단계에서 인간 확인이 필요한지 여부",
    )
    trade: HITLTradeMode = Field(
        default=True,
        description='매매 승인 단계. True(항상 승인 필요) / False(불필요) / "conditional"(조건부 자동)',
    )


class HITLConfig(BaseModel):
    """사용자의 HITL 설정 전체 구성"""

    phases: HITLPhases = Field(
        default_factory=HITLPhases,
        description="단계별 HITL 개입 여부 상세 설정",
    )


def get_interrupt_points(config: HITLConfig) -> List[str]:
    """
    UI에서 표기할 interrupt 지점 리스트를 계산한다.
    trade 단계는 조건부/항상 여부를 구분하여 표기한다.
    """

    points: List[str] = []
    if config.phases.data_collection:
        points.append("data_collection")
    if config.phases.analysis:
        points.append("analysis")
    if config.phases.portfolio:
        points.append("portfolio")
    if config.phases.risk:
        points.append("risk")

    trade_phase = config.phases.trade
    if trade_phase is True:
        points.append("trade")
    elif trade_phase == "conditional":
        points.append("trade (conditional)")

    return points


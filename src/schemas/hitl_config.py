"""
HITL (Human-in-the-Loop) 설정 스키마 및 프리셋 정의.

automation_level 정수 기반의 기존 구조를 대체하며,
단계별 개입 지점을 명시적으로 표현한다.
"""
from __future__ import annotations

from typing import Literal, Union, List, Dict, Any

from pydantic import BaseModel, Field


HITLPresetName = Literal["pilot", "copilot", "advisor", "custom"]
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

    preset: HITLPresetName = Field(default="copilot", description="선택된 자동화 프리셋")
    phases: HITLPhases = Field(
        default_factory=HITLPhases,
        description="단계별 HITL 개입 여부 상세 설정",
    )


# ---------------------------------------------------------------------------
# 프리셋 정의
# ---------------------------------------------------------------------------

PRESET_PILOT = HITLConfig(
    preset="pilot",
    phases=HITLPhases(
        data_collection=False,
        analysis=False,
        portfolio=False,
        risk=False,
        trade="conditional",
    ),
)

PRESET_COPILOT = HITLConfig(
    preset="copilot",
    phases=HITLPhases(
        data_collection=False,
        analysis=False,
        portfolio=True,
        risk=False,
        trade=True,
    ),
)

PRESET_ADVISOR = HITLConfig(
    preset="advisor",
    phases=HITLPhases(
        data_collection=False,
        analysis=True,
        portfolio=True,
        risk=False,
        trade=True,
    ),
)

# Custom 프리셋은 사용자가 직접 phases를 조정한다.


PRESET_METADATA: Dict[str, Dict[str, Any]] = {
    "pilot": {
        "name": "Pilot",
        "description": "AI가 대부분 자동으로 처리하며 저위험 거래는 자동 승인됩니다.",
        "features": [
            "저위험 매매는 자동 실행",
            "고위험 매매만 승인 필요",
            "가장 빠른 의사결정",
        ],
        "recommended_for": "경험 많은 투자자",
    },
    "copilot": {
        "name": "Copilot",
        "description": "AI가 제안하고, 중요한 결정은 사용자가 승인합니다.",
        "features": [
            "포트폴리오 구성 시 승인 필요",
            "모든 매매 시 승인 필요",
            "자동화와 통제의 균형",
        ],
        "recommended_for": "대부분의 투자자 (권장)",
    },
    "advisor": {
        "name": "Advisor",
        "description": "AI는 정보만 제공하고, 모든 중요 결정은 사용자가 직접 합니다.",
        "features": [
            "전략 수립 시 승인 필요",
            "포트폴리오 구성 시 승인 필요",
            "모든 매매 시 승인 필요",
        ],
        "recommended_for": "신중함을 선호하는 투자자",
    },
}


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


def level_to_config(level: int) -> HITLConfig:
    """
    기존 automation_level 정수 값을 새 HITLConfig 프리셋으로 변환한다.
    하위 호환성을 위해 존재하며, 미지정 값은 Copilot으로 폴백한다.
    """
    if level == 1:
        return PRESET_PILOT.model_copy()
    if level == 2:
        return PRESET_COPILOT.model_copy()
    if level == 3:
        return PRESET_ADVISOR.model_copy()
    return PRESET_COPILOT.model_copy()


def config_to_level(config: HITLConfig) -> int:
    """
    HITLConfig를 legacy automation_level 정수로 변환한다.
    Custom 프리셋은 Copilot(2)로 폴백한다.
    """
    preset = config.preset
    if preset == "pilot":
        return 1
    if preset == "advisor":
        return 3
    # copilot, custom → 2
    return 2


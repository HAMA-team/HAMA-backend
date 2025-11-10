"""
HITL 호환성 레이어

레거시 automation_level을 hitl_config로 변환하는 유틸리티
Phase 3 완료 후 이 파일은 제거될 예정
"""
import logging
from typing import Dict, Any

from src.schemas.hitl_config import HITLConfig, level_to_config, config_to_level

logger = logging.getLogger(__name__)


def automation_level_to_hitl_config(level: int) -> HITLConfig:
    """
    레거시 automation_level을 HITLConfig로 변환

    Args:
        level: automation_level (1-3)
            - 1: Pilot (AI가 거의 모든 것을 처리)
            - 2: Copilot (AI가 제안, 큰 결정만 승인) [기본값]
            - 3: Advisor (AI는 정보만 제공, 사용자가 결정)

    Returns:
        HITLConfig 객체
    """
    config = level_to_config(level)
    logger.info(f"🔄 [HITLCompat] automation_level {level} → HITLConfig (preset={config.preset})")
    return config


def hitl_config_to_automation_level(config: HITLConfig) -> int:
    """
    HITLConfig를 레거시 automation_level로 역변환 (deprecated)

    Args:
        config: HITLConfig 객체

    Returns:
        automation_level (1-3)
    """
    level = config_to_level(config)
    logger.info(f"🔄 [HITLCompat] HITLConfig (preset={config.preset}) → automation_level {level}")
    return level


def get_hitl_config_from_state(state: Dict[str, Any]) -> HITLConfig:
    """
    State에서 HITLConfig 추출 (automation_level fallback 지원)

    Args:
        state: 에이전트 State 딕셔너리

    Returns:
        HITLConfig 객체
    """
    # 우선순위 1: hitl_config가 있으면 사용
    if "hitl_config" in state and state["hitl_config"]:
        hitl_config = state["hitl_config"]

        # Dict이면 HITLConfig로 변환
        if isinstance(hitl_config, dict):
            return HITLConfig(**hitl_config)
        elif isinstance(hitl_config, HITLConfig):
            return hitl_config

    # 우선순위 2: automation_level이 있으면 변환
    if "automation_level" in state:
        logger.warning("⚠️ [HITLCompat] automation_level 사용 중 (deprecated). hitl_config로 전환하세요.")
        return automation_level_to_hitl_config(state["automation_level"])

    # 기본값: Copilot (2)
    logger.warning("⚠️ [HITLCompat] hitl_config와 automation_level 모두 없음. 기본값(Copilot) 사용")
    return automation_level_to_hitl_config(2)

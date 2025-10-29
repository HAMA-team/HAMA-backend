"""
LangGraph 1.0/0.x 호환 어댑터.

LangGraph 1.0에서 체크포인터 및 Command/interrupt 경로가 변경되면서
기존 코드와의 호환을 유지하기 위한 얇은 추상화 계층을 제공한다.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Protocol


class SupportsInterrupt(Protocol):
    """Interrupt 생성 가능 객체 프로토콜."""

    def __call__(self, payload: Any) -> Any: ...


# 체크포인터 모듈 위치(0.x → 1.0) 호환
try:  # LangGraph 1.0
    from langgraph.checkpoints.memory import MemorySaver  # type: ignore
except ModuleNotFoundError:  # LangGraph 0.x
    from langgraph.checkpoint.memory import MemorySaver  # type: ignore

try:  # LangGraph 1.0
    from langgraph.checkpoints.redis import RedisSaver  # type: ignore
except ModuleNotFoundError:  # LangGraph 0.x
    try:
        from langgraph.checkpoint.redis import RedisSaver  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - 선택적 의존성
        RedisSaver = None  # type: ignore

# Command / interrupt import 호환
try:  # LangGraph SDK (1.0)
    from langgraph_sdk.schema import Command  # type: ignore
except ModuleNotFoundError:  # LangGraph 0.x
    from langgraph.types import Command  # type: ignore

_interrupt_factory: Optional[Callable[[Any], Any]] = None

if _interrupt_factory is None:
    try:
        from langgraph_sdk.schema import interrupt as _sdk_interrupt  # type: ignore

        _interrupt_factory = _sdk_interrupt  # type: ignore[assignment]
    except ModuleNotFoundError:
        pass

if _interrupt_factory is None:
    try:
        from langgraph.types import interrupt as _legacy_interrupt  # type: ignore

        _interrupt_factory = _legacy_interrupt  # type: ignore[assignment]
    except ModuleNotFoundError:  # pragma: no cover - 이론상 발생하지 않음
        _interrupt_factory = None


def make_interrupt(payload: Any) -> Any:
    """
    LangGraph 버전에 따라 올바른 interrupt 객체를 생성한다.

    Args:
        payload: interrupt에 전달할 페이로드

    Returns:
        LangGraph가 이해할 수 있는 interrupt 객체
    """
    if _interrupt_factory is None:
        raise RuntimeError("interrupt factory를 찾을 수 없습니다. LangGraph 설치를 확인하세요.")
    return _interrupt_factory(payload)


__all__ = [
    "Command",
    "MemorySaver",
    "RedisSaver",
    "make_interrupt",
]

"""텍스트/콘텐츠 정규화 유틸리티."""
from __future__ import annotations

from typing import Any


def ensure_plain_text(value: Any) -> str:
    """
    다양한 타입(str, dict, list 등)으로 전달된 콘텐츠를 안전한 문자열로 변환한다.

    LangChain/OpenAI 멀티모달 메시지는 list[dict(type=..., text=...)] 형태로 들어오는데,
    Router/노드들이 문자열을 기대하기 때문에 단일 문자열로 정규화한다.
    """

    def _coerce(item: Any) -> str:
        if item is None:
            return ""

        if isinstance(item, str):
            return item

        if isinstance(item, list):
            return "".join(filter(None, (_coerce(part) for part in item)))

        if isinstance(item, dict):
            # 우선순위: text -> content -> message -> parts
            for key in ("text", "content", "message"):
                if key in item:
                    return _coerce(item[key])
            if "parts" in item:
                return _coerce(item["parts"])
            return ""

        content = getattr(item, "content", None)
        if content is not None:
            return _coerce(content)

        return str(item)

    return _coerce(value)

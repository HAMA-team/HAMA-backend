"""Deprecated legacy agent base.

Import `LegacyAgent` from `src.agents.legacy` instead. This shim exists to
provide a soft migration path while agents transition to Langgraph subgraphs.
"""
from __future__ import annotations

import warnings

from src.agents.legacy import LegacyAgent

warnings.warn(
    "src.agents.base is deprecated; import LegacyAgent from src.agents.legacy",
    DeprecationWarning,
    stacklevel=2,
)

BaseAgent = LegacyAgent

__all__ = ["BaseAgent", "LegacyAgent"]

"""DeepSeek provider (OpenAI-compatible chat completions).

Thin wrapper over :class:`OpenAICompatibleProvider`: DeepSeek and AgentRouter
share the exact same request/parse/cost logic, so it lives in one place and this
class only binds the DeepSeek config. Behaviour is unchanged from before the
shared base was extracted.

``SYSTEM_RULES`` and the small parsing helpers are re-exported here for backward
compatibility (the answer engine and tests import them from this module).
"""
from __future__ import annotations

from typing import Optional

from .openai_compatible import (  # noqa: F401  (re-exported)
    SYSTEM_RULES,
    OpenAICompatibleProvider,
    _clamp_conf,
    _coerce_index,
    _strip_code_fence,
)
from ..utils.config import CONFIG


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"

    def __init__(self, api_key: Optional[str]):
        super().__init__(api_key, CONFIG.provider, name="deepseek")

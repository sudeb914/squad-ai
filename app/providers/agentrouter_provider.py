"""AgentRouter provider (OpenAI-compatible chat completions).

AgentRouter exposes an OpenAI-compatible API, so it reuses the shared
:class:`OpenAICompatibleProvider` implementation unchanged and only binds the
AgentRouter config (base URL, model, temperature, pricing, token caps — all
editable from Settings). Default endpoint: ``https://co.agentrouter.org/v1``;
default model: ``deepseek-v4-flash`` (both configurable, not hard-coded here).
"""
from __future__ import annotations

from typing import Optional

from .openai_compatible import OpenAICompatibleProvider
from ..utils.config import CONFIG


class AgentRouterProvider(OpenAICompatibleProvider):
    name = "agentrouter"

    def __init__(self, api_key: Optional[str]):
        super().__init__(api_key, CONFIG.agentrouter, name="agentrouter")

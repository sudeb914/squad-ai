"""Application service container (simple dependency injection).

Wires the database, repositories, retrieval, memory, security and the answer
engine together. The UI and CLI both build a single :class:`Services` and pull
what they need from it — nothing constructs the answer engine or provider ad hoc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .core.answer_engine import AnswerEngine
from .database.db import Database
from .database.repositories.capture_repo import CaptureRepo
from .database.repositories.chat_repo import ChatRepo
from .database.repositories.memory_repo import MemoryRepo
from .database.repositories.profile_repo import ProfileRepo
from .database.repositories.reference_repo import ReferenceRepo
from .database.repositories.settings_repo import SettingsRepo
from .database.repositories.usage_repo import UsageRepo
from .memory.answer_memory import AnswerMemory
from .memory.import_export import MemoryPorter
from .providers.agentrouter_provider import AgentRouterProvider
from .providers.base_provider import BaseAIProvider
from .providers.deepseek_provider import DeepSeekProvider
from .retrieval.semantic_matcher import SemanticMatcher
from .security.credential_manager import CredentialManager
from .utils.config import CONFIG
from .utils.logging import get_logger, setup_logging

log = get_logger("services")


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Services:
    def __init__(self, db_path: Optional[Path] = None):
        setup_logging(CONFIG.log_level)
        self.db = Database(db_path)

        # repositories
        self.settings = SettingsRepo(self.db)
        self.profile = ProfileRepo(self.db)
        self.reference = ReferenceRepo(self.db)
        self.memory_repo = MemoryRepo(self.db)
        self.usage = UsageRepo(self.db)
        self.chat = ChatRepo(self.db)
        self.capture = CaptureRepo(self.db)

        # security
        self.credentials = CredentialManager()

        # retrieval + memory
        self.semantic = SemanticMatcher(self.memory_repo, self.reference)
        self.answer_memory = AnswerMemory(self.memory_repo, self.semantic)
        self.porter = MemoryPorter(self.memory_repo)

        self._apply_persisted_settings()

        # the one and only answer engine
        self.engine = AnswerEngine(
            profile_provider=self.profile.as_dict,
            memory_repo=self.memory_repo,
            usage_repo=self.usage,
            semantic=self.semantic,
            answer_memory=self.answer_memory,
            provider_factory=self.build_provider,
            instruction_provider=lambda: self.settings.get("custom_prompt", ""),
            profile_info_provider=lambda: self.settings.get(
                "profile_info_raw", ""),
        )

    # -- provider ---------------------------------------------------------
    def build_provider(self) -> Optional[BaseAIProvider]:
        """The provider for the CURRENTLY-SELECTED cloud AI (or None if its key
        is missing). The answer engine calls this — switching ``active_provider``
        is all it takes to change which cloud backend is used."""
        return self.build_named_provider(CONFIG.active_provider)

    def build_named_provider(self, name: str) -> Optional[BaseAIProvider]:
        """Build a specific provider by name regardless of which is active.

        Used by Settings' Test Connection so the user can test a provider before
        making it active. Returns None when that provider has no stored key.
        """
        if name == "agentrouter":
            key = self.credentials.get_key("agentrouter")
            return AgentRouterProvider(key) if key else None
        key = self.credentials.get_key(CONFIG.provider.name)
        return DeepSeekProvider(key) if key else None

    def has_api_key(self) -> bool:
        """Whether the ACTIVE provider has a key configured."""
        name = CONFIG.active_provider
        provider_key = "agentrouter" if name == "agentrouter" \
            else CONFIG.provider.name
        return self.credentials.has_key(provider_key)

    # -- settings ---------------------------------------------------------
    def _apply_persisted_settings(self) -> None:
        """Load user-overridable settings from the DB into CONFIG."""
        mode = self.settings.get("capture_mode")
        if mode in ("manual", "auto"):
            CONFIG.capture.mode = mode
        hotkey = self.settings.get("hotkey")
        if hotkey:
            CONFIG.capture.hotkey = hotkey
        es = self.settings.get("enable_semantic")
        if isinstance(es, bool):
            CONFIG.enable_semantic = es
        em = self.settings.get("enable_memory")
        if isinstance(em, bool):
            CONFIG.enable_memory = em
        model = self.settings.get("model")
        # deepseek-flash/v4-pro are reasoning models that return empty content
        # under a small token budget — force the working deepseek-chat unless the
        # user explicitly picked deepseek-reasoner.
        if model not in ("deepseek-chat", "deepseek-reasoner"):
            model = CONFIG.provider.model  # default: deepseek-chat
            self.settings.set("model", model)
        CONFIG.provider.model = model

        # --- active provider selector (deepseek | agentrouter) ---
        active = self.settings.get("active_provider")
        if active in ("deepseek", "agentrouter"):
            CONFIG.active_provider = active

        # --- AgentRouter config (all user-editable; never the API key here) ---
        ar = CONFIG.agentrouter
        saved_base = self.settings.get("agentrouter_base_url", ar.base_url) \
            or ar.base_url
        # Migrate the earlier wrong 'co.' subdomain to the documented endpoint so
        # existing installs start working without the user editing anything.
        if "co.agentrouter.org" in saved_base:
            saved_base = ar.base_url  # the corrected default
            self.settings.set("agentrouter_base_url", saved_base)
        ar.base_url = saved_base
        ar.model = self.settings.get("agentrouter_model", ar.model) or ar.model
        ar.user_agent = self.settings.get(
            "agentrouter_user_agent", ar.user_agent) or ar.user_agent
        ar.temperature = _as_float(
            self.settings.get("agentrouter_temperature"), ar.temperature)
        ar.max_output_tokens = _as_int(
            self.settings.get("agentrouter_max_tokens"), ar.max_output_tokens)
        ar.price_input_per_m = _as_float(
            self.settings.get("agentrouter_price_input"), ar.price_input_per_m)
        ar.price_input_cached_per_m = _as_float(
            self.settings.get("agentrouter_price_cached"),
            ar.price_input_cached_per_m)
        ar.price_output_per_m = _as_float(
            self.settings.get("agentrouter_price_output"), ar.price_output_per_m)

    def close(self) -> None:
        self.db.close()

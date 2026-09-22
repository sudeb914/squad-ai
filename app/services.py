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
from .providers.base_provider import BaseAIProvider
from .providers.deepseek_provider import DeepSeekProvider
from .retrieval.semantic_matcher import SemanticMatcher
from .security.credential_manager import CredentialManager
from .utils.config import CONFIG
from .utils.logging import get_logger, setup_logging

log = get_logger("services")


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
        key = self.credentials.get_key(CONFIG.provider.name)
        if not key:
            return None
        return DeepSeekProvider(key)

    def has_api_key(self) -> bool:
        return self.credentials.has_key(CONFIG.provider.name)

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

    def close(self) -> None:
        self.db.close()

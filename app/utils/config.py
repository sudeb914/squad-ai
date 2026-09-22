"""Central configuration.

All tunable thresholds live here (per the spec: do not scatter magic numbers
through the code). Values can be overridden at runtime from the ``settings``
table, but these are the defaults and the single source of truth for names.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict


@dataclass
class ConfidenceThresholds:
    """Conservative reuse thresholds. Higher = stricter (less likely to reuse)."""
    exact_memory: float = 0.99      # normalized exact match
    fuzzy_reuse: float = 0.90       # min fuzzy ratio (0..1) to reuse memory
    semantic_reuse: float = 0.86    # min cosine similarity to reuse memory
    # Reference is the user's OWN curated Q&A, so a more permissive semantic
    # threshold is safe (measured: related paraphrases 0.63-0.83, unrelated ~0.18).
    reference_semantic_min: float = 0.62
    fuzzy_profile_option: float = 0.82   # profile->option fuzzy mapping
    semantic_min_floor: float = 0.60     # below this, never even consider
    # A result at or above this confidence is considered "resolved locally"
    # and DeepSeek will NOT be called.
    local_resolution_min: float = 0.80


@dataclass
class ProviderConfig:
    name: str = "deepseek"
    # deepseek-chat = the fast, non-reasoning model that WORKS on api.deepseek.com
    # and returns tiny answers (cheap). deepseek-reasoner is smarter but a
    # reasoning model (needs a much larger token budget), so it's opt-in only.
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.1
    max_output_tokens: int = 600
    max_output_tokens_simple: int = 120
    request_timeout_s: float = 30.0
    # deepseek-chat pricing (USD per 1M tokens). Used only for cost estimation.
    price_input_per_m: float = 0.27
    price_input_cached_per_m: float = 0.07
    price_output_per_m: float = 1.10


@dataclass
class AgentRouterConfig:
    """AgentRouter (OpenAI-compatible) provider config.

    Kept separate from ``ProviderConfig`` so switching providers never disturbs
    the DeepSeek settings. Base URL and model stay editable from Settings so a
    future endpoint/model change needs no code edit. Pricing defaults to 0 —
    AgentRouter may not return billing info, so any cost shown is an ESTIMATE
    derived from these (user-configurable) values, never presented as actual.
    """
    name: str = "agentrouter"
    model: str = "deepseek-v4-flash"
    # OpenAI-compatible endpoint per AgentRouter docs (agentrouter.org/docs).
    base_url: str = "https://agentrouter.org/v1"
    temperature: float = 0.1
    max_output_tokens: int = 600
    # A touch higher than DeepSeek's 120 so flash/reasoning models always have
    # room to emit the final JSON (too small a cap can yield empty content).
    max_output_tokens_simple: int = 512
    request_timeout_s: float = 30.0
    # AgentRouter only accepts requests from approved clients and rejects a
    # generic User-Agent with "unauthorized client detected" (before it even
    # checks the key). Identifying as an approved client lets the user's own key
    # authenticate. Editable in case AgentRouter changes the accepted client.
    user_agent: str = "RooCode/1.0"
    # USD per 1M tokens — used ONLY for estimation. 0 => cost unknown/estimate.
    price_input_per_m: float = 0.0
    price_input_cached_per_m: float = 0.0
    price_output_per_m: float = 0.0


@dataclass
class RetrievalConfig:
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reference_chunk_chars: int = 450
    reference_chunk_overlap: int = 60
    top_k_memory: int = 5
    top_k_reference: int = 2          # fewer chunks = fewer tokens = less cost
    max_reference_context_chars: int = 700  # hard cap on reference tokens sent
    max_profile_fields_to_send: int = 8


@dataclass
class CaptureConfig:
    hotkey: str = "F8"
    mode: str = "manual"  # "manual" | "auto"


@dataclass
class AppConfig:
    confidence: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    agentrouter: AgentRouterConfig = field(default_factory=AgentRouterConfig)
    # Which cloud provider the AI-fallback uses: "deepseek" | "agentrouter".
    # Each provider keeps its own key + config, so switching never wipes the
    # other's settings or any local data.
    active_provider: str = "deepseek"
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    log_level: str = "INFO"
    # Semantic search understands paraphrased questions (essential for matching
    # survey wording to the user's reference Q&A). The torch model is loaded in a
    # BACKGROUND thread at startup so it never blocks the UI; until it's ready
    # the app falls back to fuzzy/API, then semantic activates automatically.
    enable_semantic: bool = True
    enable_reasoning_mode: bool = False  # expensive; off by default
    # Cache AI answers for free reuse. The user can turn this off (Settings) to
    # always get a fresh answer — sensible now that deepseek-flash is very cheap.
    enable_memory: bool = True

    def active_provider_config(self):
        """The config object for the currently-selected cloud provider."""
        if self.active_provider == "agentrouter":
            return self.agentrouter
        return self.provider

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Module-level singleton, cheap to construct (no I/O).
CONFIG = AppConfig()

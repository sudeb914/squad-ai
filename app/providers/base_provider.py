"""Provider interface so DeepSeek can later be swapped for Gemini/OpenAI/etc.

The answer engine only ever talks to this interface, and every implementation
must return a structured :class:`ProviderResponse` including token usage so the
usage logger can record cost. Nothing else in the app may call a network AI
directly.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AIRequest:
    """Minimal, relevance-scoped payload — never the whole database."""
    system: str
    question: str
    options: List[str] = field(default_factory=list)
    profile_context: str = ""
    reference_context: str = ""
    recent_context: str = ""
    instructions: str = ""   # user's custom instruction prompt
    max_output_tokens: int = 120


@dataclass
class ProviderResponse:
    answer: str
    selected_option_index: Optional[int]
    confidence: float
    raw_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: int = 0
    success: bool = True
    error: Optional[str] = None


class BaseAIProvider(abc.ABC):
    name: str = "base"
    model: str = "base"

    @abc.abstractmethod
    def answer(self, request: AIRequest) -> ProviderResponse:
        ...

    @abc.abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        ...

    @abc.abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int,
                      cached_tokens: int = 0) -> float:
        ...

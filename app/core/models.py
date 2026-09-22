"""Core dataclasses / enums shared across the answer pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class QuestionType(str, Enum):
    FACT = "FACT"
    BOOLEAN = "BOOLEAN"
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTI_CHOICE = "MULTI_CHOICE"
    NUMERIC = "NUMERIC"
    NUMERIC_RANGE = "NUMERIC_RANGE"
    FREQUENCY = "FREQUENCY"
    RATING = "RATING"
    RANKING = "RANKING"
    OPEN_TEXT = "OPEN_TEXT"
    UNKNOWN = "UNKNOWN"


class AnswerSource(str, Enum):
    LOCAL_FACT = "LOCAL_FACT"
    LOCAL_RULE = "LOCAL_RULE"
    EXACT_MEMORY = "EXACT_MEMORY"
    FUZZY_MEMORY = "FUZZY_MEMORY"
    SEMANTIC_MEMORY = "SEMANTIC_MEMORY"
    DEEPSEEK = "DEEPSEEK"
    UNRESOLVED = "UNRESOLVED"

    @property
    def is_free(self) -> bool:
        return self in {
            AnswerSource.LOCAL_FACT, AnswerSource.LOCAL_RULE,
            AnswerSource.EXACT_MEMORY, AnswerSource.FUZZY_MEMORY,
            AnswerSource.SEMANTIC_MEMORY,
        }

    def ui_label(self) -> str:
        if self in {AnswerSource.LOCAL_FACT, AnswerSource.LOCAL_RULE}:
            return "🟢 Local — Free"
        if self in {AnswerSource.EXACT_MEMORY, AnswerSource.FUZZY_MEMORY,
                    AnswerSource.SEMANTIC_MEMORY}:
            return "🟢 Memory — Free"
        if self is AnswerSource.DEEPSEEK:
            return "🟡 DeepSeek — API"
        return "⚪ Unresolved"


@dataclass
class Option:
    """A single answer choice."""
    original: str
    normalized: str
    index: int


@dataclass
class ParsedQuestion:
    original: str
    normalized: str
    qtype: QuestionType
    options: List[Option] = field(default_factory=list)

    @property
    def has_options(self) -> bool:
        return bool(self.options)


@dataclass
class ApiUsage:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class AnswerResult:
    """Standardized result returned by the AnswerEngine for every question."""
    answer: str
    source: AnswerSource
    confidence: float
    reasoning_code: str
    selected_option: Optional[str] = None
    selected_option_index: Optional[int] = None
    matched_memory_id: Optional[int] = None
    similarity: Optional[float] = None
    api_usage: Optional[ApiUsage] = None
    processing_time_ms: int = 0
    qtype: QuestionType = QuestionType.UNKNOWN
    error: Optional[str] = None
    # Free-form debug candidates (not shown to normal users).
    debug: dict = field(default_factory=dict)

    @property
    def used_api(self) -> bool:
        return self.source is AnswerSource.DEEPSEEK

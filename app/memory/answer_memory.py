"""Service that decides what to persist to answer memory and stores it.

Not every result should become permanent memory, and profile facts must never
be rewritten by answer memory (spec §46). We store results that were genuinely
resolved (memory reuse or a successful API answer, or high-confidence rules),
tagging the source so authority ordering is preserved on read.
"""
from __future__ import annotations

import re
from typing import Optional

from ..core.models import AnswerResult, AnswerSource, ParsedQuestion
from ..database.repositories.memory_repo import MemoryRecord, MemoryRepo
from ..retrieval.semantic_matcher import SemanticMatcher
from ..utils.config import CONFIG
from ..utils.logging import get_logger

log = get_logger("memory")

# Only genuine AI answers are cached. Profile/rule/reference answers are derived
# fresh from the user's data every time (so they never go stale in the cache —
# this is what the user asked for: don't memorize personal/profile info).
_STORABLE = {AnswerSource.DEEPSEEK}

# Never cache a "non-answer" — these poison the cache: once "do you have a
# child? -> Not specified" is stored, it would be replayed forever even after
# the user adds the fact. Also skip trivial chit-chat.
_NON_ANSWER = re.compile(
    r"\b(not specified|not provided|not (?:in|available)|no information|"
    r"cannot determine|can'?t determine|don'?t know|do not know|unknown|"
    r"n/?a|no answer|not sure|none|no data|unable to)\b", re.IGNORECASE)


def _is_non_answer(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 1:
        return True
    if _NON_ANSWER.search(t):
        return True
    return False


class AnswerMemory:
    def __init__(self, repo: MemoryRepo, semantic: SemanticMatcher):
        self.repo = repo
        self.semantic = semantic

    def maybe_store(self, q: ParsedQuestion, result: AnswerResult
                    ) -> Optional[int]:
        if not CONFIG.enable_memory:      # user chose to always answer fresh
            return None
        if result.source not in _STORABLE:
            return None
        if not result.answer or _is_non_answer(result.answer):
            return None
        # Don't cache free-form chit-chat (no options, very short question that
        # isn't really a survey question).
        if not q.has_options and len(q.normalized.split()) <= 2:
            return None
        # Don't create duplicates of an identical normalized question.
        existing = self.repo.find_exact(q.normalized)
        if existing and existing.answer == result.answer:
            return existing.id

        rec = MemoryRecord(
            id=None,
            question_original=q.original,
            question_normalized=q.normalized,
            answer=result.answer,
            options=[o.original for o in q.options],
            selected_option=result.selected_option,
            selected_option_index=result.selected_option_index,
            source=result.source.value,
            category=result.qtype.value,
            confidence=result.confidence,
            relevant_fields=result.debug.get("relevant_fields", {}),
            embedding=None,
        )
        mem_id = self.repo.add(rec)
        rec.id = mem_id
        # Precompute embedding so future semantic search is cheap (best effort).
        try:
            self.semantic.ensure_embedding_for(rec)
        except Exception as exc:  # noqa: BLE001
            log.debug("embedding precompute skipped: %s", exc)
        log.info("Stored memory #%d (%s)", mem_id, result.source.value)
        return mem_id

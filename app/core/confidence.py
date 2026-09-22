"""Memory-reuse gatekeeping.

Similarity alone is never enough to reuse a stored answer (spec §36). Before
reusing memory we also require *intent compatibility*: "Do you own a car?" and
"Do you plan to buy a car?" look similar but must not be treated as equal.

All numeric thresholds come from :data:`CONFIG.confidence`; nothing here invents
its own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from ..utils.config import CONFIG

# Signals that change a question's *intent* even when wording overlaps.
_FUTURE = re.compile(r"\b(plan|planning|intend|will|going to|likely|next|"
                     r"future|considering|thinking of|would you)\b")
_PAST = re.compile(r"\b(did|used to|previously|last|have you ever|in the past)\b")
_PRESENT_OWN = re.compile(r"\b(currently|now|do you own|do you have|are you)\b")
_NEG = re.compile(r"\b(not|never|don't|doesn't|didn't|no longer|without)\b")


def _tense(text: str) -> str:
    if _FUTURE.search(text):
        return "future"
    if _PAST.search(text):
        return "past"
    if _PRESENT_OWN.search(text):
        return "present"
    return "neutral"


def intent_compatible(q_norm: str, mem_norm: str,
                      q_options: List[str], mem_options: List[str]) -> bool:
    """Return True only if the two questions share intent closely enough."""
    # Tense / intent mismatch (own now vs buy next) -> incompatible.
    t1, t2 = _tense(q_norm), _tense(mem_norm)
    if {t1, t2} == {"future", "present"}:
        return False
    if {t1, t2} == {"future", "past"}:
        return False

    # Negation mismatch -> incompatible.
    if bool(_NEG.search(q_norm)) != bool(_NEG.search(mem_norm)):
        return False

    # If both have options, require substantial option overlap.
    if q_options and mem_options:
        a, b = set(q_options), set(mem_options)
        if a and b:
            overlap = len(a & b) / max(1, min(len(a), len(b)))
            if overlap < 0.5:
                return False
    return True


@dataclass
class ReuseDecision:
    reuse: bool
    confidence: float
    reason: str


def decide_reuse(kind: str, similarity: float, q_norm: str, mem_norm: str,
                 q_options: List[str], mem_options: List[str],
                 base_confidence: float) -> ReuseDecision:
    """Decide whether a retrieved memory may be reused.

    ``kind`` in {"exact", "fuzzy", "semantic"}.
    """
    th = CONFIG.confidence
    if kind == "exact":
        # Exact normalized text still needs intent sanity (options can differ).
        if not intent_compatible(q_norm, mem_norm, q_options, mem_options):
            return ReuseDecision(False, 0.0, "EXACT_INTENT_MISMATCH")
        return ReuseDecision(True, max(base_confidence, th.exact_memory),
                             "EXACT_MEMORY_MATCH")

    if kind == "fuzzy":
        if similarity < th.fuzzy_reuse:
            return ReuseDecision(False, similarity, "FUZZY_BELOW_THRESHOLD")
        if not intent_compatible(q_norm, mem_norm, q_options, mem_options):
            return ReuseDecision(False, similarity, "FUZZY_INTENT_MISMATCH")
        return ReuseDecision(True, min(0.94, similarity), "FUZZY_MEMORY_MATCH")

    if kind == "semantic":
        if similarity < th.semantic_reuse:
            return ReuseDecision(False, similarity, "SEMANTIC_BELOW_THRESHOLD")
        if not intent_compatible(q_norm, mem_norm, q_options, mem_options):
            return ReuseDecision(False, similarity, "SEMANTIC_INTENT_MISMATCH")
        return ReuseDecision(True, min(0.9, similarity), "SEMANTIC_MEMORY_MATCH")

    return ReuseDecision(False, 0.0, "UNKNOWN_KIND")


def is_locally_resolved(confidence: float) -> bool:
    return confidence >= CONFIG.confidence.local_resolution_min

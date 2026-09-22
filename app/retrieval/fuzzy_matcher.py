"""Fuzzy string similarity.

Uses RapidFuzz when installed (fast, high quality). Falls back to the stdlib
``difflib`` so the deterministic core runs with zero third-party dependencies.
All ratios are returned in the 0..1 range for consistency.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

try:  # pragma: no cover - exercised by availability, not logic
    from rapidfuzz import fuzz as _rf_fuzz

    _HAVE_RAPIDFUZZ = True
except Exception:  # noqa: BLE001
    _rf_fuzz = None
    _HAVE_RAPIDFUZZ = False

if not _HAVE_RAPIDFUZZ:
    import difflib


def have_rapidfuzz() -> bool:
    return _HAVE_RAPIDFUZZ


def ratio(a: str, b: str) -> float:
    """Return similarity of ``a`` and ``b`` in 0..1."""
    a = a or ""
    b = b or ""
    if not a and not b:
        return 1.0
    if _HAVE_RAPIDFUZZ:
        return _rf_fuzz.ratio(a, b) / 100.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def token_set_ratio(a: str, b: str) -> float:
    """Order/duplication-insensitive similarity in 0..1."""
    a = a or ""
    b = b or ""
    if _HAVE_RAPIDFUZZ:
        return _rf_fuzz.token_set_ratio(a, b) / 100.0
    # difflib fallback: compare sorted unique token strings.
    sa = " ".join(sorted(set(a.split())))
    sb = " ".join(sorted(set(b.split())))
    return difflib.SequenceMatcher(None, sa, sb).ratio()


def best_match(
    query: str, candidates: Iterable[str]
) -> Tuple[Optional[int], float]:
    """Return ``(index_of_best, score)`` using a blend of ratio metrics."""
    best_i: Optional[int] = None
    best_s = 0.0
    for i, cand in enumerate(candidates):
        s = max(ratio(query, cand), token_set_ratio(query, cand))
        if s > best_s:
            best_s, best_i = s, i
    return best_i, best_s

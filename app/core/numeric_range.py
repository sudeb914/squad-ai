"""Deterministic numeric & range resolution.

Handles the many textual range formats surveys use so we never spend API money
on arithmetic Python can do:

    "18-24", "31 to 40", "35+", "35 or older", "under 35", "less than 35",
    "over 35", "more than 35", "51+", "$50,000-$74,999", "45 or younger".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# No leading sign: in survey ranges a hyphen is a separator ("31-40"), never a
# negative sign, and survey values are non-negative.
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_K_SUFFIX = re.compile(r"(\d[\d,.]*)\s*[kK]\b")


def parse_number(text: str) -> Optional[float]:
    """Extract the first number from ``text`` (handles $, commas, 50k)."""
    if text is None:
        return None
    s = str(text)
    km = _K_SUFFIX.search(s)
    if km:
        try:
            return float(km.group(1).replace(",", "")) * 1000.0
        except ValueError:
            pass
    m = _NUM_RE.search(s.replace("$", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


@dataclass
class Bound:
    """An inclusive numeric interval; ``None`` = open on that side."""
    low: Optional[float]
    high: Optional[float]

    def contains(self, v: float) -> bool:
        if self.low is not None and v < self.low:
            return False
        if self.high is not None and v > self.high:
            return False
        return True

    @property
    def is_open(self) -> bool:
        return self.low is None or self.high is None


def parse_bound(text: str) -> Optional[Bound]:
    """Parse a single option / phrase into a :class:`Bound`."""
    if not text:
        return None
    t = text.lower().strip()

    # explicit range: "18-24", "18 to 24", "$50,000 - $74,999"
    nums = _all_numbers(t)
    has_dash = bool(re.search(r"\d\s*(?:-|–|to)\s*\$?\d", t))
    if has_dash and len(nums) >= 2:
        return Bound(low=min(nums[0], nums[1]), high=max(nums[0], nums[1]))

    if not nums:
        return None
    n = nums[0]

    # open-ended upward
    if re.search(r"\+\s*$|or older|or more|or above|or greater|and older|and up|"
                 r"and above|over|more than|greater than|older than|at least", t):
        # "more than 35" is strictly >; treat as >= (n+epsilon handled by caller
        # rarely matters for surveys). We keep inclusive for "or more/older".
        if re.search(r"more than|greater than|older than|over", t) and not \
           re.search(r"or more|or older", t):
            return Bound(low=n + 1e-9, high=None)
        return Bound(low=n, high=None)

    # open-ended downward
    if re.search(r"under|less than|below|younger than|or younger|or less|"
                 r"or fewer|up to|at most|fewer than", t):
        if re.search(r"under|less than|below|younger than|fewer than", t) and \
           not re.search(r"or less|or younger|or fewer", t):
            return Bound(low=None, high=n - 1e-9)
        return Bound(low=None, high=n)

    # bare single number as an exact bucket (e.g. option "40")
    return Bound(low=n, high=n)


def _all_numbers(text: str) -> List[float]:
    out: List[float] = []
    for m in _NUM_RE.finditer(text.replace("$", "")):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    # handle 50k style
    for km in _K_SUFFIX.finditer(text):
        try:
            out.append(float(km.group(1).replace(",", "")) * 1000.0)
        except ValueError:
            continue
    return out


def match_range_option(value: float, option_texts: List[str]
                       ) -> Tuple[Optional[int], List[Bound]]:
    """Return ``(index, bounds)`` of the option whose range contains ``value``.

    Prefers a *closed* bounded interval over an open one when both match, so
    "31-40" wins over "18+".
    """
    bounds = [parse_bound(o) for o in option_texts]
    closed_hit: Optional[int] = None
    open_hit: Optional[int] = None
    for i, b in enumerate(bounds):
        if b is None:
            continue
        if b.contains(value):
            if b.is_open:
                if open_hit is None:
                    open_hit = i
            else:
                # For exact-number buckets (low==high) require equality already
                # satisfied by contains; prefer narrower closed intervals.
                if closed_hit is None:
                    closed_hit = i
    idx = closed_hit if closed_hit is not None else open_hit
    return idx, bounds


def answer_numeric_boolean(value: float, question_norm: str) -> Optional[bool]:
    """Answer 'Are you X or older?' style yes/no from a numeric value."""
    b = parse_bound(question_norm)
    if b is None:
        return None
    # Only meaningful if the question actually expresses a threshold.
    if b.low is None and b.high is None:
        return None
    # A bare single number ("are you 35?") -> equality check.
    if b.low is not None and b.high is not None and b.low == b.high:
        return abs(value - b.low) < 1e-6
    return b.contains(value)

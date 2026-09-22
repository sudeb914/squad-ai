"""Link questions to profile fields and map profile values onto options.

This is where deterministic *relevance* lives: given a question, which profile
field (if any) answers it, and which option best represents a profile value.
The same relevance logic feeds the API context builder so DeepSeek only ever
receives the handful of fields likely to matter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import normalization as N
from .models import Option
from ..retrieval import fuzzy_matcher as F

# Concept -> trigger words that, if present in a question, point at a field
# whose key contains the concept token. Keeps profile linking robust to phrasing.
_KEY_SYNONYMS: Dict[str, List[str]] = {
    "age": ["age", "aged", "old", "older", "younger", "young", "born", "birth"],
    "employment": ["employment", "employed", "work", "working", "job",
                   "occupation", "profession"],
    "income": ["income", "earn", "salary", "wage", "household income"],
    "gender": ["gender", "sex"],
    "marital": ["marital", "married", "relationship", "spouse"],
    "education": ["education", "school", "degree", "study", "studied"],
    "children": ["children", "kids", "child", "dependents"],
    "household": ["household", "people", "live", "family size"],
    "state": ["state", "province"],
    "city": ["city", "town"],
    "zip": ["zip", "postal", "postcode"],
    "country": ["country", "nation"],
    "occupation": ["occupation", "job", "profession", "role"],
    "vehicle": ["vehicle", "car", "cars", "automobile"],
    "pet": ["pet", "pets", "dog", "cat"],
    "home": ["home", "house", "own", "rent", "ownership", "residence"],
    "industry": ["industry", "sector"],
}

# Equivalence groups so a stored value maps onto a differently-worded option.
_VALUE_OPTION_GROUPS: List[set] = [
    {"full time", "fulltime", "full-time", "full time employed",
     "employed full time", "working full time", "work full time"},
    {"part time", "parttime", "part-time", "part time employed",
     "working part time", "work part time"},
    {"unemployed", "not employed", "no job", "out of work", "jobless"},
    {"self employed", "self-employed", "freelance", "freelancer",
     "business owner"},
    {"retired", "pensioner"},
    {"student", "in school", "studying"},
    {"yes", "y", "true", "yeah", "yep"},
    {"no", "n", "false", "nope"},
    {"male", "man", "m"},
    {"female", "woman", "f"},
    {"own", "owner", "homeowner", "i own", "own my home"},
    {"rent", "renter", "renting", "i rent"},
    {"married", "spouse"},
    {"single", "unmarried", "never married"},
]


def _expand(token: str) -> List[str]:
    for concept, words in _KEY_SYNONYMS.items():
        if concept in token:
            return [token] + words
    return [token]


@dataclass
class FieldMatch:
    key: str
    value: str
    score: float


class ProfileResolver:
    def __init__(self, profile: Dict[str, str]):
        self.profile = {k: v for k, v in profile.items() if v not in (None, "")}

    # -- field relevance --------------------------------------------------
    def score_field(self, key: str, question_norm: str,
                    option_norms: List[str]) -> float:
        q_tokens = set(question_norm.split())
        o_tokens = set(" ".join(option_norms).split())
        key_tokens = N.normalize(key.replace("_", " ")).split()
        best = 0.0
        strong = 0  # key tokens with a solid match (for coverage tiebreak)
        for raw_tok in key_tokens:
            tok_best = 0.0
            for tok in _expand(raw_tok):
                if tok in q_tokens:
                    tok_best = max(tok_best, 1.0)
                elif tok in o_tokens:
                    tok_best = max(tok_best, 0.75)
                else:
                    tok_best = max(
                        tok_best, 0.6 * F.token_set_ratio(tok, question_norm))
            best = max(best, tok_best)
            if tok_best >= 0.75:
                strong += 1
        # Tiebreak: when two fields share the same peak match, prefer the one
        # whose key is more fully covered (e.g. "income" over "household_size"
        # for a "household income" question). Small so it never crosses tiers.
        coverage = strong / len(key_tokens) if key_tokens else 0.0
        return best + 0.05 * coverage if best > 0 else 0.0

    def relevant_field(self, question_norm: str,
                       option_norms: List[str] | None = None
                       ) -> Optional[FieldMatch]:
        option_norms = option_norms or []
        best: Optional[FieldMatch] = None
        for key, value in self.profile.items():
            s = self.score_field(key, question_norm, option_norms)
            if best is None or s > best.score:
                best = FieldMatch(key=key, value=value, score=s)
        if best and best.score >= 0.75:
            return best
        return None

    def top_fields(self, question_norm: str, option_norms: List[str],
                   k: int) -> List[FieldMatch]:
        scored = [FieldMatch(key=k_, value=v,
                             score=self.score_field(k_, question_norm,
                                                     option_norms))
                  for k_, v in self.profile.items()]
        scored.sort(key=lambda m: m.score, reverse=True)
        return [m for m in scored[:k] if m.score > 0.3]

    # -- value -> option mapping -----------------------------------------
    @staticmethod
    def _group_of(text_norm: str) -> Optional[frozenset]:
        for grp in _VALUE_OPTION_GROUPS:
            if text_norm in grp:
                return frozenset(grp)
        return None

    def map_value_to_option(self, value: str, options: List[Option],
                            fuzzy_threshold: float
                            ) -> Tuple[Optional[Option], float, str]:
        """Return ``(option, score, reasoning_code)`` best matching ``value``.

        Uses a hyphen/space-insensitive ("loose") form so stored values like
        "Full-time employed" map onto options worded "Working full time".
        """
        if not options:
            return None, 0.0, ""
        v = N.normalize_loose(value)
        opt_loose = [N.normalize_loose(o.original) for o in options]

        # 1. exact (loose) normalized
        for opt, ol in zip(options, opt_loose):
            if ol == v:
                return opt, 1.0, "PROFILE_EXACT_MATCH"

        # 2. synonym group: value and option in the same equivalence group
        vg = self._group_of(v)
        if vg:
            for opt, ol in zip(options, opt_loose):
                if ol in vg:
                    return opt, 0.95, "PROFILE_SYNONYM_MATCH"

        # 3. containment (value words subset of option or vice versa)
        for opt, ol in zip(options, opt_loose):
            if v and (v in ol or ol in v):
                return opt, 0.9, "PROFILE_CONTAINS_MATCH"

        # 4. fuzzy
        idx, score = F.best_match(v, opt_loose)
        if idx is not None and score >= fuzzy_threshold:
            return options[idx], score, "PROFILE_FUZZY_MATCH"

        return None, score, ""

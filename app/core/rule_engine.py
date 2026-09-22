"""Level-1 deterministic answering ($0, highest priority).

Given a parsed question and the profile, try to resolve without any retrieval or
API. Returns ``None`` when it cannot answer confidently — callers then fall
through to memory / semantic / API.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from . import numeric_range as NR
from .models import AnswerResult, AnswerSource, ParsedQuestion, QuestionType
from .profile_resolver import ProfileResolver
from ..utils.config import CONFIG

# Subjective markers: don't answer these from a bare profile fact.
_SUBJECTIVE_RE = re.compile(
    r"\b(favorite|favourite|prefer|preferred|like|dislike|best|worst|ideal|"
    r"opinion|most|least|why|rate|rating|enjoy|love|hate|happy|satisfied|"
    r"would you|do you plan|planning|likely)\b")

# A question about a family member must NOT be answered from the MAIN person's
# fields (e.g. "my wife's name" must not return the user's own name). Let the AI
# answer these from the full profile text instead.
_RELATIVE_RE = re.compile(
    r"\b(wife|husband|spouse|partner|fiance[e]?|child|children|kid|kids|son|"
    r"sons|daughter|daughters|mother|mom|father|dad|parent|parents|sibling|"
    r"brother|sister|dependent|dependents|spouse'?s)\b", re.IGNORECASE)

# Words for an EXTERNAL thing the question may be about (a car, a brand, a
# phone…). If one of these appears and it is not itself a profile field, a stray
# field-word match (e.g. "brand NAME of your car" -> the person's name) is wrong,
# so we defer to the AI, which sees the whole profile.
_EXTERNAL_RE = re.compile(
    r"\b(car|cars|vehicle|automobile|brand|brands|product|products|company|"
    r"companies|employer|phone|smartphone|mobile|device|laptop|computer|"
    r"tablet|pet|pets|dog|cat|game|games|console|show|shows|event|events|"
    r"dataset|website|site|app|apps|application|software|service|subscription|"
    r"movie|film|song|book|team|store|shop|restaurant|hotel|bank|card|account|"
    r"model|make)\b", re.IGNORECASE)


def _is_external_subject(q_norm: str, profile_keys) -> bool:
    """True if the question is about an external object that isn't a profile
    field — in which case we should not answer from a stray profile field."""
    m = _EXTERNAL_RE.search(q_norm)
    if not m:
        return False
    word = m.group(1).lower()
    for k in profile_keys:                 # answerable if the user HAS that field
        kl = k.lower()
        if word in kl or kl in word:
            return False
    return True


class RuleEngine:
    def __init__(self, profile: Dict[str, str]):
        self.profile = profile
        self.resolver = ProfileResolver(profile)
        self.th = CONFIG.confidence

    def resolve(self, q: ParsedQuestion) -> Optional[AnswerResult]:
        # Questions about a relative are not about the main person's own fields;
        # defer to reference/AI (which see the full family profile).
        if _RELATIVE_RE.search(q.normalized):
            return None
        # Questions about an external object (a car, a brand, a phone…) that the
        # user has no profile field for: don't answer from a stray field word.
        if _is_external_subject(q.normalized, self.profile.keys()):
            return None
        opt_norms = [o.normalized for o in q.options]
        field = self.resolver.relevant_field(q.normalized, opt_norms)
        if field is None:
            return None

        value = field.value
        num = NR.parse_number(value)

        # --- NUMERIC: "what is your age?" ---------------------------------
        if q.qtype == QuestionType.NUMERIC and not q.has_options:
            if num is not None:
                return self._result(
                    answer=self._fmt_num(num, value), source=AnswerSource.LOCAL_FACT,
                    confidence=0.97, reasoning="PROFILE_NUMERIC_FACT", q=q)

        # --- BOOLEAN threshold: "are you 35 or older?" --------------------
        if q.qtype == QuestionType.BOOLEAN and num is not None:
            verdict = NR.answer_numeric_boolean(num, q.normalized)
            if verdict is not None:
                ans = "Yes" if verdict else "No"
                opt = self._find_bool_option(q, verdict)
                return self._result(
                    answer=opt.original if opt else ans,
                    selected_option=opt.original if opt else None,
                    selected_option_index=opt.index if opt else None,
                    source=AnswerSource.LOCAL_RULE, confidence=0.96,
                    reasoning="NUMERIC_BOOLEAN_MATCH", q=q)

        # --- NUMERIC_RANGE options: "which age range?" --------------------
        if q.qtype == QuestionType.NUMERIC_RANGE and q.has_options and \
                num is not None:
            idx, _ = NR.match_range_option(num, [o.original for o in q.options])
            if idx is not None:
                opt = q.options[idx]
                return self._result(
                    answer=opt.original, selected_option=opt.original,
                    selected_option_index=opt.index,
                    source=AnswerSource.LOCAL_RULE, confidence=0.95,
                    reasoning="NUMERIC_RANGE_MATCH", q=q)

        # --- Choice: map profile value onto an option ---------------------
        if q.has_options and q.qtype in (
                QuestionType.SINGLE_CHOICE, QuestionType.BOOLEAN,
                QuestionType.FREQUENCY, QuestionType.NUMERIC_RANGE):
            opt, score, code = self.resolver.map_value_to_option(
                value, q.options, self.th.fuzzy_profile_option)
            if opt is not None:
                conf = min(0.97, 0.6 + 0.4 * score)
                return self._result(
                    answer=opt.original, selected_option=opt.original,
                    selected_option_index=opt.index,
                    source=AnswerSource.LOCAL_FACT, confidence=conf,
                    reasoning=code, q=q)

        # --- FACT with no options: return the stored value ----------------
        if q.qtype == QuestionType.FACT and not q.has_options:
            # Require a strong field link to avoid answering the wrong fact.
            if field.score >= 0.95:
                return self._result(
                    answer=value, source=AnswerSource.LOCAL_FACT,
                    confidence=0.95, reasoning="PROFILE_EXACT_MATCH", q=q)

        # --- Value-prompt fallback: any phrasing that clearly names a field --
        # Handles "Select your age", "Your age is", "Age?", "Please enter your
        # age", etc. — different wordings, same profile answer. Skipped for
        # yes/no and subjective questions, and ONLY for SHORT direct prompts:
        # a long multi-option question that merely happens to contain a field
        # word (e.g. "PlayStation State of Play" -> "state") must NOT return a
        # profile value.
        if (not q.has_options and q.qtype != QuestionType.BOOLEAN
                and field.score >= 0.95
                and len(q.normalized.split()) <= 7
                and not _SUBJECTIVE_RE.search(q.normalized)):
            answer = self._fmt_num(num, value) if num is not None else value
            return self._result(
                answer=answer, source=AnswerSource.LOCAL_FACT, confidence=0.9,
                reasoning="PROFILE_VALUE_PROMPT", q=q)

        return None

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _fmt_num(num: float, original: str) -> str:
        if num.is_integer():
            return str(int(num))
        return original.strip()

    @staticmethod
    def _find_bool_option(q: ParsedQuestion, verdict: bool):
        want = {"yes", "true"} if verdict else {"no", "false"}
        for opt in q.options:
            if opt.normalized in want:
                return opt
        return None

    def _result(self, *, answer, source, confidence, reasoning, q,
                selected_option=None, selected_option_index=None) -> AnswerResult:
        return AnswerResult(
            answer=answer, source=source, confidence=confidence,
            reasoning_code=reasoning, selected_option=selected_option,
            selected_option_index=selected_option_index, qtype=q.qtype)

"""Classify a question into a :class:`QuestionType` and parse its options.

Version 1 uses robust heuristics, not a model. Priority is correct handling of
FACT / BOOLEAN / SINGLE_CHOICE / NUMERIC / NUMERIC_RANGE because those are the
types most often resolvable locally.
"""
from __future__ import annotations

import re

from . import normalization as N
from . import option_parser
from .models import ParsedQuestion, QuestionType

_YESNO_OPTIONS = {"yes", "no", "true", "false"}
_BOOL_LEAD = re.compile(
    r"^(are|is|do|does|did|have|has|had|can|could|would|will|should|were|was)\b"
)
_RANGE_IN_OPTION = re.compile(r"(\d[\d,]*)\s*(?:-|to|–)\s*(\d[\d,]*)|(\d[\d,]*)\s*\+|\bunder\b|\bover\b|\bless than\b|\bmore than\b|or older|or younger|or more|or less")
_RATING_RE = re.compile(r"\b(scale|rate|rating|1\s*(?:-|to)\s*(?:5|7|10))\b")
_FREQ_WORDS = {"never", "rarely", "sometimes", "often", "always", "daily",
               "weekly", "monthly", "yearly", "occasionally"}
_NUMERIC_ASK = re.compile(r"\b(how many|how much|what is your age|number of|"
                          r"how old)\b")
_RANK_RE = re.compile(r"\b(rank|order|most to least|least to most|prioriti[sz]e)\b")
_MULTI_RE = re.compile(r"\b(select all|choose all|all that apply|check all)\b")


def classify(question_norm: str, options) -> QuestionType:
    opt_norms = [o.normalized for o in options]
    opt_set = set(opt_norms)

    if _MULTI_RE.search(question_norm):
        return QuestionType.MULTI_CHOICE

    # Boolean: yes/no options, or a boolean-leading verb with no options.
    if opt_set and opt_set <= _YESNO_OPTIONS:
        return QuestionType.BOOLEAN
    if not options and _BOOL_LEAD.match(question_norm):
        return QuestionType.BOOLEAN

    if _RANK_RE.search(question_norm):
        return QuestionType.RANKING

    if _RATING_RE.search(question_norm):
        return QuestionType.RATING

    # Numeric range: options contain numeric ranges / bounds.
    if options and any(_RANGE_IN_OPTION.search(o) for o in opt_norms):
        return QuestionType.NUMERIC_RANGE

    # Frequency: options are frequency words.
    if options and any(o in _FREQ_WORDS for o in opt_norms):
        return QuestionType.FREQUENCY

    if options:
        return QuestionType.SINGLE_CHOICE

    # No options.
    if _NUMERIC_ASK.search(question_norm):
        return QuestionType.NUMERIC

    if question_norm.startswith(("what", "which", "where", "who", "when",
                                 "name your", "state your")):
        return QuestionType.FACT

    if _BOOL_LEAD.match(question_norm):
        return QuestionType.BOOLEAN

    return QuestionType.OPEN_TEXT


def parse(text: str, explicit_options=None) -> ParsedQuestion:
    question_text, options = option_parser.extract(text, explicit_options)
    q_norm = N.normalize(question_text)
    qtype = classify(q_norm, options)
    # "Select all that apply" often sits on its own line (stripped from the
    # question), so also check the full raw text for the multi-select marker.
    if options and _MULTI_RE.search(N.normalize(text)):
        qtype = QuestionType.MULTI_CHOICE
    return ParsedQuestion(
        original=question_text.strip(),
        normalized=q_norm,
        qtype=qtype,
        options=options,
    )

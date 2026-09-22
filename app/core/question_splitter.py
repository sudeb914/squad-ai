"""Split one OCR'd page into its separate questions.

A single screenshot often holds several questions, each with its own options. If
the whole page is answered as one question the user only gets a single answer and
can't tell which option belongs to which question. This module cuts the page into
per-question blocks (question text + the options that belong to it) so each can be
answered independently.

Heuristic (works for the common survey layout Question → Options → Question →
Options): questions end with '?'. The lines between two question marks are the
previous question's options plus the next question's (possibly multi-line) text;
we assign the short/marker "option-like" lines to the earlier question and the
trailing text lines to the next question. When there is at most one '?', the page
is treated as a single question (safe fallback — never a wrong split).
"""
from __future__ import annotations

import re
from typing import List

_OPTION_MARKER = re.compile(r"^\s*(?:[A-Za-z]|\d{1,2})\s*[.)]\s+\S|^\s*[-•*✓☐○●]\s*\S")
_MAX_OPTION_LEN = 45


def _looks_like_option(line: str) -> bool:
    """Option lines are short, or start with a bullet / letter / number marker."""
    s = line.strip()
    if not s:
        return False
    if _OPTION_MARKER.match(s):
        return True
    # short line without sentence/clause punctuation reads like a choice, not
    # prose (a trailing comma/colon/period/question-mark signals question text).
    return len(s) <= _MAX_OPTION_LEN and not s.endswith((".", ":", "?", ",", ";"))


def split_questions(text: str) -> List[str]:
    """Return a list of question blocks. Length 1 means a single question."""
    raw = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not raw:
        return []

    qmarks = [i for i, ln in enumerate(raw) if ln.endswith("?")]
    if len(qmarks) <= 1:
        return ["\n".join(raw)]

    blocks: List[str] = []
    start = 0  # first unassigned line
    for qi, qend in enumerate(qmarks):
        # The first question owns everything before its '?': nothing precedes it
        # to peel off as a previous question's options.
        if qi == 0:
            qstart = start
        else:
            # Walk back from the '?' over consecutive non-option lines: that run
            # is THIS question's (possibly multi-line) text.
            qstart = qend
            while qstart - 1 >= start and not _looks_like_option(raw[qstart - 1]):
                qstart -= 1

        # Lines between `start` and this question's text are the PREVIOUS
        # question's options.
        if qi > 0 and qstart > start:
            prev_opts = raw[start:qstart]
            if prev_opts:
                blocks[-1] = blocks[-1] + "\n" + "\n".join(prev_opts)

        blocks.append("\n".join(raw[qstart:qend + 1]))
        start = qend + 1

    # Anything after the last '?' are the last question's options.
    if start < len(raw):
        blocks[-1] = blocks[-1] + "\n" + "\n".join(raw[start:])

    return blocks

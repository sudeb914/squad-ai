"""Extract answer options from OCR / free text.

Survey OCR typically yields a question line followed by option lines, often with
markers like ``A)``, ``1.``, ``-`` or bullets. We identify those, strip the
markers, and keep everything else as the question.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from . import normalization as N
from .models import Option

_PREFIX_RE = re.compile(
    r"^\s*(?:\(?[A-Za-z]\)|\(?[A-Za-z]\.|\(?\d{1,2}\)|\(?\d{1,2}\.|[-*•·▢□○●☐])\s+",
)

# Lines that are survey instructions/chrome, not real answer options.
_INSTRUCTION_RE = re.compile(
    r"\b(choose|select|pick|following|all that apply|please|mark all|"
    r"check all|tick|required|optional|one answer|scroll)\b", re.IGNORECASE)


def _looks_like_option(line: str) -> bool:
    return bool(_PREFIX_RE.match(line))


# Bare single-letter option markers: "A The Game Awards", "B) ...", "C. ...".
_BARE_LETTER = re.compile(r"^\s*([A-Za-z])[.):\-]?\s+(?=\S)")


def _strip_bare_letter(line: str) -> str:
    return _BARE_LETTER.sub("", line, count=1).strip()


def _plausible_option(line: str) -> bool:
    """A choice-like line (no trailing '?', not an instruction). Survey options
    can be fairly long ("Summer Game Fest / Xbox Games Showcase / …")."""
    s = line.strip().strip("_").strip()
    if not s or s.endswith("?"):
        return False
    if _INSTRUCTION_RE.search(s):
        return False
    return len(s) <= 120 and len(s.split()) <= 20


def build_options(raw_options: List[str]) -> List[Option]:
    out: List[Option] = []
    for i, raw in enumerate(raw_options):
        stripped = N.strip_option_prefix(raw)
        out.append(Option(original=stripped, normalized=N.normalize(stripped),
                          index=i))
    return out


def extract(text: str, explicit_options: List[str] | None = None
            ) -> Tuple[str, List[Option]]:
    """Return ``(question_text, options)``.

    If ``explicit_options`` are given (e.g. UI supplied them), they win.
    Otherwise options are inferred from marker prefixes in the text.
    """
    if explicit_options:
        opts = [o for o in (s.strip() for s in explicit_options) if o]
        # First non-empty line is the question when options are explicit.
        q_lines = [ln for ln in N.clean_lines(text)]
        question = q_lines[0] if q_lines else text.strip()
        return question, build_options(opts)

    lines = N.clean_lines(text)
    if not lines:
        return "", []

    marked = [ln for ln in lines if _looks_like_option(ln)]
    if len(marked) >= 2:
        # Options are the marked lines; question is the joined preceding text.
        first_marked_idx = next(i for i, ln in enumerate(lines)
                                if _looks_like_option(ln))
        question = " ".join(lines[:first_marked_idx]).strip() or lines[0]
        raw_opts = [ln for ln in lines if _looks_like_option(ln)]
        return question, build_options(raw_opts)

    # Marker-less options (radio buttons): the common survey case. Options are
    # short lines that follow the question, minus instruction lines.
    q_indices = [i for i, ln in enumerate(lines) if ln.rstrip().endswith("?")]
    q_idx = q_indices[-1] if q_indices else 0
    question = lines[q_idx] if q_indices else lines[0]
    candidates = [ln for ln in lines[q_idx + 1:] if _plausible_option(ln)]
    if len(candidates) >= 2:
        # Strip bare single-letter markers ("A The Game Awards" -> "The Game…")
        # ONLY when the candidates form a distinct A/B/C… sequence — so a real
        # option like "A lot" / "A little" is left untouched.
        letters = [m.group(1).upper() for c in candidates
                   if (m := _BARE_LETTER.match(c))]
        if len(letters) >= max(2, len(candidates) - 1) and \
                len(set(letters)) == len(letters):
            candidates = [_strip_bare_letter(c) for c in candidates]
        return question, build_options(candidates)

    # No reliable markers: treat as a single question with no options.
    return " ".join(lines).strip(), []

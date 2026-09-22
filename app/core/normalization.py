"""Text normalization used everywhere before matching.

We keep the ORIGINAL text intact (callers store it separately) and produce a
normalized form for comparison. Handles OCR artifacts, curly quotes, option
prefixes, whitespace and unicode inconsistencies.
"""
from __future__ import annotations

import re
import unicodedata

# Curly quotes / dashes / misc unicode -> ascii equivalents.
_TRANSLATE = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-",  # en/em dash, minus
    " ": " ", "​": "", "﻿": "",
    "…": "...",
}
_TRANS_TABLE = {ord(k): v for k, v in _TRANSLATE.items()}

# Leading option markers: "A)", "A.", "(a)", "1.", "1)", "- ", "• ".
_OPTION_PREFIX_RE = re.compile(
    r"^\s*(?:\(?[A-Za-z]\)|\(?[A-Za-z]\.|\(?\d{1,2}\)|\(?\d{1,2}\.|[-*•·]) *",
)
_WS_RE = re.compile(r"\s+")


def strip_option_prefix(text: str) -> str:
    """Remove a single leading option marker like ``A)`` or ``1.``."""
    return _OPTION_PREFIX_RE.sub("", text, count=1).strip()


def normalize(text: str) -> str:
    """Return a canonical lowercase form for matching.

    NOT lossy on the caller's side: the original is always preserved elsewhere.
    """
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = t.translate(_TRANS_TABLE)
    t = t.strip()
    t = strip_option_prefix(t)
    t = t.lower()
    # Drop trailing question/colon punctuation but keep internal meaning.
    t = re.sub(r"[?:;,.\s]+$", "", t)
    # Collapse remaining punctuation to spaces for token robustness, but keep
    # ranges/decimals intact (digits, hyphen, dollar, %) and in-word apostrophes.
    t = re.sub(r"[^\w\s$%\-']", " ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def normalize_loose(text: str) -> str:
    """Even more aggressive: also removes hyphens and $, for bag-of-words."""
    t = normalize(text)
    t = re.sub(r"[$%\-]", " ", t)
    return _WS_RE.sub(" ", t).strip()


def clean_lines(text: str) -> list[str]:
    """Split OCR text into cleaned, non-empty lines preserving order."""
    out: list[str] = []
    for raw in str(text).replace("\r", "\n").split("\n"):
        s = raw.translate(_TRANS_TABLE).strip()
        if s:
            out.append(s)
    return out

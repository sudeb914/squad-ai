"""Answer questions FREE from the user's reference Q&A — no API call.

The user's reference text is typically their own answered questions. When an
incoming question matches one of those reference questions closely (and the
intent is compatible), we return the stored answer locally at $0 instead of
paying DeepSeek. Supports common formats:

    Q: ...        A: ...
    Question: ... Answer: ...
    <line ending with ?>   <next line is the answer>
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import normalization as N
from ..retrieval import fuzzy_matcher as F
from ..retrieval.embedding_manager import EmbeddingManager, cosine
from ..utils.config import CONFIG

_Q_MARK = re.compile(r"^\s*(?:q|question)\s*[:.)\-]\s*(.+)$", re.IGNORECASE)
_A_MARK = re.compile(r"^\s*(?:a|ans|answer)\s*[:.)\-]\s*(.+)$", re.IGNORECASE)
# Inline "… A: answer" / "… Answer: answer" on the SAME line as the question.
# Capital A / Answer / Ans only, to avoid matching a stray lowercase "a:".
_INLINE_A = re.compile(r"(?:^|\s)(?:A|Ans|Answer)\s*[:.)\-]\s*(.+)$")


@dataclass
class QAPair:
    question: str
    q_norm: str
    answer: str


def parse_pairs(text: str) -> List[QAPair]:
    """Extract (question, answer) pairs from free reference text."""
    pairs: List[QAPair] = []
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    pending_q: Optional[str] = None

    def add(q: str, a: str):
        q, a = q.strip(), a.strip()
        if q and a:
            pairs.append(QAPair(q, N.normalize(q), a))

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        # "<question>?  A: <answer>" on one line (with or without a Q: marker).
        inline_all = _INLINE_A.search(line)
        if inline_all and "?" in line[:inline_all.start()]:
            q_part = line[:inline_all.start()]
            q_part = _Q_MARK.sub(r"\1", q_part)  # strip a leading "Q:" if present
            add(q_part, inline_all.group(1))
            pending_q = None
            continue

        mq = _Q_MARK.match(line)
        ma = _A_MARK.match(line)
        if mq:
            rest = mq.group(1).strip()
            inline = _INLINE_A.search(rest)
            if inline:  # "Q: question  A: answer" all on one line
                add(rest[:inline.start()], inline.group(1))
                pending_q = None
            else:
                pending_q = rest
            continue
        if ma and pending_q:
            add(pending_q, ma.group(1))
            pending_q = None
            continue
        # "line ending with ?" then the next non-empty line is its answer
        if line.endswith("?"):
            pending_q = line
            continue
        if pending_q:  # a plain line right after a question = its answer
            add(pending_q, line)
            pending_q = None
    return pairs


class ReferenceAnswerer:
    def __init__(self, reference_repo):
        self.reference_repo = reference_repo
        self.emb = EmbeddingManager.instance()
        self._vec_cache: dict = {}  # q_norm -> embedding (persists across calls)

    def _all_text(self) -> str:
        return "\n".join(ch.text for ch in self.reference_repo.all_chunks())

    def _vec(self, text: str):
        if text not in self._vec_cache:
            self._vec_cache[text] = self.emb.encode(text)
        return self._vec_cache[text]

    def best(self, q_norm: str) -> Tuple[Optional[QAPair], float, str]:
        """Return ``(pair, score, method)`` for the closest reference Q&A.

        ``method`` is "semantic" (score = cosine) when embeddings are ready, else
        "fuzzy" (score = 0..1 ratio). Semantic understands paraphrased survey
        wording; fuzzy is the fast fallback while the model loads.
        """
        pairs = parse_pairs(self._all_text())
        if not pairs:
            return None, 0.0, "none"

        if CONFIG.enable_semantic and self.emb.available():
            qv = self._vec(q_norm)
            if qv is not None:
                best_p, best_s = None, 0.0
                for p in pairs:
                    pv = self._vec(p.q_norm)
                    if pv is None:
                        continue
                    s = cosine(qv, pv)
                    if s > best_s:
                        best_s, best_p = s, p
                return best_p, best_s, "semantic"

        # fuzzy fallback (semantic model not available). token_set_ratio scores
        # ~1.0 when the query's words are a SUBSET of a longer reference question
        # (e.g. "how are you" vs "how are you currently managing your diabetes"),
        # which caused wrong matches. Penalise big length gaps so a short query
        # can't hijack a long unrelated question — those go to the AI instead.
        best_p, best_s = None, 0.0
        for p in pairs:
            r = F.ratio(q_norm, p.q_norm)
            ts = F.token_set_ratio(q_norm, p.q_norm)
            la = q_norm and p.q_norm
            len_ratio = (min(len(q_norm), len(p.q_norm))
                         / max(1, max(len(q_norm), len(p.q_norm)))) if la else 0.0
            s = max(r, ts * len_ratio)
            if s > best_s:
                best_s, best_p = s, p
        return best_p, best_s, "fuzzy"

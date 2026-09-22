"""Lightweight local vector search.

Uses FAISS when available for speed; otherwise a pure-python brute-force cosine
scan (fine for the thousands of Q&A rows a single user accumulates). No remote
service is involved.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .embedding_manager import EmbeddingManager, cosine

try:  # pragma: no cover
    import faiss  # type: ignore
    import numpy as np  # type: ignore

    _HAVE_FAISS = True
except Exception:  # noqa: BLE001
    _HAVE_FAISS = False


class VectorStore:
    """Holds ``(id, vector)`` pairs and returns nearest neighbours."""

    def __init__(self) -> None:
        self._ids: List[int] = []
        self._vecs: List[List[float]] = []
        self._index = None  # faiss index when available

    def add(self, item_id: int, vec: List[float]) -> None:
        self._ids.append(item_id)
        self._vecs.append(vec)
        self._index = None  # invalidate

    def add_blob(self, item_id: int, blob: Optional[bytes]) -> None:
        if blob:
            self.add(item_id, EmbeddingManager.from_bytes(blob))

    def build(self) -> None:
        if _HAVE_FAISS and self._vecs:
            dim = len(self._vecs[0])
            idx = faiss.IndexFlatIP(dim)  # vectors are L2-normalized -> IP=cos
            idx.add(np.array(self._vecs, dtype="float32"))
            self._index = idx

    def search(self, query: List[float], k: int
               ) -> List[Tuple[int, float]]:
        if not self._ids or not query:
            return []
        if _HAVE_FAISS:
            if self._index is None:
                self.build()
            q = np.array([query], dtype="float32")
            scores, idxs = self._index.search(q, min(k, len(self._ids)))
            return [(self._ids[i], float(s))
                    for s, i in zip(scores[0], idxs[0]) if i >= 0]
        # pure python
        scored = [(self._ids[i], cosine(query, v))
                  for i, v in enumerate(self._vecs)]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._ids)

"""Local sentence embeddings (lazy, optional).

Uses sentence-transformers when installed; the model is downloaded once and
cached under the app cache dir. If the library is unavailable the whole semantic
layer degrades gracefully (``available()`` returns False) and the pipeline falls
back to exact/fuzzy matching only — no remote embedding API is ever used.
"""
from __future__ import annotations

import array
import math
import threading
from typing import List, Optional

from ..utils.config import CONFIG
from ..utils.logging import get_logger
from ..utils.paths import models_dir

log = get_logger("embeddings")


class EmbeddingManager:
    _instance: Optional["EmbeddingManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._model = None
        self._tried = False
        self._model_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "EmbeddingManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # -- lazy model load --------------------------------------------------
    def _ensure_model(self):
        if self._model is not None or self._tried and self._model is None:
            return self._model
        with self._model_lock:
            if self._tried:
                return self._model
            self._tried = True
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                log.info("Loading embedding model %s (first run may download)",
                         CONFIG.retrieval.embedding_model)
                self._model = SentenceTransformer(
                    CONFIG.retrieval.embedding_model,
                    cache_folder=str(models_dir()))
            except Exception as exc:  # noqa: BLE001
                log.warning("Embeddings unavailable (%s); semantic search off",
                            exc)
                self._model = None
            return self._model

    def available(self) -> bool:
        return self._ensure_model() is not None

    def encode(self, text: str) -> Optional[List[float]]:
        model = self._ensure_model()
        if model is None:
            return None
        vec = model.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in vec]

    # -- (de)serialization ------------------------------------------------
    @staticmethod
    def to_bytes(vec: List[float]) -> bytes:
        return array.array("f", vec).tobytes()

    @staticmethod
    def from_bytes(blob: bytes) -> List[float]:
        a = array.array("f")
        a.frombytes(blob)
        return list(a)


def cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity for equal-length vectors (pure python; no numpy)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

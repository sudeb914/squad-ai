"""Semantic memory & reference retrieval using local embeddings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .embedding_manager import EmbeddingManager
from .vector_store import VectorStore
from ..database.repositories.memory_repo import MemoryRecord, MemoryRepo
from ..database.repositories.reference_repo import ReferenceRepo
from ..utils.config import CONFIG


@dataclass
class SemanticHit:
    record: MemoryRecord
    similarity: float


class SemanticMatcher:
    """Encapsulates embedding-backed retrieval. Safe when embeddings are off."""

    def __init__(self, memory_repo: MemoryRepo, reference_repo: ReferenceRepo):
        self.memory_repo = memory_repo
        self.reference_repo = reference_repo
        self.emb = EmbeddingManager.instance()

    @property
    def available(self) -> bool:
        return CONFIG.enable_semantic and self.emb.available()

    def ensure_embedding_for(self, rec: MemoryRecord) -> Optional[bytes]:
        """Compute & persist a memory row's embedding lazily."""
        if not self.available or rec.id is None:
            return rec.embedding
        if rec.embedding:
            return rec.embedding
        vec = self.emb.encode(rec.question_normalized)
        if vec is None:
            return None
        blob = self.emb.to_bytes(vec)
        self.memory_repo.set_embedding(rec.id, blob)
        return blob

    def search_memory(self, question_norm: str, k: Optional[int] = None
                      ) -> List[SemanticHit]:
        if not self.available or not question_norm:
            return []
        qvec = self.emb.encode(question_norm)
        if qvec is None:
            return []
        store = VectorStore()
        records = {}
        for rec in self.memory_repo.all():
            blob = self.ensure_embedding_for(rec)
            if blob and rec.id is not None:
                store.add_blob(rec.id, blob)
                records[rec.id] = rec
        if not len(store):
            return []
        k = k or CONFIG.retrieval.top_k_memory
        hits = store.search(qvec, k)
        return [SemanticHit(records[i], s) for i, s in hits if i in records]

    def search_reference(self, question_norm: str, k: Optional[int] = None
                         ) -> List[str]:
        """Return the most relevant reference chunks (text only)."""
        if not self.available or not question_norm:
            return []
        qvec = self.emb.encode(question_norm)
        if qvec is None:
            return []
        store = VectorStore()
        texts = {}
        for ch in self.reference_repo.all_chunks():
            if not ch.embedding:
                vec = self.emb.encode(ch.normalized)
                if vec is None:
                    continue
                blob = self.emb.to_bytes(vec)
                self.reference_repo.set_chunk_embedding(ch.id, blob)
                store.add_blob(ch.id, blob)
            else:
                store.add_blob(ch.id, ch.embedding)
            texts[ch.id] = ch.text
        if not len(store):
            return []
        k = k or CONFIG.retrieval.top_k_reference
        return [texts[i] for i, _ in store.search(qvec, k) if i in texts]

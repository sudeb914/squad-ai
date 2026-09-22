"""Reference / training documents, chunked for retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..db import Database
from ...core import normalization as N
from ...utils.config import CONFIG


@dataclass
class Chunk:
    id: int
    document_id: int
    chunk_index: int
    text: str
    normalized: str
    embedding: Optional[bytes]


def chunk_text(text: str, size: int, overlap: int) -> List[str]:
    """Split ``text`` into ~``size``-char chunks preferring paragraph breaks."""
    text = text.strip()
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= size:
                buf = p
            else:  # hard-split a very long paragraph
                for i in range(0, len(p), size - overlap):
                    chunks.append(p[i:i + size])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


class ReferenceRepo:
    def __init__(self, db: Database):
        self.db = db

    def add_document(self, content: str, title: str = "",
                     kind: str = "reference") -> int:
        cur = self.db.execute(
            "INSERT INTO reference_documents(title, content, kind) "
            "VALUES(?,?,?)", (title, content, kind))
        doc_id = int(cur.lastrowid)
        rc = CONFIG.retrieval
        for i, ch in enumerate(chunk_text(content, rc.reference_chunk_chars,
                                          rc.reference_chunk_overlap)):
            self.db.execute(
                "INSERT INTO reference_chunks(document_id, chunk_index, text, "
                "normalized) VALUES(?,?,?,?)",
                (doc_id, i, ch, N.normalize(ch)))
        return doc_id

    def all_chunks(self) -> List[Chunk]:
        return [Chunk(r["id"], r["document_id"], r["chunk_index"], r["text"],
                      r["normalized"], r["embedding"])
                for r in self.db.query("SELECT * FROM reference_chunks")]

    def set_chunk_embedding(self, chunk_id: int, blob: bytes) -> None:
        self.db.execute("UPDATE reference_chunks SET embedding=? WHERE id=?",
                        (blob, chunk_id))

    def documents(self):
        return self.db.query(
            "SELECT id, title, kind, created_at FROM reference_documents "
            "ORDER BY id DESC")

    def delete_document(self, doc_id: int) -> None:
        self.db.execute("DELETE FROM reference_documents WHERE id=?", (doc_id,))

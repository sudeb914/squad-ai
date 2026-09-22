"""Answer memory persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from ..db import Database


@dataclass
class MemoryRecord:
    id: Optional[int]
    question_original: str
    question_normalized: str
    answer: str
    options: List[str]
    selected_option: Optional[str]
    selected_option_index: Optional[int]
    source: str
    category: Optional[str]
    confidence: float
    relevant_fields: dict
    embedding: Optional[bytes]
    created_at: Optional[str] = None


class MemoryRepo:
    def __init__(self, db: Database):
        self.db = db

    def add(self, rec: MemoryRecord) -> int:
        cur = self.db.execute(
            """INSERT INTO answer_memory(
                question_original, question_normalized, answer, options_json,
                selected_option, selected_option_index, source, category,
                confidence, relevant_fields_json, embedding)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (rec.question_original, rec.question_normalized, rec.answer,
             json.dumps(rec.options), rec.selected_option,
             rec.selected_option_index, rec.source, rec.category,
             rec.confidence, json.dumps(rec.relevant_fields), rec.embedding),
        )
        return int(cur.lastrowid)

    def find_exact(self, question_normalized: str) -> Optional[MemoryRecord]:
        row = self.db.query_one(
            "SELECT * FROM answer_memory WHERE question_normalized=? "
            "ORDER BY confidence DESC, id DESC LIMIT 1",
            (question_normalized,))
        return self._row(row) if row else None

    def all(self) -> List[MemoryRecord]:
        return [self._row(r) for r in
                self.db.query("SELECT * FROM answer_memory ORDER BY id DESC")]

    def count(self) -> int:
        return int(self.db.query_one(
            "SELECT COUNT(*) c FROM answer_memory")["c"])

    def set_embedding(self, memory_id: int, blob: bytes) -> None:
        self.db.execute("UPDATE answer_memory SET embedding=? WHERE id=?",
                        (blob, memory_id))

    def clear(self) -> None:
        self.db.execute("DELETE FROM answer_memory")

    @staticmethod
    def _row(r) -> MemoryRecord:
        return MemoryRecord(
            id=r["id"],
            question_original=r["question_original"],
            question_normalized=r["question_normalized"],
            answer=r["answer"],
            options=json.loads(r["options_json"]) if r["options_json"] else [],
            selected_option=r["selected_option"],
            selected_option_index=r["selected_option_index"],
            source=r["source"],
            category=r["category"],
            confidence=r["confidence"],
            relevant_fields=(json.loads(r["relevant_fields_json"])
                             if r["relevant_fields_json"] else {}),
            embedding=r["embedding"],
            created_at=r["created_at"],
        )

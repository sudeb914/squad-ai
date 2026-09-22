"""Profile fields: arbitrary user-defined key/value/type triples.

The spec requires arbitrary custom fields, so we do NOT hardcode a fixed schema
of columns; every field is a row. ``value_type`` in {text, number, boolean,
date, longtext}.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..db import Database

VALID_TYPES = {"text", "number", "boolean", "date", "longtext"}


@dataclass
class ProfileField:
    key: str
    value: str
    value_type: str = "text"
    id: Optional[int] = None


class ProfileRepo:
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, key: str, value: str, value_type: str = "text") -> None:
        key = key.strip()
        if value_type not in VALID_TYPES:
            value_type = "text"
        self.db.execute(
            "INSERT INTO profile_fields(key, value, value_type) "
            "VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value, value_type=excluded.value_type, "
            "updated_at=datetime('now')",
            (key, str(value), value_type),
        )

    def delete(self, key: str) -> None:
        self.db.execute("DELETE FROM profile_fields WHERE key=?", (key,))

    def get(self, key: str) -> Optional[ProfileField]:
        row = self.db.query_one(
            "SELECT * FROM profile_fields WHERE key=? COLLATE NOCASE", (key,))
        return self._row(row) if row else None

    def all(self) -> List[ProfileField]:
        return [self._row(r) for r in
                self.db.query("SELECT * FROM profile_fields ORDER BY key")]

    def as_dict(self) -> dict:
        return {f.key: f.value for f in self.all()}

    @staticmethod
    def _row(r) -> ProfileField:
        return ProfileField(id=r["id"], key=r["key"], value=r["value"],
                            value_type=r["value_type"])

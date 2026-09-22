"""Persisted screenshot capture regions (for Lock Area)."""
from __future__ import annotations

from typing import Optional

from ..db import Database


class CaptureRepo:
    def __init__(self, db: Database):
        self.db = db

    def save_locked(self, x: int, y: int, w: int, h: int,
                    name: str = "locked") -> int:
        self.db.execute("UPDATE capture_regions SET locked=0")
        cur = self.db.execute(
            "INSERT INTO capture_regions(name, x, y, w, h, locked) "
            "VALUES(?,?,?,?,?,1)", (name, x, y, w, h))
        return int(cur.lastrowid)

    def locked_region(self) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM capture_regions WHERE locked=1 "
            "ORDER BY id DESC LIMIT 1")
        if not row:
            return None
        return {"x": row["x"], "y": row["y"], "w": row["w"], "h": row["h"]}

    def clear_lock(self) -> None:
        self.db.execute("UPDATE capture_regions SET locked=0")

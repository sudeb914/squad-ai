"""Key/value application settings (non-secret)."""
from __future__ import annotations

import json
from typing import Any, Optional

from ..db import Database


class SettingsRepo:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: Any = None) -> Any:
        row = self.db.query_one("SELECT value FROM settings WHERE key=?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    def set(self, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )

    def all(self) -> dict:
        return {r["key"]: self.get(r["key"])
                for r in self.db.query("SELECT key FROM settings")}

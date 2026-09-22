"""Persistent chat sessions and messages."""
from __future__ import annotations

import json
from typing import List, Optional

from ..db import Database


class ChatRepo:
    def __init__(self, db: Database):
        self.db = db

    def create_session(self, title: str = "New Chat") -> int:
        cur = self.db.execute(
            "INSERT INTO chat_sessions(title) VALUES(?)", (title,))
        return int(cur.lastrowid)

    def latest_session(self) -> Optional[int]:
        row = self.db.query_one(
            "SELECT id FROM chat_sessions ORDER BY id DESC LIMIT 1")
        return row["id"] if row else None

    def ensure_session(self) -> int:
        return self.latest_session() or self.create_session()

    def add_message(self, session_id: int, role: str, content: str,
                    source: Optional[str] = None, meta: Optional[dict] = None
                    ) -> int:
        cur = self.db.execute(
            "INSERT INTO chat_messages(session_id, role, content, source, "
            "meta_json) VALUES(?,?,?,?,?)",
            (session_id, role, content, source,
             json.dumps(meta) if meta else None))
        return int(cur.lastrowid)

    def messages(self, session_id: int) -> List[dict]:
        rows = self.db.query(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY id",
            (session_id,))
        return [{"id": r["id"], "role": r["role"], "content": r["content"],
                 "source": r["source"],
                 "meta": json.loads(r["meta_json"]) if r["meta_json"] else {},
                 "created_at": r["created_at"]} for r in rows]

    def sessions(self) -> List[dict]:
        return [{"id": r["id"], "title": r["title"],
                 "created_at": r["created_at"]}
                for r in self.db.query(
                    "SELECT * FROM chat_sessions ORDER BY id DESC")]

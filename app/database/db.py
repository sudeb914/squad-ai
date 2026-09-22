"""SQLite connection wrapper + schema migrations.

One connection per process, ``check_same_thread=False`` so worker threads can
use it (writes are serialised by SQLite; we keep operations short). WAL mode is
enabled for better concurrency.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Optional

from ..utils.logging import get_logger
from ..utils.paths import database_path
from . import migrations

log = get_logger("db")


class Database:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            self.conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            pass
        migrations.migrate(self.conn)
        log.info("Database ready at %s (schema v%d)",
                 self.path, migrations.current_version(self.conn))

    # -- low level helpers ------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, tuple(params))
            self.conn.commit()
            return cur

    def executemany(self, sql: str, seq: Iterable[Iterable[Any]]) -> None:
        with self._lock:
            self.conn.executemany(sql, [tuple(p) for p in seq])
            self.conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.conn.execute(sql, tuple(params)).fetchall())

    def query_one(self, sql: str, params: Iterable[Any] = ()
                  ) -> Optional[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, tuple(params)).fetchone()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

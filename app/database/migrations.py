"""Versioned schema migrations.

Each entry in ``MIGRATIONS`` is a list of SQL statements applied in order once.
``schema_version`` (PRAGMA user_version) tracks the applied version so upgrades
are idempotent and forward-only.
"""
from __future__ import annotations

import sqlite3
from typing import List

# Migration N is applied when user_version < N. Append; never edit shipped ones.
MIGRATIONS: List[List[str]] = [
    # --- v1: initial schema ------------------------------------------------
    [
        """CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS profile_fields (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT NOT NULL UNIQUE,
            value      TEXT,
            value_type TEXT NOT NULL DEFAULT 'text',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS reference_documents (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            content    TEXT NOT NULL,
            kind       TEXT NOT NULL DEFAULT 'reference',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS reference_chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES reference_documents(id)
                        ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            text        TEXT NOT NULL,
            normalized  TEXT NOT NULL,
            embedding   BLOB
        )""",
        """CREATE INDEX IF NOT EXISTS idx_chunks_doc
            ON reference_chunks(document_id)""",
        """CREATE TABLE IF NOT EXISTS answer_memory (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            question_original     TEXT NOT NULL,
            question_normalized   TEXT NOT NULL,
            answer                TEXT NOT NULL,
            options_json          TEXT,
            selected_option       TEXT,
            selected_option_index INTEGER,
            source                TEXT NOT NULL,
            category              TEXT,
            confidence            REAL NOT NULL DEFAULT 0,
            relevant_fields_json  TEXT,
            embedding             BLOB,
            created_at            TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE INDEX IF NOT EXISTS idx_memory_norm
            ON answer_memory(question_normalized)""",
        """CREATE TABLE IF NOT EXISTS chat_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS chat_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES chat_sessions(id)
                       ON DELETE CASCADE,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            source     TEXT,
            meta_json  TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE INDEX IF NOT EXISTS idx_messages_session
            ON chat_messages(session_id)""",
        """CREATE TABLE IF NOT EXISTS api_usage (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp          TEXT NOT NULL DEFAULT (datetime('now')),
            provider           TEXT NOT NULL,
            model              TEXT NOT NULL,
            input_tokens       INTEGER NOT NULL DEFAULT 0,
            output_tokens      INTEGER NOT NULL DEFAULT 0,
            cached_tokens      INTEGER NOT NULL DEFAULT 0,
            estimated_cost_usd REAL NOT NULL DEFAULT 0,
            latency_ms         INTEGER NOT NULL DEFAULT 0,
            success            INTEGER NOT NULL DEFAULT 1,
            error              TEXT
        )""",
        """CREATE INDEX IF NOT EXISTS idx_usage_ts ON api_usage(timestamp)""",
        """CREATE TABLE IF NOT EXISTS capture_regions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT,
            x          INTEGER NOT NULL,
            y          INTEGER NOT NULL,
            w          INTEGER NOT NULL,
            h          INTEGER NOT NULL,
            locked     INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
    ],
]


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> None:
    version = current_version(conn)
    for i, statements in enumerate(MIGRATIONS, start=1):
        if version < i:
            for stmt in statements:
                conn.execute(stmt)
            conn.execute(f"PRAGMA user_version = {i}")
            conn.commit()

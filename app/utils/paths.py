"""OS-appropriate application data locations.

User data must survive application updates and *display-name* changes, so we key
storage off a stable internal identifier (APP_ID) rather than the visible product
name. Code, user-data, cache and logs are kept in separate trees.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Stable internal identifier. Changing the *display* name (see APP_DISPLAY_NAME)
# must NOT move the database, so this value must never change once shipped.
APP_ID = "com.squadai.desktop"
APP_DISPLAY_NAME = "Squad AI"


def _base_dir(kind: str) -> Path:
    """Return the platform base directory for ``kind`` in {data, cache, logs}.

    Honours ``SQUAD_AI_HOME`` for tests / portable installs.
    """
    override = os.environ.get("SQUAD_AI_HOME")
    if override:
        return Path(override) / kind

    home = Path.home()
    if sys.platform == "darwin":
        if kind == "cache":
            return home / "Library" / "Caches" / APP_ID
        if kind == "logs":
            return home / "Library" / "Logs" / APP_ID
        return home / "Library" / "Application Support" / APP_ID
    if sys.platform.startswith("win"):
        root = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        if kind == "cache":
            return local / APP_ID / "Cache"
        if kind == "logs":
            return local / APP_ID / "Logs"
        return root / APP_ID
    # Linux / other: XDG
    if kind == "cache":
        root = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    elif kind == "logs":
        root = Path(os.environ.get("XDG_STATE_HOME", home / ".local" / "state"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return root / APP_ID


def data_dir() -> Path:
    return _ensure(_base_dir("data"))


def cache_dir() -> Path:
    return _ensure(_base_dir("cache"))


def logs_dir() -> Path:
    return _ensure(_base_dir("logs"))


def models_dir() -> Path:
    """Downloaded ML models (embeddings, OCR) live in the cache tree."""
    return _ensure(cache_dir() / "models")


def database_path() -> Path:
    return data_dir() / "squad_ai.sqlite3"


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

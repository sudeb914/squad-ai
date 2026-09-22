"""Structured local logging with normal / debug levels.

Never logs API keys: :func:`redact` scrubs anything that looks like a secret.
"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from .paths import logs_dir

_CONFIGURED = False

# Patterns that must never reach a log file.
_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9]{6,}|Bearer\s+[A-Za-z0-9._-]{6,})")


def redact(text: str) -> str:
    """Mask anything resembling an API key / bearer token."""
    if not text:
        return text
    return _SECRET_RE.sub("***REDACTED***", str(text))


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    root = logging.getLogger("squad_ai")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if _CONFIGURED:
        return

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"
    )
    redactor = _RedactingFilter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(redactor)
    root.addHandler(console)

    try:
        fileh = RotatingFileHandler(
            logs_dir() / "squad_ai.log", maxBytes=1_000_000, backupCount=3,
            encoding="utf-8",
        )
        fileh.setFormatter(fmt)
        fileh.addFilter(redactor)
        root.addHandler(fileh)
    except OSError:
        # Never fail startup because logs can't be written.
        pass

    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"squad_ai.{name}")

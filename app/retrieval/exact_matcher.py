"""Exact (normalized) memory lookup."""
from __future__ import annotations

from typing import Optional

from ..database.repositories.memory_repo import MemoryRecord, MemoryRepo


class ExactMatcher:
    def __init__(self, repo: MemoryRepo):
        self.repo = repo

    def find(self, question_normalized: str) -> Optional[MemoryRecord]:
        if not question_normalized:
            return None
        return self.repo.find_exact(question_normalized)

"""Region data type + platform-agnostic helpers for screenshot capture."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int

    def valid(self) -> bool:
        return self.w > 0 and self.h > 0

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

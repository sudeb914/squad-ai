"""Import / export of answer memory.

Export: native Squad AI JSON (round-trippable). Import: tolerant of native JSON,
simple ``[{question, answer}]`` JSON, and CSV with recognizable columns. Never
corrupts existing memory: invalid rows are skipped and reported, valid rows are
added.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import List

from ..core import normalization as N
from ..database.repositories.memory_repo import MemoryRecord, MemoryRepo

_Q_KEYS = ("question", "q", "prompt", "question_original")
_A_KEYS = ("answer", "a", "response", "selected_option")


@dataclass
class ImportReport:
    added: int = 0
    skipped: int = 0
    errors: List[str] = None  # type: ignore

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class MemoryPorter:
    def __init__(self, repo: MemoryRepo):
        self.repo = repo

    # -- export -----------------------------------------------------------
    def export_json(self) -> str:
        rows = []
        for r in self.repo.all():
            rows.append({
                "question": r.question_original,
                "question_normalized": r.question_normalized,
                "answer": r.answer,
                "options": r.options,
                "selected_option": r.selected_option,
                "selected_option_index": r.selected_option_index,
                "source": r.source,
                "category": r.category,
                "confidence": r.confidence,
                "created_at": r.created_at,
            })
        return json.dumps({"version": 1, "app": "squad_ai",
                           "memory": rows}, indent=2)

    # -- import -----------------------------------------------------------
    def import_text(self, text: str, fmt: str = "auto") -> ImportReport:
        text = text.strip()
        if not text:
            return ImportReport(errors=["empty input"])
        if fmt == "csv" or (fmt == "auto" and not text.startswith(("{", "["))):
            return self._import_csv(text)
        return self._import_json(text)

    def _import_json(self, text: str) -> ImportReport:
        rep = ImportReport()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return ImportReport(errors=[f"invalid JSON: {exc}"])
        rows = data["memory"] if isinstance(data, dict) and "memory" in data \
            else data
        if not isinstance(rows, list):
            return ImportReport(errors=["JSON must be a list or {memory: []}"])
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                rep.skipped += 1
                rep.errors.append(f"row {i}: not an object")
                continue
            q = _first(row, _Q_KEYS)
            a = _first(row, _A_KEYS)
            if not q or not a:
                rep.skipped += 1
                rep.errors.append(f"row {i}: missing question/answer")
                continue
            self._add(q, a, row)
            rep.added += 1
        return rep

    def _import_csv(self, text: str) -> ImportReport:
        rep = ImportReport()
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return ImportReport(errors=["CSV has no header row"])
        lower = {f.lower(): f for f in reader.fieldnames}
        qcol = next((lower[k] for k in _Q_KEYS if k in lower), None)
        acol = next((lower[k] for k in _A_KEYS if k in lower), None)
        if not qcol or not acol:
            return ImportReport(errors=[
                "CSV needs recognizable question/answer columns"])
        for i, row in enumerate(reader):
            q, a = (row.get(qcol) or "").strip(), (row.get(acol) or "").strip()
            if not q or not a:
                rep.skipped += 1
                continue
            self._add(q, a, row)
            rep.added += 1
        return rep

    def _add(self, question: str, answer: str, row: dict) -> None:
        self.repo.add(MemoryRecord(
            id=None,
            question_original=question,
            question_normalized=N.normalize(question),
            answer=answer,
            options=row.get("options") if isinstance(row.get("options"), list)
            else [],
            selected_option=row.get("selected_option"),
            selected_option_index=row.get("selected_option_index"),
            source=row.get("source") or "IMPORTED",
            category=row.get("category"),
            confidence=float(row.get("confidence", 0.7) or 0.7),
            relevant_fields={},
            embedding=None,
        ))


def _first(row: dict, keys) -> str:
    for k in keys:
        if row.get(k):
            return str(row[k]).strip()
    return ""

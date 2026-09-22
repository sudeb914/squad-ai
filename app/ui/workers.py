"""Qt worker threads so OCR / embeddings / network never block the GUI."""
from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..core.models import AnswerResult


class _Signals(QObject):
    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)


class AnswerWorker(QRunnable):
    """Runs a single AnswerEngine.answer() call off the GUI thread."""

    def __init__(self, engine, text: str,
                 options: Optional[List[str]] = None, allow_api: bool = True,
                 recent_context: str = ""):
        super().__init__()
        self.engine = engine
        self.text = text
        self.options = options
        self.allow_api = allow_api
        self.recent_context = recent_context
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            result: AnswerResult = self.engine.answer(
                self.text, explicit_options=self.options,
                allow_api=self.allow_api, recent_context=self.recent_context,
                progress=self.signals.progress.emit)
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))


class FnWorker(QRunnable):
    """Runs an arbitrary function off the GUI thread, emitting its result."""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.fn(*self.args, **self.kwargs))
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))

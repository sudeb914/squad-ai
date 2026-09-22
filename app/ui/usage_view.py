"""Usage page: API cost dashboard + local resolution rate."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget)

from ..core.models import AnswerSource
from ..services import Services


class UsageView(QWidget):
    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>API usage & cost</h2>"))

        self.grid = QGridLayout()
        layout.addLayout(self.grid)

        self.rate_box = QGroupBox("Local resolution rate")
        rl = QVBoxLayout(self.rate_box)
        self.rate_label = QLabel()
        rl.addWidget(self.rate_label)
        layout.addWidget(self.rate_box)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        layout.addWidget(refresh)
        layout.addStretch(1)
        self.reload()

    def reload(self) -> None:
        # clear grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dash = self.svc.usage.dashboard()
        cols = [("Today", dash["today"]), ("Last 7 days", dash["last_7_days"]),
                ("Total", dash["total"])]
        for c, (title, data) in enumerate(cols):
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            bl.addWidget(QLabel(f"API calls: <b>{data['calls']}</b>"))
            bl.addWidget(QLabel(f"Input tokens: {data['input_tokens']}"))
            bl.addWidget(QLabel(f"Output tokens: {data['output_tokens']}"))
            bl.addWidget(QLabel(f"Cache-hit tokens: {data['cached_tokens']}"))
            bl.addWidget(QLabel(f"Est. cost: <b>${data['cost']:.4f}</b>"))
            bl.addWidget(QLabel(f"Failures: {data['failures']}"))
            self.grid.addWidget(box, 0, c)

        self.rate_label.setText(self._resolution_text())

    def _resolution_text(self) -> str:
        rows = self.svc.memory_repo.all()
        total = self.svc.usage.summary()["calls"] + len(rows)
        if total == 0:
            return "No questions answered yet."
        api = self.svc.usage.summary()["calls"]
        local = len(rows)  # stored non-API + memory (approximation of learned)
        free = max(0, local)
        pct = 100.0 * free / max(1, (free + api))
        avg = (self.svc.usage.summary()["input_tokens"] / api) if api else 0
        return (f"Approx local/free answers: <b>{pct:.0f}%</b> "
                f"({free} local, {api} API calls). "
                f"Avg input tokens/API question: {avg:.0f}.")

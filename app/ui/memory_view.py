"""Memory page: browse stored Q&A, import/export, clear (with confirmation)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..services import Services


class MemoryView(QWidget):
    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Answer memory</h2>"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Question", "Answer", "Source", "Conf"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        exp = QPushButton("Export JSON")
        exp.clicked.connect(self._export)
        imp = QPushButton("Import…")
        imp.clicked.connect(self._import)
        clear = QPushButton("Clear memory")
        clear.clicked.connect(self._clear)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        for w in (exp, imp, clear, refresh):
            row.addWidget(w)
        row.addStretch(1)
        layout.addLayout(row)
        self.reload()

    def reload(self) -> None:
        rows = self.svc.memory_repo.all()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r.question_original))
            self.table.setItem(i, 1, QTableWidgetItem(r.answer))
            self.table.setItem(i, 2, QTableWidgetItem(r.source))
            self.table.setItem(i, 3, QTableWidgetItem(f"{r.confidence:.2f}"))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export memory", "squad_ai_memory.json", "JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.svc.porter.export_json())
        QMessageBox.information(self, "Exported", f"Saved to {path}")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import memory", "", "Data (*.json *.csv);;All files (*)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        fmt = "csv" if path.lower().endswith(".csv") else "auto"
        report = self.svc.porter.import_text(text, fmt)
        self.reload()
        msg = f"Added {report.added}, skipped {report.skipped}."
        if report.errors:
            msg += "\n\nIssues:\n" + "\n".join(report.errors[:10])
        QMessageBox.information(self, "Import complete", msg)

    def _clear(self) -> None:
        confirm = QMessageBox.question(
            self, "Clear memory",
            "This deletes all stored Q&A. Export first if unsure. Continue?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.svc.memory_repo.clear()
            self.reload()

"""Profile page: manage arbitrary fields + long-form profile/reference/prompt."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

from ..database.repositories.profile_repo import VALID_TYPES
from ..services import Services


class ProfileView(QWidget):
    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<h2>Profile fields</h2>"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Field", "Value", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        self.key_in = QLineEdit(placeholderText="field (e.g. age)")
        self.val_in = QLineEdit(placeholderText="value (e.g. 39)")
        self.type_in = QComboBox()
        self.type_in.addItems(sorted(VALID_TYPES))
        add = QPushButton("Add / Update")
        add.clicked.connect(self._add)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self._delete)
        for w in (self.key_in, self.val_in, self.type_in, add, delete):
            row.addWidget(w)
        layout.addLayout(row)

        layout.addWidget(QLabel("<h3>Reference / training information</h3>"))
        self.reference = QPlainTextEdit()
        self.reference.setPlaceholderText(
            "Paste long reference/training text; it is chunked & indexed "
            "locally and only relevant parts are ever sent to the AI.")
        layout.addWidget(self.reference)
        save_ref = QPushButton("Save reference document")
        save_ref.clicked.connect(self._save_reference)
        layout.addWidget(save_ref)

        layout.addWidget(QLabel("<h3>Custom instruction prompt</h3>"))
        self.custom = QPlainTextEdit()
        self.custom.setPlaceholderText("Extra instructions for the AI provider.")
        self.custom.setFixedHeight(80)
        save_custom = QPushButton("Save custom instructions")
        save_custom.clicked.connect(self._save_custom)
        layout.addWidget(self.custom)
        layout.addWidget(save_custom)

        self._load()

    def _load(self) -> None:
        fields = self.svc.profile.all()
        self.table.setRowCount(len(fields))
        for i, f in enumerate(fields):
            self.table.setItem(i, 0, QTableWidgetItem(f.key))
            self.table.setItem(i, 1, QTableWidgetItem(f.value))
            self.table.setItem(i, 2, QTableWidgetItem(f.value_type))
        self.custom.setPlainText(self.svc.settings.get("custom_prompt", "") or "")

    def _add(self) -> None:
        key = self.key_in.text().strip()
        if not key:
            return
        self.svc.profile.upsert(key, self.val_in.text().strip(),
                                self.type_in.currentText())
        self.key_in.clear()
        self.val_in.clear()
        self._load()

    def _delete(self) -> None:
        r = self.table.currentRow()
        if r < 0:
            return
        key = self.table.item(r, 0).text()
        self.svc.profile.delete(key)
        self._load()

    def _save_reference(self) -> None:
        text = self.reference.toPlainText().strip()
        if not text:
            return
        self.svc.reference.add_document(text, title="Reference")
        self.reference.clear()
        QMessageBox.information(self, "Saved",
                                "Reference indexed locally.")

    def _save_custom(self) -> None:
        self.svc.settings.set("custom_prompt", self.custom.toPlainText())
        QMessageBox.information(self, "Saved", "Custom instructions saved.")

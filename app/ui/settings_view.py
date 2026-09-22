"""Settings page: API key (secure), hotkey, mode, semantic toggle."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..services import Services
from ..utils.config import CONFIG


class SettingsView(QWidget):
    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Settings</h2>"))

        form = QFormLayout()
        layout.addLayout(form)

        # API key
        self.key_status = QLabel(self._key_status())
        form.addRow("DeepSeek key:", self.key_status)
        self.key_in = QLineEdit()
        self.key_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_in.setPlaceholderText("Paste API key (stored in OS keyring)")
        form.addRow("Set key:", self.key_in)

        key_row = QHBoxLayout()
        save = QPushButton("Save key")
        save.clicked.connect(self._save_key)
        test = QPushButton("Test connection")
        test.clicked.connect(self._test)
        delete = QPushButton("Delete key")
        delete.clicked.connect(self._delete_key)
        for w in (save, test, delete):
            key_row.addWidget(w)
        layout.addLayout(key_row)

        # hotkey / mode / semantic
        form2 = QFormLayout()
        layout.addLayout(form2)
        self.hotkey_in = QLineEdit(CONFIG.capture.hotkey)
        form2.addRow("Capture hotkey:", self.hotkey_in)
        self.mode_in = QComboBox()
        self.mode_in.addItems(["manual", "auto"])
        self.mode_in.setCurrentText(CONFIG.capture.mode)
        form2.addRow("Default mode:", self.mode_in)
        self.semantic_in = QCheckBox("Enable local semantic search")
        self.semantic_in.setChecked(CONFIG.enable_semantic)
        form2.addRow("", self.semantic_in)

        save_prefs = QPushButton("Save preferences")
        save_prefs.clicked.connect(self._save_prefs)
        layout.addWidget(save_prefs)
        layout.addStretch(1)

    def _key_status(self) -> str:
        key = self.svc.credentials.get_key(CONFIG.provider.name)
        return self.svc.credentials.masked(key)

    def _save_key(self) -> None:
        key = self.key_in.text().strip()
        if not key:
            return
        self.svc.credentials.set_key(CONFIG.provider.name, key)
        self.key_in.clear()
        self.key_status.setText(self._key_status())
        QMessageBox.information(self, "Saved", "API key stored securely.")

    def _delete_key(self) -> None:
        self.svc.credentials.delete_key(CONFIG.provider.name)
        self.key_status.setText(self._key_status())

    def _test(self) -> None:
        provider = self.svc.build_provider()
        if provider is None:
            QMessageBox.warning(self, "No key", "Configure an API key first.")
            return
        ok, msg = provider.test_connection()
        (QMessageBox.information if ok else QMessageBox.warning)(
            self, "Connection", msg)

    def _save_prefs(self) -> None:
        CONFIG.capture.hotkey = self.hotkey_in.text().strip() or "F8"
        CONFIG.capture.mode = self.mode_in.currentText()
        CONFIG.enable_semantic = self.semantic_in.isChecked()
        self.svc.settings.set("hotkey", CONFIG.capture.hotkey)
        self.svc.settings.set("capture_mode", CONFIG.capture.mode)
        self.svc.settings.set("enable_semantic", CONFIG.enable_semantic)
        QMessageBox.information(self, "Saved",
                                "Preferences saved (restart to re-bind hotkey).")

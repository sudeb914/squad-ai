"""Settings page: AI provider (DeepSeek / AgentRouter), keys (secure), hotkey…

Each provider keeps its own key + config. Switching the active provider never
deletes the other's settings or any local data — it only changes which cloud
backend the answer engine falls back to.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..services import Services
from ..utils.config import CONFIG

_PROVIDER_LABELS = {"deepseek": "DeepSeek", "agentrouter": "AgentRouter"}


class SettingsView(QWidget):
    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc

        # Scroll so the (now longer) settings fit on small windows.
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        root = QWidget()
        scroll.setWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(QLabel("<h2>Settings</h2>"))

        # ---- active provider selector -----------------------------------
        prov_row = QFormLayout()
        layout.addLayout(prov_row)
        self.provider_in = QComboBox()
        for key, lbl in _PROVIDER_LABELS.items():
            self.provider_in.addItem(lbl, key)
        self._select_combo(self.provider_in, CONFIG.active_provider)
        self.provider_in.currentIndexChanged.connect(self._on_provider_changed)
        prov_row.addRow("AI Provider:", self.provider_in)
        self.active_lbl = QLabel(self._active_text())
        prov_row.addRow("", self.active_lbl)

        # ---- DeepSeek section -------------------------------------------
        layout.addWidget(self._build_deepseek_box())
        # ---- AgentRouter section ---------------------------------------
        layout.addWidget(self._build_agentrouter_box())

        # ---- general preferences ---------------------------------------
        prefs = QGroupBox("General")
        form2 = QFormLayout(prefs)
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
        form2.addRow("", save_prefs)
        layout.addWidget(prefs)

        layout.addStretch(1)

    # ================================================================
    # DeepSeek (unchanged behaviour)
    # ================================================================
    def _build_deepseek_box(self) -> QGroupBox:
        box = QGroupBox("DeepSeek")
        form = QFormLayout(box)
        self.key_status = QLabel(self._key_status("deepseek"))
        form.addRow("DeepSeek key:", self.key_status)
        self.key_in = QLineEdit()
        self.key_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_in.setPlaceholderText("Paste API key (stored in OS keyring)")
        form.addRow("Set key:", self.key_in)

        row = QHBoxLayout()
        save = QPushButton("Save key")
        save.clicked.connect(self._save_key)
        test = QPushButton("Test connection")
        test.clicked.connect(lambda: self._test("deepseek"))
        delete = QPushButton("Delete key")
        delete.clicked.connect(self._delete_key)
        for w in (save, test, delete):
            row.addWidget(w)
        form.addRow("", self._wrap(row))
        return box

    # ================================================================
    # AgentRouter
    # ================================================================
    def _build_agentrouter_box(self) -> QGroupBox:
        ar = CONFIG.agentrouter
        box = QGroupBox("AgentRouter")
        form = QFormLayout(box)

        self.ar_key_status = QLabel(self._key_status("agentrouter"))
        form.addRow("AgentRouter key:", self.ar_key_status)
        self.ar_key_in = QLineEdit()
        self.ar_key_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.ar_key_in.setPlaceholderText("Paste API key (stored in OS keyring)")
        form.addRow("Set key:", self.ar_key_in)

        self.ar_base_in = QLineEdit(ar.base_url)
        form.addRow("Base URL:", self.ar_base_in)
        self.ar_model_in = QLineEdit(ar.model)
        form.addRow("Model:", self.ar_model_in)
        self.ar_temp_in = QLineEdit(str(ar.temperature))
        form.addRow("Temperature:", self.ar_temp_in)
        self.ar_maxtok_in = QLineEdit(str(ar.max_output_tokens))
        form.addRow("Max output tokens:", self.ar_maxtok_in)

        # Optional pricing (USD / 1M tokens) — used only for cost ESTIMATES.
        self.ar_price_in = QLineEdit(str(ar.price_input_per_m))
        form.addRow("Price input /1M ($):", self.ar_price_in)
        self.ar_price_cached_in = QLineEdit(str(ar.price_input_cached_per_m))
        form.addRow("Price cached /1M ($):", self.ar_price_cached_in)
        self.ar_price_out_in = QLineEdit(str(ar.price_output_per_m))
        form.addRow("Price output /1M ($):", self.ar_price_out_in)
        form.addRow("", QLabel("<i>Pricing is only for cost estimates — "
                               "shown as “Est.”, never actual billing.</i>"))

        row = QHBoxLayout()
        save = QPushButton("Save AgentRouter settings")
        save.clicked.connect(self._save_agentrouter)
        test = QPushButton("Test connection")
        test.clicked.connect(lambda: self._test("agentrouter"))
        delete = QPushButton("Delete key")
        delete.clicked.connect(self._delete_ar_key)
        for w in (save, test, delete):
            row.addWidget(w)
        form.addRow("", self._wrap(row))
        return box

    # ================================================================
    # helpers
    # ================================================================
    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _select_combo(combo: QComboBox, data_value: str) -> None:
        idx = combo.findData(data_value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _active_text(self) -> str:
        name = CONFIG.active_provider
        lbl = _PROVIDER_LABELS.get(name, name)
        return f"Active: <b>{lbl}</b> — this provider handles the AI fallback."

    def _key_status(self, provider: str) -> str:
        key = self.svc.credentials.get_key(provider)
        return self.svc.credentials.masked(key)

    # -- provider switching ----------------------------------------------
    def _on_provider_changed(self) -> None:
        name = self.provider_in.currentData()
        CONFIG.active_provider = name
        self.svc.settings.set("active_provider", name)
        self.active_lbl.setText(self._active_text())

    # -- DeepSeek key ----------------------------------------------------
    def _save_key(self) -> None:
        key = self.key_in.text().strip()
        if not key:
            return
        self.svc.credentials.set_key("deepseek", key)
        self.key_in.clear()
        self.key_status.setText(self._key_status("deepseek"))
        QMessageBox.information(self, "Saved", "DeepSeek key stored securely.")

    def _delete_key(self) -> None:
        self.svc.credentials.delete_key("deepseek")
        self.key_status.setText(self._key_status("deepseek"))

    # -- AgentRouter key + config ----------------------------------------
    def _delete_ar_key(self) -> None:
        self.svc.credentials.delete_key("agentrouter")
        self.ar_key_status.setText(self._key_status("agentrouter"))

    def _collect_agentrouter_into_config(self) -> None:
        """Apply the current AgentRouter fields into CONFIG (no key here)."""
        ar = CONFIG.agentrouter
        ar.base_url = self.ar_base_in.text().strip() or ar.base_url
        ar.model = self.ar_model_in.text().strip() or ar.model
        ar.temperature = _f(self.ar_temp_in.text(), ar.temperature)
        ar.max_output_tokens = _i(self.ar_maxtok_in.text(), ar.max_output_tokens)
        ar.price_input_per_m = _f(self.ar_price_in.text(), ar.price_input_per_m)
        ar.price_input_cached_per_m = _f(
            self.ar_price_cached_in.text(), ar.price_input_cached_per_m)
        ar.price_output_per_m = _f(
            self.ar_price_out_in.text(), ar.price_output_per_m)

    def _save_agentrouter(self) -> None:
        # key (only if a new one was typed)
        key = self.ar_key_in.text().strip()
        if key:
            self.svc.credentials.set_key("agentrouter", key)
            self.ar_key_in.clear()
            self.ar_key_status.setText(self._key_status("agentrouter"))
        # config
        self._collect_agentrouter_into_config()
        ar = CONFIG.agentrouter
        s = self.svc.settings
        s.set("agentrouter_base_url", ar.base_url)
        s.set("agentrouter_model", ar.model)
        s.set("agentrouter_temperature", ar.temperature)
        s.set("agentrouter_max_tokens", ar.max_output_tokens)
        s.set("agentrouter_price_input", ar.price_input_per_m)
        s.set("agentrouter_price_cached", ar.price_input_cached_per_m)
        s.set("agentrouter_price_output", ar.price_output_per_m)
        QMessageBox.information(self, "Saved",
                                "AgentRouter settings saved securely.")

    # -- connection test (either provider) -------------------------------
    def _test(self, provider: str) -> None:
        if provider == "agentrouter":
            # Use the values currently in the fields (even if unsaved) so the
            # test reflects what the user is about to save.
            self._collect_agentrouter_into_config()
            typed = self.ar_key_in.text().strip()
            if typed:
                from ..providers.agentrouter_provider import AgentRouterProvider
                prov = AgentRouterProvider(typed)
            else:
                prov = self.svc.build_named_provider("agentrouter")
        else:
            prov = self.svc.build_named_provider("deepseek")

        if prov is None:
            QMessageBox.warning(self, "No key",
                                "Configure an API key for this provider first.")
            return
        ok, msg = prov.test_connection()
        title = "✓ Connected" if ok else "Connection failed"
        (QMessageBox.information if ok else QMessageBox.warning)(
            self, title, msg)

    # -- general prefs ---------------------------------------------------
    def _save_prefs(self) -> None:
        CONFIG.capture.hotkey = self.hotkey_in.text().strip() or "F8"
        CONFIG.capture.mode = self.mode_in.currentText()
        CONFIG.enable_semantic = self.semantic_in.isChecked()
        self.svc.settings.set("hotkey", CONFIG.capture.hotkey)
        self.svc.settings.set("capture_mode", CONFIG.capture.mode)
        self.svc.settings.set("enable_semantic", CONFIG.enable_semantic)
        QMessageBox.information(self, "Saved",
                                "Preferences saved (restart to re-bind hotkey).")


def _f(text: str, default: float) -> float:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def _i(text: str, default: int) -> int:
    try:
        return int(float(str(text).strip()))
    except (TypeError, ValueError):
        return default

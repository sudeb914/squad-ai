"""First-run onboarding wizard.

Shown once (guarded by the ``onboarded`` setting). Lets the user seed a few
common profile fields and optionally add a DeepSeek key. Everything here is
optional — the app is fully usable locally without a key, and the user can skip
straight through.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QVBoxLayout)

from ..services import Services
from ..utils.config import CONFIG
from ..utils.paths import APP_DISPLAY_NAME

# Common starter fields; the user can add arbitrary custom ones later.
_STARTER_FIELDS = [
    ("age", "Age", "number"),
    ("gender", "Gender", "text"),
    ("state", "State / Region", "text"),
    ("country", "Country", "text"),
    ("employment_status", "Employment status", "text"),
    ("household_size", "Household size", "number"),
    ("income", "Annual income (number)", "number"),
]


class OnboardingDialog(QDialog):
    def __init__(self, svc: Services, parent=None):
        super().__init__(parent)
        self.svc = svc
        self.setWindowTitle(f"Welcome to {APP_DISPLAY_NAME}")
        self.setMinimumWidth(460)
        self._inputs: dict[str, tuple[QLineEdit, str]] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<h2>Welcome to {APP_DISPLAY_NAME}</h2>"
            "<p>Squad AI answers surveys <b>locally first</b>. Add a few facts "
            "so it can answer without spending API credits. Everything is "
            "optional — you can skip and fill this in later on the Profile "
            "page.</p>"))

        profile_box = QGroupBox("Your profile (optional)")
        form = QFormLayout(profile_box)
        for key, label, vtype in _STARTER_FIELDS:
            edit = QLineEdit()
            self._inputs[key] = (edit, vtype)
            form.addRow(label, edit)
        layout.addWidget(profile_box)

        key_box = QGroupBox("DeepSeek API key (optional)")
        kl = QFormLayout(key_box)
        self.key_in = QLineEdit()
        self.key_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_in.setPlaceholderText("Leave blank to use local features only")
        kl.addRow("API key:", self.key_in)
        kl.addRow("", QLabel("<i style='color:#888'>Stored securely in your OS "
                             "keyring. Local answers work without it.</i>"))
        layout.addWidget(key_box)

        buttons = QDialogButtonBox()
        skip = buttons.addButton("Skip for now",
                                 QDialogButtonBox.ButtonRole.RejectRole)
        finish = buttons.addButton("Finish",
                                   QDialogButtonBox.ButtonRole.AcceptRole)
        skip.clicked.connect(self._skip)
        finish.clicked.connect(self._finish)
        layout.addWidget(buttons)

    def _finish(self) -> None:
        for key, (edit, vtype) in self._inputs.items():
            val = edit.text().strip()
            if val:
                self.svc.profile.upsert(key, val, vtype)
        api_key = self.key_in.text().strip()
        if api_key:
            self.svc.credentials.set_key(CONFIG.provider.name, api_key)
        self.svc.settings.set("onboarded", True)
        self.accept()

    def _skip(self) -> None:
        self.svc.settings.set("onboarded", True)
        self.reject()


def needs_onboarding(svc: Services) -> bool:
    return not bool(svc.settings.get("onboarded", False))

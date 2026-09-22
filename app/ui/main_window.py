"""Single-window chat UI — same simple layout as the app the user liked.

Top bar (⚙ / brand / 🗑 / ?), a chat thread, and a composer with upload /
screenshot / send plus Auto and Lock-area chips. Settings and Help are overlay
pages, not separate nav destinations. Underneath sits the local-first
AnswerEngine, so the look is familiar but API cost stays low.
"""
from __future__ import annotations

import html as _html
import re
import sys
import time
from typing import List, Optional

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget)

from ..capture.hotkey_manager import HotkeyManager
from ..capture.region_selector import Region
from ..capture.screenshot_manager import ScreenshotError, ScreenshotManager
from ..core import normalization as _N
from ..core import question_parser as _QP
from ..core.models import AnswerResult, AnswerSource
from ..core.question_splitter import split_questions
from ..ocr.ocr_manager import OcrManager
from ..services import Services
from ..utils.config import CONFIG
from ..utils.paths import cache_dir
from .screenshot_overlay import ScreenshotOverlay
from .theme import COLORS, QSS
from .workers import AnswerWorker, FnWorker


def _to_float(text: str, default: float) -> float:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def _to_int(text: str, default: int) -> int:
    try:
        return int(float(str(text).strip()))
    except (TypeError, ValueError):
        return default


def _answer_html(text: str) -> str:
    """Render answer text: bullet/numbered/checked lines get a green ✓."""
    out = []
    for raw in str(text).split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(?:✅|✓|\d+[.)]|[-•])\s*(.*)$", line)
        if m:
            out.append(
                f"<div style='margin:5px 0'><span style='color:{COLORS['success']};"
                f"font-weight:900'>✓</span>&nbsp;{_html.escape(m.group(1))}</div>")
        else:
            out.append(f"<div style='margin:5px 0'>{_html.escape(line)}</div>")
    return "".join(out) or _html.escape(text)


def _source_meta(source: AnswerSource) -> str:
    if source in (AnswerSource.LOCAL_FACT, AnswerSource.LOCAL_RULE):
        t, c = "📁 From your data · free (no AI)", COLORS["success"]
    elif source in (AnswerSource.EXACT_MEMORY, AnswerSource.FUZZY_MEMORY,
                    AnswerSource.SEMANTIC_MEMORY):
        t, c = "💾 Local memory · free (no AI)", COLORS["success"]
    elif source is AnswerSource.DEEPSEEK:
        label = "AgentRouter" if CONFIG.active_provider == "agentrouter" \
            else "DeepSeek"
        t, c = f"🤖 {label} AI (API call)", "#fbbf24"
    else:
        return ""
    return (f"<div style='margin-top:7px;border-top:1px dashed {COLORS['border']};"
            f"padding-top:6px'><span style='color:{c};font-weight:700;"
            f"font-size:11px'>{t}</span></div>")


class MainWindow(QWidget):
    _hotkey_fired = Signal()

    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc
        self.pool = QThreadPool.globalInstance()
        self.ocr = OcrManager()
        self.shots = ScreenshotManager()
        self.session_id = svc.chat.ensure_session()
        self._staged: List[str] = []
        self._busy = False
        self._overlay: Optional[ScreenshotOverlay] = None
        # Keep strong refs to running workers so Python doesn't GC a QRunnable
        # (or its signals object) mid-flight — that caused a segfault after OCR.
        self._live_workers: set = set()

        self.setWindowTitle("Squad AI")
        self.resize(430, 720)
        self.setStyleSheet(QSS)
        # Float above other apps (pinned) by default — the window stays visible
        # and only leaves when you minimise/close it yourself.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_chat_page())    # 0
        self.stack.addWidget(self._build_settings_page())  # 1
        self.stack.addWidget(self._build_help_page())      # 2
        root.addWidget(self.stack, 1)

        self._restore_chat()

        # global hotkey -> capture (marshalled to GUI thread via signal)
        self._hotkey_fired.connect(self._capture)
        self.hotkeys = HotkeyManager()
        self.hotkeys.register(CONFIG.capture.hotkey, self._hotkey_fired.emit)

        # Warm the semantic model in the BACKGROUND so paraphrased questions
        # match the reference/memory — without freezing the UI on startup.
        if CONFIG.enable_semantic:
            from ..retrieval.embedding_manager import EmbeddingManager
            warm = FnWorker(lambda: EmbeddingManager.instance().available())
            self._start(warm)

        # Warm the OCR engine in the BACKGROUND too, so the FIRST screenshot
        # isn't slow while the model loads on demand.
        self._start(FnWorker(self.ocr.any_engine_available))

    # ================= top bar =================
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 10, 12, 10)
        settings_btn = self._icon("⚙", "Settings", self._show_settings)
        brand = QLabel("✦  Squad AI")
        brand.setObjectName("brand")
        self.pin_btn = self._icon("📌", "Keep on top (pinned)", self._toggle_pin)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(True)
        reset_btn = self._icon("🗑", "New / reset chat", self._reset_chat)
        help_btn = self._icon("?", "Help", self._show_help)
        lay.addWidget(settings_btn)
        lay.addStretch(1)
        lay.addWidget(brand)
        lay.addStretch(1)
        lay.addWidget(self.pin_btn)
        lay.addWidget(reset_btn)
        lay.addWidget(help_btn)
        return bar

    def _icon(self, text, tip, slot) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("icon")
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _toggle_pin(self):
        """Toggle always-on-top. Re-show is required after changing the flag."""
        on = self.pin_btn.isChecked()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.pin_btn.setToolTip("Keep on top (pinned)" if on
                                else "Not pinned")
        self.show()

    # ================= chat page =================
    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_inner = QWidget()
        self.chat_inner.setObjectName("chatInner")
        self.chat_layout = QVBoxLayout(self.chat_inner)
        self.chat_layout.setContentsMargins(12, 14, 12, 14)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch(1)
        self._empty = self._build_empty_state()
        self.chat_layout.insertWidget(0, self._empty)
        self.scroll.setWidget(self.chat_inner)
        v.addWidget(self.scroll, 1)

        v.addWidget(self._build_composer())
        return page

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Squad AI")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Ask anything, 📸 take a screenshot, or 📎 upload one.")
        sub.setObjectName("emptySub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(40)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(40)
        return w

    def _build_composer(self) -> QWidget:
        comp = QWidget()
        comp.setObjectName("composer")
        v = QVBoxLayout(comp)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(8)

        # staged screenshots row (hidden until something is staged)
        self.staged_row = QWidget()
        self.staged_layout = QHBoxLayout(self.staged_row)
        self.staged_layout.setContentsMargins(0, 0, 0, 0)
        self.staged_layout.setSpacing(6)
        self.staged_row.hide()
        v.addWidget(self.staged_row)

        # chips: Auto-answer, Lock area (reuse same region), New area (reselect)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chip_auto = self._chip("⚡ Auto-answer",
                                    CONFIG.capture.mode == "auto",
                                    self._toggle_auto)
        self.chip_lock = self._chip("🔒 Lock area",
                                    bool(self.svc.capture.locked_region()),
                                    self._toggle_lock)
        self.chip_new = self._chip("🔁 New area", False, lambda: self._capture(True))
        self.chip_new.setCheckable(False)
        self.chip_new.setVisible(bool(self.svc.capture.locked_region()))
        chips.addWidget(self.chip_auto)
        chips.addWidget(self.chip_lock)
        chips.addWidget(self.chip_new)
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("hint")
        chips.addWidget(self.status_lbl)
        chips.addStretch(1)
        v.addLayout(chips)

        # capture / upload row
        cap_row = QHBoxLayout()
        cap_row.setSpacing(7)
        self.cap_btn = QPushButton("📸  Screenshot")
        self.cap_btn.setObjectName("ghost")
        self.cap_btn.setMinimumHeight(40)
        self.cap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cap_btn.setToolTip("Capture (F8). With 🔒 Lock area on, reuses the "
                                "same region every time.")
        self.cap_btn.clicked.connect(lambda: self._capture(False))
        up = QPushButton("📎  Upload")
        up.setObjectName("ghost")
        up.setMinimumHeight(40)
        up.setCursor(Qt.CursorShape.PointingHandCursor)
        up.setToolTip("Upload one or more images")
        up.clicked.connect(self._upload)
        cap_row.addWidget(self.cap_btn, 1)
        cap_row.addWidget(up, 1)
        v.addLayout(cap_row)

        # input + Submit row
        row = QHBoxLayout()
        row.setSpacing(7)
        self.input = QLineEdit()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("Ask anything…")
        self.input.returnPressed.connect(self._on_send)
        self.send_btn = QPushButton("Submit  ➤")
        self.send_btn.setObjectName("primary")
        self.send_btn.setMinimumHeight(44)
        self.send_btn.setMinimumWidth(110)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        v.addLayout(row)

        self._btns = [self.cap_btn, up, self.send_btn]
        return comp

    def _chip(self, text, checked, slot) -> QPushButton:
        c = QPushButton(text)
        c.setObjectName("chip")
        c.setCheckable(True)
        c.setChecked(checked)
        c.setCursor(Qt.CursorShape.PointingHandCursor)
        c.clicked.connect(slot)
        return c

    # ================= settings page =================
    def _build_settings_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(8)

        v.addWidget(self._section("🔑 Connection"))
        v.addWidget(self._label("AI Provider"))
        self.f_provider = QComboBox()
        self.f_provider.addItem("DeepSeek", "deepseek")
        self.f_provider.addItem("AgentRouter", "agentrouter")
        # Persist the choice IMMEDIATELY so it survives restart even without
        # pressing Save (switching alone must never lose the other provider's
        # saved key).
        self.f_provider.currentIndexChanged.connect(self._on_provider_change)
        v.addWidget(self.f_provider)
        prov_hint = QLabel("The selected provider handles the AI fallback. Each "
                           "keeps its own key & settings — switching never wipes "
                           "the other or any data.")
        prov_hint.setObjectName("hint")
        prov_hint.setWordWrap(True)
        v.addWidget(prov_hint)

        # --- DeepSeek ---
        v.addWidget(self._label("DeepSeek API Key"))
        self.f_key = QLineEdit()
        self.f_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.f_key.setPlaceholderText("sk-…")
        v.addWidget(self.f_key)
        self.key_hint = QLabel()
        self.key_hint.setObjectName("hint")
        v.addWidget(self.key_hint)
        v.addWidget(self._label("DeepSeek Model"))
        self.f_model = QComboBox()
        self.f_model.addItems(["deepseek-chat (fast, cheap)",
                               "deepseek-reasoner (smarter, pricier)"])
        v.addWidget(self.f_model)
        test = QPushButton("Test DeepSeek 🔌")
        test.setObjectName("ghost")
        test.clicked.connect(self._test_connection)
        v.addWidget(test)

        # --- AgentRouter ---
        v.addWidget(self._divider())
        v.addWidget(self._section("🛰️ AgentRouter (optional)"))
        v.addWidget(self._label("AgentRouter API Key"))
        self.f_ar_key = QLineEdit()
        self.f_ar_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.f_ar_key.setPlaceholderText("Paste AgentRouter key")
        v.addWidget(self.f_ar_key)
        self.ar_key_hint = QLabel()
        self.ar_key_hint.setObjectName("hint")
        v.addWidget(self.ar_key_hint)
        v.addWidget(self._label("Base URL"))
        self.f_ar_base = QLineEdit()
        v.addWidget(self.f_ar_base)
        v.addWidget(self._label("Model"))
        self.f_ar_model = QLineEdit()
        self.f_ar_model.setPlaceholderText("deepseek-v4-flash")
        v.addWidget(self.f_ar_model)
        ar_row = QHBoxLayout()
        tcol = QVBoxLayout()
        tcol.addWidget(self._label("Temperature"))
        self.f_ar_temp = QLineEdit()
        tcol.addWidget(self.f_ar_temp)
        mcol = QVBoxLayout()
        mcol.addWidget(self._label("Max output tokens"))
        self.f_ar_maxtok = QLineEdit()
        mcol.addWidget(self.f_ar_maxtok)
        ar_row.addLayout(tcol)
        ar_row.addLayout(mcol)
        v.addLayout(ar_row)
        ar_test = QPushButton("Test AgentRouter 🔌")
        ar_test.setObjectName("ghost")
        ar_test.clicked.connect(self._test_agentrouter)
        v.addWidget(ar_test)

        v.addWidget(self._divider())
        v.addWidget(self._section("⌨️ Screenshot hotkey"))
        hk_hint = QLabel(f"Press <b>{CONFIG.capture.hotkey}</b> anytime to "
                         "capture. Change it here:")
        hk_hint.setObjectName("hint")
        hk_hint.setWordWrap(True)
        v.addWidget(hk_hint)
        self.f_hotkey = QLineEdit(CONFIG.capture.hotkey)
        v.addWidget(self.f_hotkey)

        v.addWidget(self._divider())
        v.addWidget(self._section("📝 Profile & instructions"))
        v.addWidget(self._label("Profile info  (one per line, e.g.  Age: 39)"))
        self.f_profile = QPlainTextEdit()
        self.f_profile.setPlaceholderText("Age: 39\nState: California\n"
                                          "Employment: Full-time employed")
        self.f_profile.setFixedHeight(120)
        v.addWidget(self.f_profile)
        v.addWidget(self._label("Instruction prompt (optional)"))
        self.f_prompt = QPlainTextEdit()
        self.f_prompt.setFixedHeight(70)
        v.addWidget(self.f_prompt)

        v.addWidget(self._divider())
        v.addWidget(self._section("📚 Reference / training text"))
        self.f_ref = QPlainTextEdit()
        self.f_ref.setPlaceholderText("Paste notes / answer key / facts…")
        self.f_ref.setFixedHeight(110)
        v.addWidget(self.f_ref)

        v.addWidget(self._divider())
        btn_row = QHBoxLayout()
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save_settings)
        close = QPushButton("Close")
        close.setObjectName("ghost")
        close.clicked.connect(self._show_chat)
        btn_row.addWidget(save)
        btn_row.addWidget(close)
        v.addLayout(btn_row)
        v.addStretch(1)

        scroll.setWidget(inner)
        return scroll

    def _build_help_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(16, 16, 16, 16)
        v.addWidget(self._section("❔ How to use"))
        body = QLabel(
            "• <b>⚙ Settings</b> → add profile info, reference text, and "
            "(optionally) your DeepSeek key.<br><br>"
            "• Type any question and press <b>➤</b>.<br><br>"
            "• <b>📸</b> capture the screen or <b>📎</b> upload an image — the "
            "answer appears in the chat.<br><br>"
            "• <b>⚡ Auto</b> answers a screenshot instantly; off = stage several "
            "then send together.<br><br>"
            "• <b>🔒 Lock area</b> reuses the last selected region.<br><br>"
            "• Answers marked <span style='color:#34d399'>free</span> cost "
            "nothing; only <span style='color:#fbbf24'>DeepSeek AI</span> uses "
            "your API credits — and only when it must.")
        body.setObjectName("hint")
        body.setWordWrap(True)
        v.addWidget(body)
        got = QPushButton("Got it")
        got.setObjectName("primary")
        got.clicked.connect(self._show_chat)
        v.addWidget(got)
        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _section(self, text) -> QLabel:
        l = QLabel(text)
        l.setObjectName("sectionTitle")
        return l

    def _label(self, text) -> QLabel:
        l = QLabel(text)
        l.setObjectName("fieldLabel")
        return l

    def _divider(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"color:{COLORS['border']};")
        return f

    # ================= navigation =================
    def _show_chat(self):
        self.stack.setCurrentIndex(0)

    def _show_settings(self):
        # Toggle: if already on Settings, clicking ⚙ again returns to chat.
        if self.stack.currentIndex() == 1:
            self.stack.setCurrentIndex(0)
            return
        self._load_settings_into_form()
        self.stack.setCurrentIndex(1)

    def _show_help(self):
        self.stack.setCurrentIndex(2)

    # ================= settings load/save =================
    def _load_settings_into_form(self):
        key = self.svc.credentials.get_key(CONFIG.provider.name)
        self.f_key.setText(key or "")
        self.key_hint.setText(f"Saved: {self.svc.credentials.masked(key)}"
                              if key else "Local features work without a key.")
        self.f_hotkey.setText(CONFIG.capture.hotkey)
        # Show the RAW profile text exactly as the user typed it (verbatim), so
        # it never gets silently reformatted. Fall back to structured fields for
        # profiles created before this was stored.
        raw = self.svc.settings.get("profile_info_raw", "")
        self.f_profile.setPlainText(raw if raw else self._profile_to_text())
        self.f_prompt.setPlainText(self.svc.settings.get("custom_prompt", "") or "")
        self.f_ref.setPlainText(self.svc.settings.get("reference_text", "") or "")
        model = self.svc.settings.get("model", "deepseek-chat")
        self.f_model.setCurrentIndex(1 if model == "deepseek-reasoner" else 0)

        # provider selector + AgentRouter fields
        pidx = self.f_provider.findData(CONFIG.active_provider)
        self.f_provider.setCurrentIndex(pidx if pidx >= 0 else 0)
        ar = CONFIG.agentrouter
        ar_key = self.svc.credentials.get_key("agentrouter")
        self.f_ar_key.setText("")
        self.ar_key_hint.setText(
            f"Saved: {self.svc.credentials.masked(ar_key)}" if ar_key
            else "No AgentRouter key saved yet.")
        self.f_ar_base.setText(ar.base_url)
        self.f_ar_model.setText(ar.model)
        self.f_ar_temp.setText(str(ar.temperature))
        self.f_ar_maxtok.setText(str(ar.max_output_tokens))

    def _save_settings(self):
        key = self.f_key.text().strip()
        if key and not key.startswith("•"):
            self.svc.credentials.set_key(CONFIG.provider.name, key)
        profile_text = self.f_profile.toPlainText()
        # Keep the user's exact text (sent whole to the AI) AND parse any
        # "Key: Value" lines into fast structured fields for local answering.
        self.svc.settings.set("profile_info_raw", profile_text)
        self._text_to_profile(profile_text)
        self.svc.settings.set("custom_prompt", self.f_prompt.toPlainText())
        self._save_reference(self.f_ref.toPlainText())
        model = ("deepseek-reasoner" if self.f_model.currentIndex() == 1
                 else "deepseek-chat")
        self.svc.settings.set("model", model)
        CONFIG.provider.model = model

        # active provider + AgentRouter config
        self._save_agentrouter_fields()

        hk = self.f_hotkey.text().strip() or "F8"
        if hk != CONFIG.capture.hotkey:
            CONFIG.capture.hotkey = hk
            self.svc.settings.set("hotkey", hk)
            self.hotkeys.register(hk, self._hotkey_fired.emit)
        QMessageBox.information(self, "Saved", "Settings saved.")
        self._show_chat()

    def _profile_to_text(self) -> str:
        return "\n".join(f"{f.key}: {f.value}" for f in self.svc.profile.all())

    # A profile can describe a whole family. Only the TOP section is "me"; once
    # a wife/child/etc. section starts, those fields (Age, Gender, DOB…) belong
    # to someone else and must NOT overwrite the main person's fast fields.
    _PERSON_SECTION = re.compile(
        r"^(wife|husband|spouse|partner|child|children|son|daughter|dependent|"
        r"mother|father|parent|kid)\b", re.IGNORECASE)

    def _text_to_profile(self, text: str) -> None:
        # Canonicalize keys to lowercase so "Age" and "age" never duplicate
        # (DB keys are case-sensitive; matching is case-insensitive).
        seen = set()
        for line in text.splitlines():
            if self._PERSON_SECTION.match(line.strip()):
                break  # rest of the profile describes other people
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if not k or not v:      # skip empty section headers like "House hold:"
                continue
            vtype = "number" if re.fullmatch(r"[\d,.]+", v or "") else "text"
            self.svc.profile.upsert(k, v, vtype)
            seen.add(k)
        for f in self.svc.profile.all():
            if f.key.lower() not in seen:
                self.svc.profile.delete(f.key)

    def _save_reference(self, text: str) -> None:
        text = text.strip()
        prev = self.svc.settings.get("reference_text", "") or ""
        if text == prev:
            return
        for doc in self.svc.reference.documents():
            self.svc.reference.delete_document(doc["id"])
        if text:
            self.svc.reference.add_document(text, title="Reference")
        self.svc.settings.set("reference_text", text)

    def _test_connection(self):
        key = self.f_key.text().strip()
        if key and not key.startswith("•"):
            self.svc.credentials.set_key(CONFIG.provider.name, key)
        provider = self.svc.build_named_provider("deepseek")
        if provider is None:
            QMessageBox.warning(self, "No key", "Add your DeepSeek key first.")
            return
        ok, msg = provider.test_connection()
        (QMessageBox.information if ok else QMessageBox.warning)(
            self, "✓ Connected" if ok else "Connection failed", msg)

    def _on_provider_change(self) -> None:
        prov = self.f_provider.currentData() or "deepseek"
        CONFIG.active_provider = prov
        self.svc.settings.set("active_provider", prov)

    def _save_agentrouter_fields(self) -> None:
        """Persist the active-provider choice and AgentRouter config + key."""
        prov = self.f_provider.currentData() or "deepseek"
        CONFIG.active_provider = prov
        self.svc.settings.set("active_provider", prov)

        ar_key = self.f_ar_key.text().strip()
        if ar_key and not ar_key.startswith("•"):
            self.svc.credentials.set_key("agentrouter", ar_key)

        ar = CONFIG.agentrouter
        ar.base_url = self.f_ar_base.text().strip() or ar.base_url
        ar.model = self.f_ar_model.text().strip() or ar.model
        ar.temperature = _to_float(self.f_ar_temp.text(), ar.temperature)
        ar.max_output_tokens = _to_int(self.f_ar_maxtok.text(),
                                       ar.max_output_tokens)
        s = self.svc.settings
        s.set("agentrouter_base_url", ar.base_url)
        s.set("agentrouter_model", ar.model)
        s.set("agentrouter_temperature", ar.temperature)
        s.set("agentrouter_max_tokens", ar.max_output_tokens)

    def _test_agentrouter(self):
        # apply the current fields first so the test reflects what's on screen
        self._save_agentrouter_fields()
        typed = self.f_ar_key.text().strip()
        if typed and not typed.startswith("•"):
            from ..providers.agentrouter_provider import AgentRouterProvider
            provider = AgentRouterProvider(typed)
        else:
            provider = self.svc.build_named_provider("agentrouter")
        if provider is None:
            QMessageBox.warning(self, "No key",
                                "Add your AgentRouter key first.")
            return
        ok, msg = provider.test_connection()
        (QMessageBox.information if ok else QMessageBox.warning)(
            self, "✓ Connected" if ok else "Connection failed", msg)

    # ================= chat rendering =================
    def _row(self, bubble: QWidget, role: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        if role == "user":
            h.addStretch(1)
            h.addWidget(bubble)
        else:
            avatar = QLabel()
            avatar.setObjectName("avatar")
            avatar.setFixedSize(26, 26)
            h.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            h.addWidget(bubble)
            h.addStretch(1)
        return row

    def _bubble(self, role: str, html: str = "") -> QLabel:
        b = QLabel()
        b.setObjectName("userBubble" if role == "user" else "aiBubble")
        b.setTextFormat(Qt.TextFormat.RichText)
        b.setWordWrap(True)
        b.setMaximumWidth(320)
        b.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        b.setText(html)
        return b

    def _add(self, role: str, html: str) -> QLabel:
        if self._empty is not None:
            self._empty.setParent(None)
            self._empty = None
        bubble = self._bubble(role, html)
        row = self._row(bubble, role)
        # insert before the trailing stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        QTimer.singleShot(0, self._scroll_bottom)
        return bubble

    def _add_image(self, path: str) -> None:
        b = QLabel()
        b.setObjectName("userBubble")
        pix = QPixmap(path)
        if not pix.isNull():
            b.setPixmap(pix.scaledToWidth(180,
                        Qt.TransformationMode.SmoothTransformation))
        else:
            b.setText("📸 Screenshot")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1,
                                      self._row(b, "user"))
        QTimer.singleShot(0, self._scroll_bottom)

    def _scroll_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _restore_chat(self):
        msgs = self.svc.chat.messages(self.session_id)
        for m in msgs:
            if m["role"] == "user":
                self._add("user", _html.escape(m["content"]))
            else:
                meta = ""
                src = m.get("source")
                if src and src in AnswerSource.__members__:
                    meta = _source_meta(AnswerSource(src))
                self._add("ai", _answer_html(m["content"]) + meta)

    # ================= actions =================
    def _start(self, worker):
        """Start a worker while keeping a strong Python reference to it until it
        finishes (prevents the PySide6 QRunnable/signals GC segfault)."""
        worker.setAutoDelete(False)
        self._live_workers.add(worker)
        worker.signals.finished.connect(
            lambda *_: self._live_workers.discard(worker))
        worker.signals.error.connect(
            lambda *_: self._live_workers.discard(worker))
        self.pool.start(worker, 0)  # priority arg makes this call textually unique
        return worker

    def _set_busy(self, b: bool):
        self._busy = b
        for btn in self._btns:
            btn.setEnabled(not b)

    def _on_send(self):
        if self._staged:
            imgs, self._staged = self._staged[:], []
            self._render_staged()
            self._answer_images(imgs)
        else:
            self._send_text()

    def _recent_context(self, limit: int = 6, max_chars: int = 1500) -> str:
        """Last few chat turns, bounded by BOTH turn count and characters, so the
        payload never grows with the conversation (keeps DeepSeek fast + cheap).
        The engine still only sends this when the question actually needs it."""
        msgs = self.svc.chat.messages(self.session_id)
        lines = []
        for m in msgs[-limit:]:
            who = "User" if m["role"] == "user" else "Assistant"
            content = (m["content"] or "").strip()
            if len(content) > 400:            # truncate long turns (OCR pages)
                content = content[:400] + "…"
            lines.append(f"{who}: {content}")
        text = "\n".join(lines)
        return text[-max_chars:]              # hard cap on total size

    def _send_text(self):
        text = self.input.text().strip()
        if not text or self._busy:
            return
        self.input.clear()
        recent = self._recent_context()  # BEFORE adding the new turn
        self.svc.chat.add_message(self.session_id, "user", text)
        self._add("user", _html.escape(text))
        pending = self._add("ai", "<i style='color:#9990c4'>…thinking</i>")
        self._set_busy(True)
        worker = AnswerWorker(self.svc.engine, text, recent_context=recent)
        worker.signals.progress.connect(
            lambda s: pending.setText(f"<i style='color:#9990c4'>{s}</i>"))
        worker.signals.finished.connect(
            lambda r: self._on_answer(r, pending, text))
        worker.signals.error.connect(lambda e: self._on_worker_error(e, pending))
        self._start(worker)

    def _on_answer(self, result: AnswerResult, pending: QLabel,
                   question_text: str = ""):
        self._set_busy(False)
        if result.error and not result.answer:
            msg = ("Add your API key in ⚙ Settings to answer this one."
                   if result.reasoning_code == "API_KEY_MISSING"
                   else f"⚠️ {result.error}")
            pending.setText(_html.escape(msg))
            return
        pending.setText(self._answer_body_html(question_text, result)
                        + _source_meta(result.source))
        self.svc.chat.add_message(self.session_id, "assistant", result.answer,
                                  result.source.value)
        QTimer.singleShot(0, self._scroll_bottom)

    def _answer_body_html(self, question_text: str, result: AnswerResult) -> str:
        """Render the answer. For option questions show ALL options as a tidy
        checkbox list with the chosen one(s) ticked; otherwise plain text.
        Each item is on its own line so answers never run together."""
        options = self._options_for(question_text)
        if not options:
            return _answer_html(result.answer)

        selected = self._selected_options(options, result)
        rows = []
        for opt in options:
            on = opt in selected
            box = "☑" if on else "☐"
            color = COLORS["success"] if on else COLORS["muted"]
            weight = "700" if on else "400"
            rows.append(
                f"<div style='margin:5px 0;color:{color};font-weight:{weight}'>"
                f"{box}&nbsp;&nbsp;{_html.escape(opt)}</div>")
        return "".join(rows)

    @staticmethod
    def _options_for(question_text: str):
        if not question_text:
            return []
        try:
            parsed = _QP.parse(question_text)
            return [o.original for o in parsed.options]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _selected_options(options, result: AnswerResult) -> set:
        """Which options the AI/engine picked (supports multi-select)."""
        selected = set()
        idx = result.selected_option_index
        if idx is not None and 0 <= idx < len(options):
            selected.add(options[idx])
        # also match by answer text so snapped/multi answers tick correctly
        ans_norm = _N.normalize(result.answer or "")
        if ans_norm:
            for opt in options:
                o_norm = _N.normalize(opt)
                if o_norm and o_norm in ans_norm:
                    selected.add(opt)
        return selected

    def _on_worker_error(self, err: str, pending: QLabel):
        self._set_busy(False)
        pending.setText(_html.escape(f"⚠️ {err}"))

    # ---- screenshots / upload ----
    def _capture(self, force_new: bool = False):
        """Capture the screen.

        * 🔒 Lock area ON + a saved region + not New-area → grab that SAME region
          instantly (no reselection) → auto-answer if ⚡ is on.
        * Otherwise → freeze the desktop into an image and show it so the user
          can clearly see and drag the area (fixes the black-screen overlay).
        """
        if self._busy:
            return
        locked = self.svc.capture.locked_region()
        if self.chip_lock.isChecked() and locked and not force_new:
            self._grab_region(Region(**locked))
            return
        # Hide our own window so it isn't in the frozen screenshot, then open
        # the selection overlay on the real desktop image.
        self.hide()
        QTimer.singleShot(220, self._open_selection_overlay)

    def _open_selection_overlay(self):
        try:
            self._open_selection_overlay_impl()
        except ScreenshotError as exc:
            self.show()
            QMessageBox.warning(self, "Capture failed", str(exc))
        except Exception as exc:  # noqa: BLE001
            # Never let a capture error tear the whole app down — show it and
            # keep running so the user isn't dropped back to a reinstall.
            self.show()
            QMessageBox.warning(
                self, "Capture failed",
                f"Could not open the selection overlay.\n\n"
                f"{type(exc).__name__}: {exc}")

    def _open_selection_overlay_impl(self):
        full = self.shots.capture_region(None)   # whole screen
        pix = QPixmap(full)
        if pix.isNull():
            self.show()
            QMessageBox.warning(self, "Capture failed",
                                "Could not read the screen image.")
            return
        # A near-black capture almost always means macOS did not actually
        # record the screen (missing Screen Recording permission). Showing that
        # black image as the overlay is what looked like "the overlay is black
        # and I can't see anything underneath" — so detect it and guide the
        # user instead of putting up a useless black screen.
        if self._looks_black(pix):
            self.show()
            if sys.platform == "darwin":
                detail = ("Grant Screen Recording permission to this app in "
                          "System Settings → Privacy & Security → Screen "
                          "Recording, then quit and reopen the app.")
            elif sys.platform.startswith("win"):
                detail = ("This usually means a display-driver / DRM-protected "
                          "window blocked the capture. Try again, or install "
                          "the 'mss' and 'Pillow' packages "
                          "(pip install mss Pillow).")
            else:
                detail = ("The screen grab returned nothing. Make sure a "
                          "screenshot backend is installed "
                          "(pip install mss Pillow).")
            QMessageBox.warning(
                self, "Capture came back black",
                "The screen capture came back black. " + detail)
            return
        out = str(cache_dir() / f"sel_{int(time.time() * 1000)}.png")
        self._overlay = ScreenshotOverlay(pix, out)
        self._overlay.selected.connect(self._on_region_image)
        self._overlay.showFullScreen()
        self._overlay.raise_()
        self._overlay.activateWindow()

    @staticmethod
    def _looks_black(pix: QPixmap) -> bool:
        """True if the captured image is essentially all black.

        Samples a small grid of pixels (cheap) instead of scanning every pixel.
        A capture with no permission comes back uniformly black, so if every
        sampled pixel is near-black we treat the whole image as black.
        """
        img = pix.toImage()
        w, h = img.width(), img.height()
        if w == 0 or h == 0:
            return True
        steps = 8
        for i in range(1, steps):
            for j in range(1, steps):
                c = img.pixelColor(w * i // steps, h * j // steps)
                if c.red() > 12 or c.green() > 12 or c.blue() > 12:
                    return False
        return True

    def _on_region_image(self, region, path):
        self.show()                          # bring our window back
        self.raise_()
        if region is None or not path:       # cancelled
            return
        if self.chip_lock.isChecked():
            self.svc.capture.save_locked(region.x, region.y, region.w, region.h)
            self.chip_new.setVisible(True)
        self._intake([path])

    def _grab_region(self, region: Region):
        """Capture a fixed (locked) region live, without the overlay."""
        self.status_lbl.setText("Capturing…")
        worker = FnWorker(self.shots.capture_region, region)
        worker.signals.finished.connect(self._on_capture_done)
        worker.signals.error.connect(
            lambda e: (self.status_lbl.setText(""),
                       QMessageBox.warning(self, "Capture failed", e)))
        self._start(worker)

    def _on_capture_done(self, path: Optional[str]):
        self.status_lbl.setText("")
        if not path:
            return
        self._intake([path])

    def _upload(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select image(s)", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if paths:
            self._intake(list(paths))

    def _intake(self, paths: List[str]):
        if self.chip_auto.isChecked():
            self._answer_images(paths)
        else:
            self._staged.extend(paths)
            self._render_staged()

    def _render_staged(self):
        self._clear_layout(self.staged_layout)
        if not self._staged:
            self.staged_row.hide()
            return
        self.staged_row.show()

        header = QHBoxLayout()
        lbl = QLabel(f"{len(self._staged)} screenshot(s) ready · press Submit")
        lbl.setStyleSheet(f"color:{COLORS['accent']};font-size:11px;"
                          "font-weight:600;")
        header.addWidget(lbl)
        header.addStretch(1)
        clear = QPushButton("Clear all")
        clear.setObjectName("mini")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self._clear_staged)
        header.addWidget(clear)
        self.staged_layout.addLayout(header)

        # thumbnail strip with a ✕ remove button on each; click a thumb to preview
        strip = QHBoxLayout()
        strip.setSpacing(8)
        for i, path in enumerate(self._staged):
            strip.addWidget(self._staged_thumb(i, path))
        strip.addStretch(1)
        self.staged_layout.addLayout(strip)

    def _staged_thumb(self, idx: int, path: str) -> QWidget:
        cell = QWidget()
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)

        thumb = QLabel()
        pix = QPixmap(path)
        if not pix.isNull():
            thumb.setPixmap(pix.scaledToHeight(
                60, Qt.TransformationMode.SmoothTransformation))
        else:
            thumb.setText("📸")
        thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        thumb.setToolTip("Click to preview full size")
        thumb.mousePressEvent = lambda _e, p=path: self._preview(p)
        cl.addWidget(thumb, 0, Qt.AlignmentFlag.AlignHCenter)

        rm = QPushButton(f"✕ #{idx + 1}")
        rm.setObjectName("mini")
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip("Remove this screenshot")
        rm.clicked.connect(lambda _c=False, i=idx: self._unstage(i))
        cl.addWidget(rm, 0, Qt.AlignmentFlag.AlignHCenter)
        return cell

    def _preview(self, path: str):
        """Show the chosen screenshot full size in a dialog before sending."""
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Screenshot preview")
        lay = QVBoxLayout(dlg)
        lbl = QLabel()
        pix = QPixmap(path)
        if not pix.isNull():
            screen = self.screen().availableGeometry() if self.screen() else None
            max_w = min(900, screen.width() - 80) if screen else 900
            max_h = min(700, screen.height() - 120) if screen else 700
            lbl.setPixmap(pix.scaled(max_w, max_h,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation))
        else:
            lbl.setText("Could not load image.")
        lay.addWidget(lbl)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()

    def _unstage(self, idx: int):
        if 0 <= idx < len(self._staged):
            self._staged.pop(idx)
            self._render_staged()

    def _clear_staged(self):
        self._staged = []
        self._render_staged()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                MainWindow._clear_layout(item.layout())

    def _answer_images(self, paths: List[str]):
        if self._busy or not paths:
            return
        recent = self._recent_context()  # capture history BEFORE this turn
        for p in paths:
            self._add_image(p)
        pending = self._add("ai", "<i style='color:#9990c4'>Reading…</i>")
        self._set_busy(True)
        if not self.ocr.any_engine_available():
            self._set_busy(False)
            pending.setText("No OCR engine found. Install Tesseract "
                            "(brew install tesseract) or type the question.")
            return
        worker = FnWorker(self.ocr.recognize_many, paths)
        worker.signals.finished.connect(
            lambda r: self._after_ocr(r, pending, recent))
        worker.signals.error.connect(lambda e: self._on_worker_error(e, pending))
        self._start(worker)

    _OCR_NOISE = re.compile(
        r"^(?:next question|previous|prev|submit|back|continue|skip)\b"
        r"|^(?:question|q|page)\s*\d+\s*$"
        r"|^\d+\s*%\s*$"
        r"|^\d+\s*/\s*\d+\s*$", re.IGNORECASE)

    def _clean_ocr(self, text: str) -> str:
        """Drop survey-UI chrome (nav buttons, counters) so the AI/matcher sees
        only the real question + options."""
        kept = [ln for ln in text.splitlines()
                if ln.strip() and not self._OCR_NOISE.match(ln.strip())]
        return "\n".join(kept) or text

    def _after_ocr(self, ocr_result, pending: QLabel, recent: str = ""):
        if not ocr_result.text.strip():
            self._set_busy(False)
            pending.setText("OCR did not detect any text.")
            return
        cleaned = self._clean_ocr(ocr_result.text)
        # Store the OCR'd text as the user turn so later questions about the same
        # page ("based on the above…") can use it as context.
        self.svc.chat.add_message(self.session_id, "user", cleaned)

        # A single screenshot can hold SEVERAL questions. Split the page and
        # answer each one separately so every question gets its own answer.
        blocks = split_questions(cleaned)
        if len(blocks) > 1:
            pending.setText(
                f"<i style='color:#9990c4'>Answering {len(blocks)} "
                f"questions…</i>")
            worker = FnWorker(self._answer_blocks, blocks, recent)
            worker.signals.finished.connect(
                lambda pairs: self._on_multi_answer(pairs, pending))
            worker.signals.error.connect(
                lambda e: self._on_worker_error(e, pending))
            self._start(worker)
            return

        pending.setText("<i style='color:#9990c4'>Searching locally…</i>")
        worker = AnswerWorker(self.svc.engine, cleaned, recent_context=recent)
        worker.signals.progress.connect(
            lambda s: pending.setText(f"<i style='color:#9990c4'>{s}</i>"))
        worker.signals.finished.connect(
            lambda r: self._on_answer(r, pending, cleaned))
        worker.signals.error.connect(lambda e: self._on_worker_error(e, pending))
        self._start(worker)

    def _answer_blocks(self, blocks: List[str], recent: str):
        """Answer each question block (runs off the GUI thread). Each block is
        one question → at most one API call, exactly like a single question."""
        pairs = []
        for b in blocks:
            try:
                r = self.svc.engine.answer(b, recent_context=recent)
            except Exception as exc:  # noqa: BLE001
                r = AnswerResult(answer="", source=AnswerSource.UNRESOLVED,
                                 confidence=0.0, reasoning_code="ERROR",
                                 error=str(exc))
            pairs.append((b, r))
        return pairs

    @staticmethod
    def _question_label(block: str) -> str:
        """The question line (the one ending in '?', else the first line)."""
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        for ln in lines:
            if ln.endswith("?"):
                return ln
        return lines[0] if lines else ""

    def _on_multi_answer(self, pairs, pending: QLabel):
        self._set_busy(False)
        pending.setText(f"<b>Answered {len(pairs)} questions:</b>")
        for block, result in pairs:
            q = _html.escape(self._question_label(block))
            head = (f"<div style='color:{COLORS['accent']};font-weight:700;"
                    f"margin-bottom:6px'>Q: {q}</div>")
            if result.error and not result.answer:
                body = (f"<span style='color:#fbbf24'>⚠️ "
                        f"{_html.escape(result.error)}</span>")
            else:
                body = (self._answer_body_html(block, result)
                        + _source_meta(result.source))
            self._add("ai", head + body)
            if result.answer:
                self.svc.chat.add_message(
                    self.session_id, "assistant",
                    f"Q: {self._question_label(block)}\n{result.answer}",
                    result.source.value)
        QTimer.singleShot(0, self._scroll_bottom)

    # ---- chips ----
    def _toggle_auto(self):
        mode = "auto" if self.chip_auto.isChecked() else "manual"
        CONFIG.capture.mode = mode
        self.svc.settings.set("capture_mode", mode)

    def _toggle_lock(self):
        """Turn area-lock on/off. On = the next capture picks a region and then
        every F8/📸 reuses it. Off = clear the saved region, pick fresh each time.
        """
        if self.chip_lock.isChecked():
            self.status_lbl.setText("Lock on: next capture sets the area.")
            QTimer.singleShot(2500, lambda: self.status_lbl.setText(""))
        else:
            self.svc.capture.clear_lock()
            self.chip_new.setVisible(False)

    def _reset_chat(self):
        self.session_id = self.svc.chat.create_session()
        while self.chat_layout.count() > 1:  # keep trailing stretch
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._empty = self._build_empty_state()
        self.chat_layout.insertWidget(0, self._empty)

    def closeEvent(self, event):  # noqa: N802
        self.hotkeys.stop()
        super().closeEvent(event)

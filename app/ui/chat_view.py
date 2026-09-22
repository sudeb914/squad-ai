"""Chat page: type a question, capture screenshots, see the answer + source."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from ..capture.region_selector import Region
from ..capture.screenshot_manager import ScreenshotError, ScreenshotManager
from ..core.models import AnswerResult
from ..ocr.ocr_manager import OcrManager
from ..services import Services
from ..utils.config import CONFIG
from .screenshot_overlay import ScreenshotOverlay
from .workers import AnswerWorker, FnWorker


class ChatView(QWidget):
    def __init__(self, svc: Services):
        super().__init__()
        self.svc = svc
        self.pool = QThreadPool.globalInstance()
        self.ocr = OcrManager()
        self.shots = ScreenshotManager()
        self.session_id = svc.chat.ensure_session()
        self._overlay: Optional[ScreenshotOverlay] = None
        self._pending_images: List[str] = []

        layout = QVBoxLayout(self)

        # top controls
        controls = QHBoxLayout()
        self.capture_btn = QPushButton("📷 Capture (region)")
        self.capture_btn.clicked.connect(self.start_capture)
        self.lock_btn = QPushButton("🔒 Lock area")
        self.lock_btn.setCheckable(True)
        self.new_area_btn = QPushButton("🆕 New area")
        self.new_area_btn.clicked.connect(self._clear_lock)
        self.upload_btn = QPushButton("🖼 Upload image")
        self.upload_btn.clicked.connect(self._upload)
        self.mode = QComboBox()
        self.mode.addItems(["manual", "auto"])
        self.mode.setCurrentText(CONFIG.capture.mode)
        self.mode.currentTextChanged.connect(self._mode_changed)
        for w in (self.capture_btn, self.lock_btn, self.new_area_btn,
                  self.upload_btn, QLabel("Mode:"), self.mode):
            controls.addWidget(w)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.transcript = QTextBrowser()
        layout.addWidget(self.transcript, 1)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")
        layout.addWidget(self.status)

        entry = QHBoxLayout()
        self.input = QLineEdit(placeholderText="Type a question and press Enter")
        self.input.returnPressed.connect(self.send_typed)
        send = QPushButton("Answer")
        send.clicked.connect(self.send_typed)
        new_chat = QPushButton("New Chat")
        new_chat.clicked.connect(self._new_chat)
        entry.addWidget(self.input, 1)
        entry.addWidget(send)
        entry.addWidget(new_chat)
        layout.addLayout(entry)

        self._load_history()

    # -- history ----------------------------------------------------------
    def _load_history(self) -> None:
        self.transcript.clear()
        for m in self.svc.chat.messages(self.session_id):
            self._render(m["role"], m["content"], m.get("source"))

    def _render(self, role: str, content: str, source: Optional[str]) -> None:
        if role == "user":
            self.transcript.append(f"<p><b>You:</b> {content}</p>")
        else:
            tag = f" <i style='color:#888'>[{source}]</i>" if source else ""
            self.transcript.append(f"<p><b>Squad AI:</b> {content}{tag}</p>")

    # -- typed question ---------------------------------------------------
    def send_typed(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._ask(text)

    def _ask(self, text: str, options: Optional[List[str]] = None) -> None:
        self.svc.chat.add_message(self.session_id, "user", text)
        self._render("user", text, None)
        self.status.setText("Searching locally...")
        worker = AnswerWorker(self.svc.engine, text, options)
        worker.signals.progress.connect(self.status.setText)
        worker.signals.finished.connect(self._on_answer)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_answer(self, result: AnswerResult) -> None:
        self.status.setText("")
        if result.error and not result.answer:
            self._render("assistant", f"⚠️ {result.error}",
                         result.source.ui_label())
            self.svc.chat.add_message(self.session_id, "assistant",
                                      f"⚠️ {result.error}",
                                      result.source.value)
            return
        label = result.source.ui_label()
        self._render("assistant", result.answer, label)
        self.svc.chat.add_message(self.session_id, "assistant", result.answer,
                                  result.source.value,
                                  {"confidence": result.confidence,
                                   "reasoning": result.reasoning_code})

    def _on_error(self, msg: str) -> None:
        self.status.setText("")
        QMessageBox.warning(self, "Error", msg)

    # -- capture ----------------------------------------------------------
    def start_capture(self) -> None:
        locked = self.svc.capture.locked_region()
        if self.lock_btn.isChecked() and locked:
            self._capture_region(Region(**locked))
            return
        self._overlay = ScreenshotOverlay()
        self._overlay.region_selected.connect(self._on_region)
        self._overlay.show()

    def _on_region(self, region: Optional[Region]) -> None:
        if region is None:
            return
        if self.lock_btn.isChecked():
            self.svc.capture.save_locked(region.x, region.y, region.w, region.h)
        self._capture_region(region)

    def _capture_region(self, region: Region) -> None:
        try:
            path = self.shots.capture_region(region)
        except ScreenshotError as exc:
            QMessageBox.warning(self, "Capture failed", str(exc))
            return
        self._ocr_and_maybe_answer([path])

    def _upload(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select screenshot(s)", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if paths:
            self._ocr_and_maybe_answer(list(paths))

    def _ocr_and_maybe_answer(self, paths: List[str]) -> None:
        if not self.ocr.any_engine_available():
            QMessageBox.information(
                self, "OCR unavailable",
                "No local OCR engine is installed. Install PaddleOCR or "
                "Tesseract, or type the question manually.")
            return
        self.status.setText("Reading...")
        worker = FnWorker(self.ocr.recognize_many, paths)
        worker.signals.finished.connect(self._on_ocr)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_ocr(self, result) -> None:
        self.status.setText("")
        if not result.text.strip():
            QMessageBox.information(self, "No text",
                                    "OCR did not detect any text.")
            return
        if self.mode.currentText() == "auto":
            self._ask(result.text)
        else:
            self.input.setText(result.text.replace("\n", " "))
            self.transcript.append(
                f"<p style='color:#888'><i>OCR ({result.engine}, "
                f"conf {result.confidence:.2f}):</i> {result.text}</p>")

    # -- misc -------------------------------------------------------------
    def _mode_changed(self, mode: str) -> None:
        CONFIG.capture.mode = mode
        self.svc.settings.set("capture_mode", mode)

    def _clear_lock(self) -> None:
        self.svc.capture.clear_lock()
        self.lock_btn.setChecked(False)

    def _new_chat(self) -> None:
        self.session_id = self.svc.chat.create_session()
        self._load_history()

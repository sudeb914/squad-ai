"""Coordinates OCR engines. Local-only; screenshots never leave the machine.

Runs PaddleOCR first, estimates quality, and falls back to Tesseract if the
Paddle result looks unusable. Combines multiple images (one logical question
spread across screenshots) in order. Independent of the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import preprocessing
from .paddle_engine import OcrOutput, PaddleEngine
from .tesseract_engine import TesseractEngine
from ..utils.logging import get_logger

log = get_logger("ocr")

_MIN_USABLE_CONF = 0.45
_MIN_USABLE_CHARS = 3


@dataclass
class OcrResult:
    text: str
    confidence: float
    engine: str
    usable: bool


class OcrManager:
    def __init__(self) -> None:
        self.paddle = PaddleEngine()
        self.tesseract = TesseractEngine()

    def any_engine_available(self) -> bool:
        return self.paddle.available() or self.tesseract.available()

    def recognize_image(self, image_path: str,
                        preprocess: bool = True) -> OcrResult:
        path = preprocessing.preprocess(image_path) if preprocess else image_path

        primary: Optional[OcrOutput] = None
        if self.paddle.available():
            primary = self.paddle.recognize(path)

        if self._usable(primary):
            return self._to_result(primary)

        # fallback
        if self.tesseract.available():
            fb = self.tesseract.recognize(path)
            if self._usable(fb):
                log.info("Used Tesseract fallback")
                return self._to_result(fb)
            primary = primary or fb

        if primary is None:
            return OcrResult(
                "", 0.0, "none", usable=False)
        return self._to_result(primary)

    def recognize_many(self, image_paths: List[str]) -> OcrResult:
        """OCR several images belonging to ONE question, combined in order."""
        texts, confs, engines = [], [], []
        for p in image_paths:
            r = self.recognize_image(p)
            if r.text.strip():
                texts.append(r.text.strip())
                confs.append(r.confidence)
                engines.append(r.engine)
        combined = "\n".join(texts)
        conf = sum(confs) / len(confs) if confs else 0.0
        return OcrResult(combined, conf, "+".join(dict.fromkeys(engines)) or "none",
                         usable=bool(combined.strip()))

    @staticmethod
    def _usable(out: Optional[OcrOutput]) -> bool:
        return bool(out and len(out.text.strip()) >= _MIN_USABLE_CHARS
                    and out.confidence >= _MIN_USABLE_CONF)

    @staticmethod
    def _to_result(out: OcrOutput) -> OcrResult:
        return OcrResult(out.text, out.confidence, out.engine,
                         usable=bool(out.text.strip()))

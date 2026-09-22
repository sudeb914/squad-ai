"""RapidOCR wrapper — the bundle-friendly primary OCR engine.

``rapidocr-onnxruntime`` ships its detection/recognition models inside the wheel
and runs them on onnxruntime, so it needs no system binary (unlike Tesseract)
and packages cleanly into a PyInstaller build — this is what makes OCR work in
the standalone .exe out of the box. Lazy-loaded and fully optional: if the
package isn't installed the engine simply reports unavailable and the manager
falls back to Paddle/Tesseract.

All processing is local; images never leave the machine.
"""
from __future__ import annotations

import threading
from typing import List, Optional

from .paddle_engine import OcrOutput
from ..utils.logging import get_logger

log = get_logger("ocr.rapid")


class RapidOcrEngine:
    def __init__(self) -> None:
        self._ocr = None
        self._tried = False
        self._lock = threading.Lock()

    def _ensure(self):
        if self._tried:
            return self._ocr
        with self._lock:
            if self._tried:
                return self._ocr
            self._tried = True
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore

                self._ocr = RapidOCR()
                log.info("RapidOCR loaded")
            except Exception as exc:  # noqa: BLE001
                log.warning("RapidOCR unavailable: %s", exc)
                self._ocr = None
            return self._ocr

    def available(self) -> bool:
        return self._ensure() is not None

    def recognize(self, image_path: str) -> Optional[OcrOutput]:
        ocr = self._ensure()
        if ocr is None:
            return None
        try:
            result, _elapse = ocr(image_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("RapidOCR failed: %s", exc)
            return None
        lines: List[str] = []
        confs: List[float] = []
        # result is a list of [box, text, score] (or None when nothing found).
        for entry in (result or []):
            try:
                txt = entry[1]
                score = float(entry[2])
                if txt and txt.strip():
                    lines.append(txt)
                    confs.append(score)
            except (IndexError, TypeError, ValueError):
                continue
        mean_conf = sum(confs) / len(confs) if confs else 0.0
        return OcrOutput("\n".join(lines), mean_conf, "rapidocr")

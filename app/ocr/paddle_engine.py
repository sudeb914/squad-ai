"""PaddleOCR wrapper (primary OCR engine, lazy-loaded, optional)."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import List, Optional

from ..utils.logging import get_logger

log = get_logger("ocr.paddle")


@dataclass
class OcrOutput:
    text: str
    confidence: float  # 0..1 mean line confidence
    engine: str


class PaddleEngine:
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
                from paddleocr import PaddleOCR  # type: ignore

                self._ocr = PaddleOCR(use_angle_cls=True, lang="en",
                                      show_log=False)
                log.info("PaddleOCR loaded")
            except Exception as exc:  # noqa: BLE001
                log.warning("PaddleOCR unavailable: %s", exc)
                self._ocr = None
            return self._ocr

    def available(self) -> bool:
        return self._ensure() is not None

    def recognize(self, image_path: str) -> Optional[OcrOutput]:
        ocr = self._ensure()
        if ocr is None:
            return None
        result = ocr.ocr(image_path, cls=True)
        lines: List[str] = []
        confs: List[float] = []
        for page in (result or []):
            for entry in (page or []):
                try:
                    txt, conf = entry[1][0], float(entry[1][1])
                    lines.append(txt)
                    confs.append(conf)
                except (IndexError, TypeError, ValueError):
                    continue
        mean_conf = sum(confs) / len(confs) if confs else 0.0
        return OcrOutput("\n".join(lines), mean_conf, "paddleocr")

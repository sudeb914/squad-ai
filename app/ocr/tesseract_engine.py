"""Tesseract wrapper (fallback OCR engine, optional)."""
from __future__ import annotations

from typing import Optional

from .paddle_engine import OcrOutput
from ..utils.logging import get_logger

log = get_logger("ocr.tess")


class TesseractEngine:
    def available(self) -> bool:
        try:
            import pytesseract  # type: ignore  # noqa: F401
            from PIL import Image  # type: ignore  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def recognize(self, image_path: str) -> Optional[OcrOutput]:
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore
        except Exception as exc:  # noqa: BLE001
            log.warning("Tesseract unavailable: %s", exc)
            return None
        try:
            data = pytesseract.image_to_data(
                Image.open(image_path),
                output_type=pytesseract.Output.DICT)
            words, confs = [], []
            for txt, conf in zip(data["text"], data["conf"]):
                if txt.strip():
                    words.append(txt)
                    try:
                        c = float(conf)
                        if c >= 0:
                            confs.append(c / 100.0)
                    except ValueError:
                        pass
            mean_conf = sum(confs) / len(confs) if confs else 0.0
            return OcrOutput(" ".join(words), mean_conf, "tesseract")
        except Exception as exc:  # noqa: BLE001
            log.warning("Tesseract OCR failed: %s", exc)
            return None

"""Optional image preprocessing to improve OCR (grayscale, upscale, threshold).

Uses Pillow if available; otherwise returns the image path unchanged. Never a
hard dependency.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..utils.logging import get_logger
from ..utils.paths import cache_dir

log = get_logger("ocr.pre")


def preprocess(image_path: str) -> str:
    """Return a path to a preprocessed image (or the original on failure)."""
    try:
        from PIL import Image, ImageOps  # type: ignore
    except Exception:  # noqa: BLE001
        return image_path
    try:
        img = Image.open(image_path).convert("L")
        img = ImageOps.autocontrast(img)
        w, h = img.size
        if max(w, h) < 1000:  # upscale small captures
            scale = 2
            img = img.resize((w * scale, h * scale))
        out = cache_dir() / "ocr_pre.png"
        img.save(out)
        return str(out)
    except Exception as exc:  # noqa: BLE001
        log.debug("preprocess skipped: %s", exc)
        return image_path

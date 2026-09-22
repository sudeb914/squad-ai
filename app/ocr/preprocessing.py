"""Image preprocessing to improve OCR accuracy.

Grayscale → autocontrast → upscale small captures → sharpen. Bigger, higher-
contrast, sharper text is markedly easier for OCR engines to read. Uses Pillow
if available; otherwise returns the image path unchanged (never a hard
dependency, never fails the pipeline).
"""
from __future__ import annotations

from ..utils.logging import get_logger
from ..utils.paths import cache_dir

log = get_logger("ocr.pre")

# Upscale until the longest side reaches this, so small on-screen text becomes
# large enough for the recognizer. Capped so huge screenshots aren't blown up.
_TARGET_LONG_SIDE = 1800
_MAX_SCALE = 3.0


def preprocess(image_path: str) -> str:
    """Return a path to a preprocessed image (or the original on failure)."""
    try:
        from PIL import Image, ImageFilter, ImageOps  # type: ignore
    except Exception:  # noqa: BLE001
        return image_path
    try:
        img = Image.open(image_path)
        # Flatten transparency onto white so alpha PNGs don't turn text black.
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img)
        img = img.convert("L")               # grayscale
        img = ImageOps.autocontrast(img, cutoff=1)

        w, h = img.size
        long_side = max(w, h)
        if long_side > 0 and long_side < _TARGET_LONG_SIDE:
            scale = min(_MAX_SCALE, _TARGET_LONG_SIDE / long_side)
            if scale > 1.01:
                img = img.resize((int(w * scale), int(h * scale)),
                                 Image.LANCZOS)

        # Sharpen edges of the (now upscaled) glyphs.
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140,
                                                 threshold=2))

        out = cache_dir() / "ocr_pre.png"
        img.save(out)
        return str(out)
    except Exception as exc:  # noqa: BLE001
        log.debug("preprocess skipped: %s", exc)
        return image_path

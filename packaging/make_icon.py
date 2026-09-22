"""Generate the Squad AI app icon (PNG + .ico + .icns).

Draws a rounded-square icon with the app's purple gradient, a white spark and a
check mark (the app answers questions). Run from the project root:

    python packaging/make_icon.py

Produces packaging/AppIcon.png, packaging/AppIcon.ico and (on macOS)
packaging/AppIcon.icns. Requires Pillow. Safe to re-run; deterministic output.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024
TOP = (168, 85, 247)     # #a855f7
BOTTOM = (124, 58, 237)  # #7c3aed
WHITE = (255, 255, 255, 255)


def _rounded_gradient(size: int) -> Image.Image:
    # vertical gradient
    grad = Image.new("RGB", (size, size), TOP)
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    img = grad.convert("RGBA")
    # rounded-corner mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 0.23), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _draw_mark(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    s = img.size[0]
    # check mark (bold, rounded)
    lw = int(s * 0.085)
    p1 = (s * 0.30, s * 0.53)
    p2 = (s * 0.45, s * 0.68)
    p3 = (s * 0.72, s * 0.36)
    d.line([p1, p2, p3], fill=WHITE, width=lw, joint="curve")
    for p in (p1, p2, p3):
        d.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2],
                  fill=WHITE)
    # small four-point sparkle top-right
    cx, cy, r = s * 0.72, s * 0.28, s * 0.06
    d.polygon([(cx, cy - r), (cx + r * 0.32, cy - r * 0.32),
               (cx + r, cy), (cx + r * 0.32, cy + r * 0.32),
               (cx, cy + r), (cx - r * 0.32, cy + r * 0.32),
               (cx - r, cy), (cx - r * 0.32, cy - r * 0.32)], fill=WHITE)


def main() -> int:
    base = _rounded_gradient(SIZE)
    _draw_mark(base)

    png = os.path.join(HERE, "AppIcon.png")
    base.save(png)
    print("wrote", png)

    # Windows .ico with the standard sizes
    ico = os.path.join(HERE, "AppIcon.ico")
    base.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                          (64, 64), (128, 128), (256, 256)])
    print("wrote", ico)

    # macOS .icns via iconutil when available (best quality)
    if sys.platform == "darwin":
        try:
            _make_icns(base, os.path.join(HERE, "AppIcon.icns"))
        except Exception as exc:  # noqa: BLE001
            print("icns skipped:", exc)
    return 0


def _make_icns(base: Image.Image, out: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "AppIcon.iconset")
        os.makedirs(iconset)
        for sz in (16, 32, 64, 128, 256, 512, 1024):
            base.resize((sz, sz), Image.LANCZOS).save(
                os.path.join(iconset, f"icon_{sz}x{sz}.png"))
            if sz <= 512:
                base.resize((sz * 2, sz * 2), Image.LANCZOS).save(
                    os.path.join(iconset, f"icon_{sz}x{sz}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out],
                       check=True)
        print("wrote", out)


if __name__ == "__main__":
    raise SystemExit(main())

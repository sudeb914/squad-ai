"""Screenshot capture, isolated from the UI and per-platform.

Order of preference:
  * macOS: the built-in ``screencapture`` CLI (no dependencies, respects the OS
    screen-recording permission — we detect/report permission problems).
  * ``mss`` if installed (fast, cross-platform).
  * Pillow's ``ImageGrab`` (Windows/macOS).

Region coordinates are global screen pixels. Captures are written to the cache
dir; images never leave the machine.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from .region_selector import Region
from ..utils.logging import get_logger
from ..utils.paths import cache_dir

log = get_logger("capture")


class ScreenshotError(RuntimeError):
    pass


class ScreenshotManager:
    def _out_path(self) -> Path:
        return cache_dir() / f"capture_{int(time.time() * 1000)}.png"

    def capture_region(self, region: Optional[Region]) -> str:
        """Capture ``region`` (or the full screen when None). Returns file path."""
        out = self._out_path()
        if sys.platform == "darwin":
            return self._capture_macos(region, out)
        if self._try_mss(region, out):
            return str(out)
        if self._try_pillow(region, out):
            return str(out)
        raise ScreenshotError(
            "No screenshot backend available. Install 'mss' or Pillow.")

    def capture_interactive(self) -> Optional[str]:
        """Let the user drag a selection using the OS's native tool.

        Returns the file path, or ``None`` if the user cancelled (Esc). This is
        far more reliable than a custom overlay and uses the crosshair the user
        already knows. Blocks until the user finishes selecting — call it from a
        worker thread so the GUI stays responsive.
        """
        out = self._out_path()
        if sys.platform == "darwin":
            # -i interactive, -x silent. Exits 0 with no file if cancelled.
            try:
                subprocess.run(["screencapture", "-i", "-x", str(out)],
                               capture_output=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ScreenshotError(f"screencapture failed: {exc}") from exc
            return str(out) if out.exists() else None
        # Non-macOS: no native region picker here — capture the full screen.
        if self._try_mss(None, out) or self._try_pillow(None, out):
            return str(out)
        raise ScreenshotError(
            "No screenshot backend available. Install 'mss' or Pillow.")

    # -- macOS ------------------------------------------------------------
    def _capture_macos(self, region: Optional[Region], out: Path) -> str:
        cmd = ["screencapture", "-x"]  # -x = no capture sound
        if region and region.valid():
            cmd += ["-R", f"{region.x},{region.y},{region.w},{region.h}"]
        cmd.append(str(out))
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ScreenshotError(f"screencapture failed: {exc}") from exc
        if proc.returncode != 0 or not out.exists():
            raise ScreenshotError(
                "screencapture failed. On macOS, grant Screen Recording "
                "permission to this app in System Settings > Privacy & "
                "Security > Screen Recording.")
        return str(out)

    # -- mss --------------------------------------------------------------
    def _try_mss(self, region: Optional[Region], out: Path) -> bool:
        try:
            import mss  # type: ignore
            import mss.tools  # type: ignore
        except Exception:  # noqa: BLE001
            return False
        with mss.mss() as sct:
            if region and region.valid():
                bbox = {"left": region.x, "top": region.y,
                        "width": region.w, "height": region.h}
            else:
                # monitors[0] is the union of *all* displays; the selection
                # overlay is sized to the primary screen only, so grab the
                # primary monitor (monitors[1]) to keep them aligned on
                # multi-monitor setups. Fall back to the union if unavailable.
                bbox = sct.monitors[1] if len(sct.monitors) > 1 \
                    else sct.monitors[0]
            img = sct.grab(bbox)
            mss.tools.to_png(img.rgb, img.size, output=str(out))
        return out.exists()

    # -- Pillow -----------------------------------------------------------
    def _try_pillow(self, region: Optional[Region], out: Path) -> bool:
        try:
            from PIL import ImageGrab  # type: ignore
        except Exception:  # noqa: BLE001
            return False
        bbox = None
        if region and region.valid():
            bbox = (region.x, region.y, region.x + region.w,
                    region.y + region.h)
        img = ImageGrab.grab(bbox=bbox)
        img.save(out)
        return out.exists()

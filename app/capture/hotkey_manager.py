"""Global hotkey registration (optional, via pynput).

Configurable key (default F8). If ``pynput`` is unavailable, hotkeys are simply
disabled and the UI's on-screen Capture button remains the entry point — the app
never fails to start because of this.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..utils.logging import get_logger

log = get_logger("hotkey")


class HotkeyManager:
    def __init__(self) -> None:
        self._listener = None
        self._callback: Optional[Callable[[], None]] = None

    def available(self) -> bool:
        try:
            import pynput  # type: ignore  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def register(self, hotkey: str, callback: Callable[[], None]) -> bool:
        """Register ``hotkey`` (e.g. "F8", "<ctrl>+<shift>+s"). Returns success."""
        self.stop()
        try:
            from pynput import keyboard  # type: ignore
        except Exception as exc:  # noqa: BLE001
            log.warning("Global hotkey disabled (pynput missing): %s", exc)
            return False
        combo = self._to_pynput(hotkey)
        try:
            self._callback = callback
            self._listener = keyboard.GlobalHotKeys({combo: self._fire})
            self._listener.start()
            log.info("Registered global hotkey %s", hotkey)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to register hotkey %s: %s", hotkey, exc)
            return False

    def _fire(self) -> None:
        if self._callback:
            try:
                self._callback()
            except Exception as exc:  # noqa: BLE001
                log.error("Hotkey callback error: %s", exc)

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:  # noqa: BLE001
                pass
            self._listener = None

    @staticmethod
    def _to_pynput(hotkey: str) -> str:
        hk = hotkey.strip()
        if len(hk) >= 2 and hk[0].upper() == "F" and hk[1:].isdigit():
            return f"<{hk.lower()}>"
        return hk

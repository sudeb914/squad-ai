"""Squad AI entry point.

Lazy startup: build lightweight services (DB/config/logging) first so the window
appears quickly; OCR and embedding models load on demand in the background. The
app runs fully without a DeepSeek key — only the AI fallback is disabled.
"""
from __future__ import annotations

import sys
import traceback

from .services import Services
from .utils.logging import get_logger
from .utils.paths import logs_dir

log = get_logger("main")


def _icon_file() -> str:
    """Locate the bundled app icon (PNG) in both frozen and source runs."""
    import os

    candidates = []
    base = getattr(sys, "_MEIPASS", None)          # PyInstaller bundle root
    if base:
        candidates.append(os.path.join(base, "AppIcon.png"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "..", "packaging", "AppIcon.png"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _apply_app_icon(app) -> None:
    path = _icon_file()
    if not path:
        return
    try:
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(path))
    except Exception:  # noqa: BLE001
        pass


def _install_crash_handler() -> None:
    """Log *and show* uncaught exceptions instead of silently aborting.

    In a packaged (windowed, no-console) build a Python exception raised inside
    a Qt slot otherwise tears the process down with no message — which looked
    like "the app just closes when I click the screenshot button". We write the
    traceback to a crash log and pop up a dialog so the error is visible and the
    app keeps running when possible.
    """
    crash_log = logs_dir() / "crash.log"

    def _hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(crash_log, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception:  # noqa: BLE001
            pass
        log.error("Uncaught exception:\n%s", text)
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None, "Squad AI — unexpected error",
                "Something went wrong:\n\n"
                f"{exc_type.__name__}: {exc}\n\n"
                f"Full details were saved to:\n{crash_log}")
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = _hook


def run_gui() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        print("PySide6 is required for the GUI. Install with:\n"
              "  pip install PySide6\n"
              f"(import error: {exc})", file=sys.stderr)
        return 2

    from .ui.main_window import MainWindow
    from .ui.theme import QSS

    svc = Services()
    if not svc.has_api_key():
        log.info("No DeepSeek API key configured; local features fully active.")

    app = QApplication(sys.argv)
    app.setApplicationName("Squad AI")
    _apply_app_icon(app)
    app.setStyleSheet(QSS)  # theme dialogs/message boxes too
    _install_crash_handler()

    window = MainWindow(svc)
    window.show()
    code = app.exec()
    svc.close()
    return code


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())

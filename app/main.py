"""Squad AI entry point.

Lazy startup: build lightweight services (DB/config/logging) first so the window
appears quickly; OCR and embedding models load on demand in the background. The
app runs fully without a DeepSeek key — only the AI fallback is disabled.
"""
from __future__ import annotations

import sys

from .services import Services
from .utils.logging import get_logger

log = get_logger("main")


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
    app.setStyleSheet(QSS)  # theme dialogs/message boxes too

    window = MainWindow(svc)
    window.show()
    code = app.exec()
    svc.close()
    return code


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())

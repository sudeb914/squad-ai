"""Top-level launcher (entry point for PyInstaller and `python run.py`).

Kept separate from ``app/main.py`` because that module uses package-relative
imports; importing it as ``app.main`` here resolves them correctly.
"""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())

# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Squad AI (Windows + macOS Apple Silicon).

Build from the project root:

    pip install pyinstaller
    pyinstaller packaging/squad_ai.spec

Heavy optional packages (PaddleOCR, sentence-transformers, FAISS) are bundled
only if they are installed in the build environment; otherwise the produced app
simply runs without those features (graceful degradation). Downloaded ML models
are NOT bundled — they are fetched to the user cache dir on first use (see
packaging/MODELS.md).
"""
import sys

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas, binaries, hiddenimports = [], [], []

# Bundle optional deps when present; skip silently when not installed.
for _pkg in ("paddleocr", "paddle", "sentence_transformers", "faiss",
             "rapidfuzz", "keyring", "pynput", "mss"):
    try:
        d, b, h = collect_all(_pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:  # noqa: BLE001
        pass

a = Analysis(
    ["../run.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["app"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SquadAI",
    debug=False,
    strip=False,
    upx=True,
    console=False,  # windowed GUI app
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=True, name="SquadAI",
)

# macOS: also produce a .app bundle (Apple Silicon when built on arm64).
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Squad AI.app",
        bundle_identifier="com.squadai.desktop",
        info_plist={
            "CFBundleName": "Squad AI",
            "CFBundleDisplayName": "Squad AI",
            "NSHighResolutionCapable": True,
            # Screen Recording permission prompt text for region capture.
            "NSCameraUsageDescription": "Not used.",
        },
    )

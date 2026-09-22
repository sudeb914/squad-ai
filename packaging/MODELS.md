# Model & runtime dependencies (packaging notes)

Squad AI keeps **application code** separate from **downloaded ML models**. The
packaged app does *not* embed multi-hundred-MB models; they are fetched to the
user cache directory on first use and reused thereafter.

## Where models are stored

`<user cache>/com.squadai.desktop/models/` — e.g. on macOS
`~/Library/Caches/com.squadai.desktop/models/`. This survives app upgrades.

## Models used (all local, all optional)

| Purpose | Component | First-run behavior |
|---|---|---|
| Semantic search | `sentence-transformers/all-MiniLM-L6-v2` (~90 MB) | downloaded once to the cache dir |
| OCR (primary) | PaddleOCR English detection + recognition models (~10–20 MB) | downloaded once by PaddleOCR |
| OCR (fallback) | Tesseract | requires the system `tesseract` binary (`brew install tesseract` / installer on Windows) |

After first download the app works **offline**, except for the DeepSeek fallback
which needs internet only when a question can't be resolved locally.

## Build environment guidance

- Build on the **target OS/arch** (PyInstaller does not cross-compile). For
  Apple Silicon, build on an arm64 Mac; for Windows, build on Windows.
- Install everything in `requirements.txt` in the build venv so `collect_all`
  in `squad_ai.spec` can bundle the optional packages' code. If an optional
  package is absent at build time, the app still runs — just without that
  feature.
- `paddlepaddle` is large and platform-specific; if you don't need OCR in a
  given build, omit it and Tesseract/manual entry remain available.

## Reducing size

- Ship without `paddlepaddle`/`paddleocr` and rely on Tesseract for OCR.
- FAISS is optional; the app uses a pure-python cosine search if it's absent.

# Squad AI — Local-First Survey Assistant

A desktop assistant that answers survey questions **locally first, AI last**.
DeepSeek is a fallback engine, not the primary answer engine. The design goal is
accuracy + very low API cost.

## Philosophy

```
INPUT → OCR → normalize → parse question/options → determine type
      → deterministic local resolution (profile facts, numeric ranges, options)
      → exact memory → fuzzy memory → semantic memory
      → DeepSeek fallback (ONLY if local confidence is insufficient; ONE call)
      → return answer → store useful result
```

There is exactly **one** path to the AI provider (`AnswerEngine._try_api`), every
call is logged to `api_usage`, and there is **no** automatic retry/verification
loop.

## Requirements & optional features

The deterministic **core and the full test suite run on the Python standard
library alone** — no third-party packages required. Everything else is optional
and lazily imported; each feature degrades gracefully if its dependency is
missing:

| Feature | Package | Fallback if missing |
|---|---|---|
| Desktop GUI | `PySide6` | Use the CLI (`python -m app.cli`) |
| Fuzzy matching | `rapidfuzz` | stdlib `difflib` |
| Semantic search | `sentence-transformers` (+ `faiss-cpu`) | exact/fuzzy only; pure-python cosine |
| OCR (primary) | `paddleocr` + `paddlepaddle` | Tesseract, else type/upload |
| OCR (fallback) | `pytesseract` + tesseract binary | — |
| Screenshots | macOS built-in `screencapture` (0 deps); `mss`/`Pillow` elsewhere | — |
| Networking | `httpx` | stdlib `urllib` |
| Secure key storage | `keyring` | 0600-perms file in the data dir |
| Global hotkey | `pynput` | on-screen Capture button |

Install everything for the full experience:

```bash
pip install -r requirements.txt
```

## Run

Desktop app:

```bash
python -m app.main
```

Headless CLI (same AnswerEngine, no GUI needed):

```bash
python -m app.cli profile set age 39
python -m app.cli profile set employment_status "Full-time employed"
python -m app.cli key set sk-...                       # stored via OS keyring
python -m app.cli ask "What is your age?"
python -m app.cli ask "Which age range?" -o "18-24" -o "25-34" -o "35-44"
python -m app.cli ask "Describe your weekend" --no-api
python -m app.cli usage
```

## Tests

```bash
python -m unittest discover -s tests
```

Tests explicitly assert that locally solvable questions trigger **0** API calls
and that an unresolved question triggers at most **1**.

## Data location

User data lives in the OS application-data directory keyed off the stable
identifier `com.squadai.desktop` (not the display name), so renaming the app or
upgrading it does not lose the database. Set `SQUAD_AI_HOME` to override (used by
tests). Code / user-data / cache / logs are kept in separate trees.

## Architecture

```
app/
  main.py              GUI entry (lazy startup)
  cli.py               headless CLI
  services.py          dependency-injection hub (builds engine + repos)
  core/                answer_engine, question_parser, option_parser,
                       rule_engine, numeric_range, profile_resolver,
                       confidence, normalization, context_builder, models
  retrieval/           exact / fuzzy / semantic matchers, embeddings, vector store
  memory/              answer_memory (what to persist), import_export
  providers/           base_provider (interface), deepseek_provider
  ocr/                 paddle / tesseract engines, ocr_manager, preprocessing
  capture/             screenshot_manager, region_selector, hotkey_manager
  database/            db, migrations, repositories/*
  security/            credential_manager (keyring)
  ui/                  main_window + chat/profile/memory/usage/settings views
  utils/               config (all thresholds), paths, logging
```

Swapping providers (Gemini/OpenAI/…) only requires a new `BaseAIProvider`
subclass and a one-line change in `Services.build_provider`; the answer engine
is untouched.

## Cost controls (non-negotiable)

- One centralized AI path; UI components cannot call the provider directly.
- Only the top few relevant profile fields + relevant reference chunks are sent
  — never the whole profile, reference corpus, or memory.
- Static system prompt first (prompt-cache friendly), temperature 0.1, tiny
  output caps (120 tokens for simple questions; 600 hard ceiling).
- All thresholds live in `app/utils/config.py`.

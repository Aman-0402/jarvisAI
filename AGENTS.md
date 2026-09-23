# Project: J.A.R.V.I.S. — Local AI Voice Assistant

Fully local, agentic AI voice assistant. Wake word → STT → LLM (tool-calling) → TTS. Web UI (Iron Man HUD). Windows-only.

## Tech Stack
- **Runtime**: Python 3.11+ (3.12 in dev), venv (`.venv`)
- **Wake word**: openWakeWord (ONNX), custom `hey_jarvis` model
- **STT**: faster-whisper (tiny/small/medium/large-v3, CPU or CUDA)
- **TTS**: Kokoro-82M (local CPU)
- **LLM**: Ollama (default) or any OpenAI-compatible API (Gemini, NVIDIA NIM, LM Studio, etc.) via `openai` SDK
- **Web UI**: FastAPI + WebSocket + uvicorn, served at `http://localhost:7860`
- **Memory**: SQLite + ChromaDB (semantic search)
- **Desktop automation/vision**: PyAutoGUI + Pillow screenshots → Windows PowerShell OCR
- **Web search**: ddgs (DuckDuckGo)
- **Tests**: pytest + pytest-mock
- **Shell**: PowerShell (Windows 11)
- **GPU**: optional NVIDIA CUDA. STT (faster-whisper) runs full-GPU when `stt.device: cuda`. Ollama auto-splits GPU/CPU layers by available VRAM — a 4GB card only partially offloads an 8B Q4 model (expect ~40/60 GPU/CPU split), still faster than pure CPU. Check actual split with `ollama ps`.

## Shell Commands
```powershell
install.bat                        # venv + deps + ONNX model download
start.bat                          # activates venv, runs python -m jarvis.main
pytest                             # run tests
ollama serve                       # required if using local Ollama provider
ollama pull qwen3:8b                # pull default model
pyinstaller jarvis.spec --clean   # build standalone dist/Jarvis/Jarvis.exe
```

## Project Structure
```
jarvisAI/
├── config.yaml              # All runtime config (wake word, stt, llm, tts, memory, tools) — gitignored, holds live secrets (API keys)
├── config.yaml.example      # Committed template, no secrets — install.bat copies this to config.yaml if missing
├── install.bat / start.bat
├── requirements.txt         # deps
├── jarvis/
│   ├── main.py              # Core orchestrator: pipeline, abort/mute, keyboard listener (Esc/F2/Insert), event bus
│   ├── wake.py               # Wake word detection (openWakeWord)
│   ├── stt.py                 # Speech-to-text (faster-whisper), speech-gated silence detection
│   ├── tts.py                 # Text-to-speech (Kokoro), polling-based interrupt
│   ├── web.py                  # FastAPI + WebSocket backend: provider CRUD, settings CRUD, mute API, serves /assets
│   ├── tray.py                 # System tray icon, menu (Open/Stop/Start with Windows/Exit), autostart
│   ├── context.py             # Sliding window context manager, auto-summarization
│   ├── memory.py               # Long-term memory: SQLite + ChromaDB fact extraction/search
│   ├── llm.py                   # Internal LLM calls (e.g. summarization)
│   ├── widget.py                # Floating status widget: position persistence, state mapping, window creation
│   ├── assets/                   # App logo/icon set (favicon.png, favicon-32.png, icon.ico, tray_icon.png, icon_master.png)
│   ├── static/index.html        # Iron Man HUD web UI (single-file)
│   └── tools/
│       ├── router.py            # Tool registry + dispatch (31 tools)
│       ├── desktop.py            # Screen OCR, mouse/keyboard, window control
│       ├── app_control.py         # App launching (30+ mapped), URL opening
│       ├── web_search.py           # DuckDuckGo search, weather, page fetch
│       ├── system.py               # Volume, brightness, clipboard, power, notifications
│       ├── file_ops.py              # Sandboxed file read/write/list (allowed_paths)
│       ├── code_exec.py             # Python sandbox exec (10s timeout)
│       └── subagent.py               # delegate_task → local LLM for subtasks
├── docs/superpowers/specs/   # Design specs (brainstorming skill output)
├── docs/superpowers/plans/   # Implementation plans (writing-plans skill output)
└── tests/                    # pytest unit tests
```

## Key Conventions
- **Config**: all settings in `config.yaml` (gitignored — holds live API keys); also editable live via web UI Config tab (`PUT /api/settings`). Fresh clones get `config.yaml.example` copied by `install.bat`. **Never commit `config.yaml`** — it will contain real provider API keys once any are added via the Config tab.
- **Providers**: LLM providers are pluggable — `type: ollama` or `type: openai` (any OpenAI-compatible base_url — this covers Gemini via `https://generativelanguage.googleapis.com/v1beta/openai/`, NVIDIA NIM, LM Studio, etc.). Managed via `/api/providers` CRUD; active provider can't be deleted.
- **Tool calling**: agentic loop, up to 15 sequential tool calls per request. New tools register in `jarvis/tools/router.py` and live in their own `jarvis/tools/*.py` module.
- **Abort/mute**: global abort via Esc key, voice "stop", web "stop"/ABORT button — routed through `main.py`'s `abort_all()`. Mute toggled via Insert key or `/api/mute`.
- **File ops sandboxing**: `read_file`/`write_file`/`list_files` restricted to `tools.allowed_paths` in `config.yaml` (default `~/Documents`, `~/Desktop`). Never widen this without explicit ask.
- **Memory**: facts persisted to SQLite (`jarvis/data/memory.db`) + ChromaDB (`jarvis/data/chroma`) for semantic recall; top_k configurable.
- **All local by default** — no data leaves the machine unless a cloud LLM provider is explicitly configured.
- **Launch mode**: `start.bat`/`python -m jarvis.main` opens a hidden native window (pywebview) + tray icon, not a browser tab. Tray menu: Open Jarvis, Stop (mute), Start with Windows (autostart toggle), Exit (full quit). Autostart is opt-in, off by default.
- **Packaging**: `pyinstaller jarvis.spec --clean` builds a standalone `dist/Jarvis/Jarvis.exe` (onedir — folder + exe, not a single-file build; torch/ctranslate2 make onefile's per-launch extraction too slow). `jarvis/paths.py`'s `get_base_dir()` makes `config.yaml`/`jarvis/data/` resolve next to the exe when frozen vs. the repo root when running from source — any new module reading `config.yaml` must use `get_base_dir()`, not `Path(__file__).parent`, or it'll break in the packaged build. PyInstaller onedir puts bundled `datas` (e.g. `config.yaml.example`) in `dist/Jarvis/_internal/`, not next to the exe — `jarvis/paths.py`'s `ensure_config_exists()` checks `get_base_dir()` first, then falls back to `sys._MEIPASS` to find it there. On a truly fresh machine with no `config.yaml`, `main.py` calls `ensure_config_exists()` on import to seed one from the bundled example before anything tries to read it.
- **Ollama startup check**: `main()` calls `is_ollama_reachable(base_url)` (in `jarvis/main.py`) before the pipeline starts, only when the active provider is `type: ollama`. Prints and broadcasts a friendly "Ollama not detected" message instead of letting the first tool call hit a raw connection-refused error.
- **Windowed-build (`console=False`) gotcha — resolved**: `sys.stdout`/`sys.stderr` are `None` in a windowed PyInstaller build (no console to attach to). `uvicorn`'s logging setup calls `sys.stderr.isatty()` at startup and raised `AttributeError`, silently killing the web server's daemon thread — no port ever bound, no visible error, the exe just sat idle forever. Fixed in `pyinstaller_entry.py`: redirects `stdout`/`stderr` to `os.devnull` before any other import, since that must happen before `jarvis.main`/`jarvis.web` touch those streams. `jarvis/main.py` also now sets `threading.excepthook` to log any uncaught daemon-thread exception to `crash.log` next to the exe — without this, a dying daemon thread (web server, wake-word loop) is otherwise invisible in a windowed build.
- **Startup splash screen**: `jarvis.spec` adds a PyInstaller native `Splash` (`jarvis/assets/splash.png`) that appears immediately on double-click and stays up until voice is genuinely ready — closed via `pyi_splash.close()` in `jarvis/wake.py`, right after the wake-word model loads and the mic opens (guarded by `sys.frozen`, so source runs are unaffected). See `docs/superpowers/specs/2026-09-23-splash-screen-design.md`.
- **Bundled data-file packages**: beyond the `collect_all` list's ML backends, `en_core_web_sm` (spacy model) and `misaki` (Kokoro TTS's tokenizer) are regular installed packages with their own data files that PyInstaller's default analysis misses — both are in `jarvis.spec`'s `collect_all` loop. Missing either one crashes the startup TTS greeting inside `_wake_loop`, which kills that thread *before* `listen_for_wake_word()` ever runs — voice never starts, and (with the splash screen above) the splash hangs forever instead of closing. If a future dependency does anything with `importlib.resources`/bundled data files and TTS/wake-word breaks in the packaged build only, check `crash.log` first and add the package to this list.
- **Floating status widget**: `jarvis/widget.py` creates a second, small, frameless/transparent/always-on-top pywebview window (`jarvis/static/widget.html`) showing Jarvis's live state as an animated ring. Updates via the same in-process `register_event_listener()` hook `jarvis/web.py` uses for the WebSocket HUD — no new plumbing, maps `_broadcast()`'s status strings ("Ready."/"Wake."/"Listening..."/"Thinking..."/"Speaking...") through `status_to_state()`. Position persists to `jarvis/data/widget_position.json` (via `get_base_dir()`), polled from JS every 2s rather than relying on a native "window moved" event (unreliable across pywebview's backends). Defaults to the screen's bottom-right corner on first run. Created in `main()` *before* the main window's `_on_closing` handler is defined (that closure destroys the widget too, but only on real exit via tray "Exit", not on hide-to-tray) — if you touch that ordering, the widget gets orphaned on exit. `widget.html`'s path is resolved via `Path(__file__).parent / "static" / "widget.html"` (same pattern as `jarvis/web.py`'s `_STATIC_DIR`), NOT `get_base_dir()` — that's the bug from the packaging note above (bundled `jarvis/static/` lands in `_internal/` when frozen, `get_base_dir()` points at the exe's own dir instead). `get_base_dir()` is still correct for `widget_position.json`, which is genuinely exe-adjacent user data. See `docs/superpowers/specs/2026-09-23-floating-status-widget-design.md`.

## REST API (jarvis/web.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/providers` | List all providers with full details |
| POST | `/api/providers/{key}` | Set active provider |
| PUT | `/api/providers/{key}` | Add/update provider |
| DELETE | `/api/providers/{key}` | Delete provider (not active one) |
| GET | `/api/settings` | All config (tts, stt, wake_word, llm temp, tools) |
| PUT | `/api/settings` | Partial update of any settings section |
| GET | `/api/mute` | Get mute state |
| POST | `/api/mute` | Toggle mute |
| WS | `/ws` | Real-time events: chat, interrupt, tool calls, responses |

## Environment / Runtime Requirements
- Ollama running locally (`ollama serve` + pulled model) **or** OpenAI-compatible provider configured
- CUDA optional for STT (`stt.device: cuda`); auto-falls back to CPU if unavailable
- `config.yaml` is gitignored — `config.yaml.example` (committed, no secrets) is the template; `install.bat` copies it on fresh installs if `config.yaml` is missing

## Dev Notes
- `python -m jarvis.main` is the actual entrypoint `start.bat` runs.
- Wake word mic auto-pauses during STT recording to avoid mic conflicts.
- Web UI console: check browser F12 for `[WS]` log messages when debugging WebSocket issues.

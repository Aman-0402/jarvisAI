# Project: J.A.R.V.I.S. — Local AI Voice Assistant

Fully local, agentic AI voice assistant. Wake word → STT → LLM (tool-calling) → TTS. Web UI (Iron Man HUD). Windows-only.

## Tech Stack
- **Runtime**: Python 3.11+ (3.12 in dev), venv (`.venv`)
- **Wake word**: openWakeWord (ONNX), custom `hey_jarvis` model
- **STT**: faster-whisper (tiny/small/medium/large-v3, CPU or CUDA)
- **TTS**: Kokoro-82M (local CPU)
- **LLM**: Ollama (default) or any OpenAI-compatible API (NVIDIA NIM, LM Studio, etc.) via `openai` SDK
- **Web UI**: FastAPI + WebSocket + uvicorn, served at `http://localhost:7860`
- **Memory**: SQLite + ChromaDB (semantic search)
- **Desktop automation/vision**: PyAutoGUI + Pillow screenshots → Windows PowerShell OCR
- **Web search**: ddgs (DuckDuckGo)
- **Tests**: pytest + pytest-mock
- **Shell**: PowerShell (Windows 11)

## Shell Commands
```powershell
install.bat                        # venv + deps + ONNX model download
start.bat                          # activates venv, runs python -m jarvis.main
pytest                             # run tests
ollama serve                       # required if using local Ollama provider
ollama pull qwen3:8b                # pull default model
```

## Project Structure
```
jarvisAI/
├── config.yaml              # All runtime config (wake word, stt, llm, tts, memory, tools)
├── install.bat / start.bat
├── requirements.txt         # 18 deps
├── jarvis/
│   ├── main.py              # Core orchestrator: pipeline, abort/mute, keyboard listener (Esc/F2/Insert), event bus
│   ├── wake.py               # Wake word detection (openWakeWord)
│   ├── stt.py                 # Speech-to-text (faster-whisper), speech-gated silence detection
│   ├── tts.py                 # Text-to-speech (Kokoro), polling-based interrupt
│   ├── web.py                  # FastAPI + WebSocket backend: provider CRUD, settings CRUD, mute API
│   ├── context.py             # Sliding window context manager, auto-summarization
│   ├── memory.py               # Long-term memory: SQLite + ChromaDB fact extraction/search
│   ├── llm.py                   # Internal LLM calls (e.g. summarization)
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
└── tests/                    # pytest unit tests
```

## Key Conventions
- **Config**: all settings in `config.yaml`; also editable live via web UI Config tab (`PUT /api/settings`).
- **Providers**: LLM providers are pluggable — `type: ollama` or `type: openai` (any OpenAI-compatible base_url). Managed via `/api/providers` CRUD; active provider can't be deleted.
- **Tool calling**: agentic loop, up to 15 sequential tool calls per request. New tools register in `jarvis/tools/router.py` and live in their own `jarvis/tools/*.py` module.
- **Abort/mute**: global abort via Esc key, voice "stop", web "stop"/ABORT button — routed through `main.py`'s `abort_all()`. Mute toggled via Insert key or `/api/mute`.
- **File ops sandboxing**: `read_file`/`write_file`/`list_files` restricted to `tools.allowed_paths` in `config.yaml` (default `~/Documents`, `~/Desktop`). Never widen this without explicit ask.
- **Memory**: facts persisted to SQLite (`jarvis/data/memory.db`) + ChromaDB (`jarvis/data/chroma`) for semantic recall; top_k configurable.
- **All local by default** — no data leaves the machine unless a cloud LLM provider is explicitly configured.

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
- No API keys committed — `config.yaml` ships with placeholder/local-only Ollama provider

## Dev Notes
- `python -m jarvis.main` is the actual entrypoint `start.bat` runs.
- Wake word mic auto-pauses during STT recording to avoid mic conflicts.
- Web UI console: check browser F12 for `[WS]` log messages when debugging WebSocket issues.

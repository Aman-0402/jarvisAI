# Standalone .exe Packaging

## Context

Jarvis currently requires a Python venv (`install.bat` creates it, `start.bat`
activates it) and separately-installed Ollama. The user wants a standalone
`.exe` a person can double-click with no Python/pip knowledge required. This
follows the native-tray-app work (merged in PR #1) — the app already runs as
a proper background app with a window/tray instead of a browser tab; this
spec covers distributing that as a packaged executable.

## Goals

1. A `.exe` that launches Jarvis (window/tray/voice pipeline) without the
   user installing Python or running `pip install`.
2. Keep the exe reasonably sized — don't bundle AI models (Whisper/Kokoro/
   wake-word), they still download on first run as they do today.
3. Clear, non-crashing feedback if Ollama isn't running, instead of a deep
   tool-loop failure.
4. Reuse the existing app icon (`jarvis/assets/icon.ico`).

## Non-goals

- Not bundling Ollama itself (too heavy, changes too often — stays a
  separate install, same as today's `install.bat` flow).
- Not bundling AI models inside the exe (keeps the exe smaller; first-run
  internet requirement for model download is unchanged from today).
- Not solving code-signing/SmartScreen warnings in this pass — an unsigned
  exe will show a Windows SmartScreen prompt on first run; that's expected
  and out of scope here (a future pass could add a code-signing cert).
- Not producing an installer (.msi/setup.exe) — this spec covers the raw
  packaged app folder; a proper installer wrapping this is a separate,
  later piece of work if wanted.

## Design

### Build tool and mode

**PyInstaller**, `--onedir` mode (not `--onefile`).

Rationale: `torch` alone is 536MB on disk in the current venv (measured),
plus `ctranslate2` (60MB), `chromadb`, `pyaudio`, `pythonnet` (needed by
pywebview's WinForms backend), and others. A `--onefile` build re-extracts
this entire payload to a temp directory on *every launch* — for a bundle
this size that's a real, user-visible startup delay (plausibly 10+
seconds), and self-extracting exes this large are also more likely to
trip antivirus/SmartScreen heuristics. `--onedir` produces a folder
(`dist/Jarvis/Jarvis.exe` + supporting DLLs/data) that starts instantly,
which is how comparably-sized desktop apps (Discord, Slack, etc.) actually
ship. The exe still gets double-clicked directly — the folder around it is
just where its dependencies live, same as any traditionally-installed
Windows app's Program Files entry.

Expected total build size: 700MB–1GB+ (dominated by torch/ctranslate2 plus
Python runtime and remaining deps), excluding AI models (downloaded
separately at runtime, unchanged from today).

### Entry point

New file `pyinstaller_entry.py` at repo root:

```python
from jarvis.main import main

if __name__ == "__main__":
    main()
```

PyInstaller analyzes a script file, not a `python -m module` invocation —
this thin wrapper is the actual build entry point (`pyinstaller
pyinstaller_entry.py ...`).

### Config and data location

`config.yaml` and `jarvis/data/` (SQLite memory db, ChromaDB) are read/
written relative to the exe's own directory (`sys.executable`'s parent when
frozen, vs. the repo root when running from source) — portable-style,
matching how `.venv`-relative paths work today for the non-packaged app.
`jarvis/config.py`-equivalent path resolution (currently inline
`Path(__file__).parent.parent / "config.yaml"` scattered across modules)
needs a frozen-aware base-path helper so packaged and source-run modes both
resolve correctly — see Testing section for what this needs to cover.

### Ollama availability check

On startup (in `main()`, before the LLM is ever actually called), do a
lightweight, short-timeout check that `http://localhost:11434` (or the
configured active provider's `base_url`, for non-Ollama setups) is
reachable. If not, and the active provider is `type: ollama`:

- Log a clear, human-readable message: "Ollama not detected at
  localhost:11434. Install from https://ollama.com, run `ollama serve`,
  then `ollama pull qwen3:8b` (or your configured model)."
- Broadcast the same message to the web UI/tray (so it's visible even in
  the no-console packaged-exe case) rather than only printing to a
  console that may not exist.
- Do NOT crash or block startup — voice/wake-word/web UI should still come
  up; only LLM-dependent responses will fail until Ollama is available,
  and that failure should now carry the friendly message instead of a raw
  connection-refused traceback.

This check only applies when `active_provider` is `ollama` — a configured
cloud provider (Gemini, NVIDIA NIM, etc.) skips it entirely.

### Models — unchanged from today

No change to `jarvis/stt.py`, `jarvis/tts.py`, `jarvis/wake.py`'s existing
runtime-download behavior (faster-whisper via HF Hub cache, Kokoro voices
via HF Hub cache, openWakeWord's ONNX models via its own downloader). First
run of the packaged exe still needs internet to pull these, exactly as
first run of `python -m jarvis.main` does today.

### Icon

`jarvis/assets/icon.ico` (already exists, generated in the tray-app work)
is passed to PyInstaller's `--icon` flag.

## Known risk — expect iteration

PyInstaller's static import analysis frequently misses dynamically-loaded
backends in ML-heavy dependency stacks. Concretely, expect to need explicit
`--hidden-import` / `--collect-all` / custom hook entries for at least:

- `torch` (Kokoro's dependency) — has known PyInstaller quirks around its
  C extension loading.
- `ctranslate2` (faster-whisper's backend) — loads platform-specific
  shared libraries at runtime.
- `chromadb` — pulls in `duckdb`/`sqlite` backends dynamically.
- `pyaudio` — needs its bundled PortAudio DLL to actually ship in the
  output folder, not just the Python wrapper.
- `pythonnet`/`clr` (pywebview's WinForms backend) — already ships its own
  PyInstaller hook (confirmed present at
  `.venv/Lib/site-packages/pythonnet/_pyinstaller/hook-clr.py`), which
  reduces risk here, but the .NET runtime interop still needs verification
  in the packaged build.
- `openwakeword`'s ONNX runtime and model-resource files.
- spacy's `en_core_web_sm` model package (seen being installed at runtime
  in earlier testing of this app) — if any code path still triggers this,
  it needs to be a bundled data file or an explicit `collect-data`, not a
  runtime `pip install`.

This is realistically a multi-iteration build→run→fix-missing-import→
rebuild cycle, not a one-shot script. Budget comparable effort to the
native-tray-app implementation, possibly more.

## Testing

- No meaningful unit tests for the PyInstaller spec file / build process
  itself (build tooling, not application logic) — matches this project's
  existing convention of not unit-testing OS/process-integration code
  (`wake.py`'s hardware loop, the tray/window wiring from the prior
  feature).
- New pure-logic addition — the frozen-aware base-path helper (wherever it
  lands, e.g. a new `jarvis/paths.py` or similar) — SHOULD be unit tested:
  given `sys.frozen = True` and a mocked `sys.executable`, returns the
  exe's directory; given `sys.frozen` unset/False, returns the existing
  repo-relative behavior. This is genuinely testable pure logic, unlike
  the build process around it.
- New pure-logic addition — the Ollama-reachability check function
  (e.g. `is_ollama_reachable(base_url, timeout=...)`) SHOULD be unit
  tested: mock the HTTP call, verify True on 200, False on
  connection-refused/timeout.
- Manual verification (not automatable, same reasoning as the tray-app
  work's Task 6): build the exe, copy the output folder to a machine (or a
  clean directory simulating one) without the dev venv on PATH, launch
  `Jarvis.exe` directly, confirm it starts, confirm config.yaml/data land
  next to the exe not embedded, confirm the Ollama-missing message appears
  when Ollama isn't running, confirm voice/wake-word still functions.

## Error handling

- Build-time missing-import errors are expected and handled by iterating
  on PyInstaller's spec file (hidden imports / hooks) — not a runtime
  concern.
- Runtime: if a bundled dependency is genuinely missing from the packaged
  build (a build defect slipping through), the app should fail with a
  visible error (console if attached, or a clear tray-icon-unavailable-
  style degraded state per the existing tray-app error handling) rather
  than a silent crash — but the primary defense here is catching missing
  imports during the build/manual-verification cycle before it ships, not
  runtime recovery.
- Ollama-unreachable: handled gracefully per the Ollama Availability Check
  section above — never crashes the app.

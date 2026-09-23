# Startup Splash Screen

## Context

`Jarvis.exe` (packaged, windowed/no-console build) launches silently — the
only visible feedback is a tray icon that appears once the app is fully up.
Cold start (torch, faster-whisper, Kokoro TTS, openWakeWord model loads) can
take 20-30+ seconds on first run, longer if models still need to download.
A user double-clicking the exe sees nothing happen for that whole window and
reasonably assumes it's broken (this already happened once in manual
testing this session). Needs visible feedback on launch.

## Goals

1. Something appears immediately on double-click, before any slow Python
   import/model-loading work starts.
2. Stays up until the app is genuinely ready to respond by voice — not just
   until the window/tray exists, since TTS and wake-word models load lazily
   after that point.
3. Zero effect on `python -m jarvis.main` (source runs) — packaged-exe-only.

## Non-goals

- No per-stage progress ("loading STT... loading TTS..."). Generic status
  text only.
- No custom animation/spinner graphics. PyInstaller's native splash
  mechanism (a static image + optional text) is enough.

## Design

### Mechanism: PyInstaller's built-in `Splash`

PyInstaller supports a native splash screen (`PyInstaller.building.build_main.Splash`)
that displays a Tk-rendered image immediately when the bootloader starts —
before the bundled Python interpreter even finishes initializing — and stays
up until application code explicitly closes it via the `pyi_splash` module.
This is the standard mechanism for exactly this problem; no custom window
management needed.

### Asset: `jarvis/assets/splash.png`

A 420×420 crop of the existing `icon_master.png` emblem (no text baked in —
the status text is rendered by `pyi_splash` itself, so baked-in text would
either duplicate or conflict with it).

### `jarvis.spec` changes

```python
from PyInstaller.building.build_main import Splash

splash = Splash(
    'jarvis/assets/splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(10, 390),
    text_size=12,
    text_color='white',
    text_default='Starting Jarvis...',
    always_on_top=True,
)
```

`splash` and `splash.binaries`/`splash.datas` get threaded into `EXE(...)`
and `COLLECT(...)` alongside the existing `exe`/`a.binaries`/`a.datas` args
(per PyInstaller's documented Splash usage pattern).

### Close trigger: `jarvis/wake.py`

`listen_for_wake_word()` already prints `"[Jarvis] Listening for wake
word..."` right after the openWakeWord model loads and the mic stream
opens — the exact moment voice input is live. This only executes after the
startup greeting TTS call has already succeeded (it's called earlier in the
same thread, in `main.py`'s `_wake_loop`), so by this point both TTS and
wake-word models are loaded and working.

Add right after that print, guarded by `sys.frozen` (the `pyi_splash`
module only exists inside a PyInstaller build — importing it in a source
run would raise `ModuleNotFoundError`):

```python
if getattr(sys, "frozen", False):
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass
```

`pyi_splash.close()` is safe to call once; the `try/except` guards against
it already being closed or unavailable for any reason, consistent with this
codebase's existing pattern of catching optional/environment-dependent
failures (e.g. the `webview.create_window()` try/except in `main.py`)
rather than letting a non-critical UI feature crash the app.

### Failure mode

If `listen_for_wake_word()` itself fails to start (mic unavailable, model
load error), the splash never closes and the process just looks hung with
the last status text still showing "Starting Jarvis..." — same failure
signature as today's silent hang, but now at least visible instead of
invisible. Acceptable: this is an edge case (mic/model failure), not the
common path, and making it "visibly stuck" is strictly better than
"invisibly stuck," which is the whole point of this feature. A future pass
could add a timeout that swaps the text to an error message, but that's out
of scope here.

## Testing

Not unit-testable — this is PyInstaller build tooling and a `sys.frozen`-
guarded runtime call, matching this project's existing convention of not
unit-testing build/OS-integration code. Verified manually: build the exe,
double-click it, confirm the splash appears immediately, stays up through
model loading, and closes right as "Listening for wake word..." would print
(cross-check timing against a source run's console output).

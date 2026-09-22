# Native Tray App (No Browser Window)

## Context

Jarvis currently launches by opening a browser tab (`webbrowser.open()` in
[main.py](../../../jarvis/main.py)) pointing at its own FastAPI web UI, and
relies on console-attached keyboard shortcuts (Esc/F2/Insert via `msvcrt`)
for control. The user wants Jarvis to run as a native Windows app instead —
no browser tab, minimized to system tray on start, with tray-driven controls
and optional autostart on boot.

## Goals

1. Native desktop window wrapping the existing web UI — no browser process.
2. Starts minimized to tray; window opens on demand from the tray icon.
3. Tray menu: Open Jarvis, Stop (mute toggle), Start with Windows (autostart
   toggle), Exit (full quit).
4. Autostart is opt-in (off by default), toggled from the tray menu.
5. Branded with the user's logo (`jarvis/assets/icon.ico`, `tray_icon.png`,
   already generated).

## Non-goals

- No Electron/Node toolchain — stays pure Python.
- No graceful in-process shutdown signal for the wake-word loop (see
  Architecture) — Exit relies on daemon threads dying with the process.
- No cross-platform (macOS/Linux) tray support — Windows-only, matching the
  rest of the project.

## Approaches considered

1. **pywebview + pystray (recommended)** — pure Python, no new runtime,
   reuses the existing FastAPI/HTML UI unchanged. `pywebview` uses the
   system WebView2 runtime already present on Win10/11. `pystray` runs
   safely off the main thread on Windows.
2. **Electron** — full Chromium + Node.js toolchain. Massive dependency
   footprint mismatched with a solo-dev Python project; rejected.
3. **Browser "app mode"** (`chrome.exe --app=...`) — zero new deps, but
   still a browser process under the hood; doesn't satisfy "not in
   browser."

Going with (1).

## Architecture

### Thread ownership (change from current)

Today `main()` blocks the main thread on `listen_for_wake_word()` and opens
a browser tab. New layout:

- **Main thread**: `pywebview` window event loop (required on Windows).
- **Daemon thread**: wake-word listen loop (moved off main thread —
  `listen_for_wake_word()` itself is unchanged, just called from a thread).
- **Daemon thread**: `pystray` icon loop.
- **Daemon thread**: keyboard listener (unchanged, but see guard below).
- Existing daemon thread: uvicorn server (already threaded via
  `start_web_background`).

### Window behavior

- `webview.create_window(..., hidden=True)` on startup — matches "start
  minimized to tray."
- Tray "Open Jarvis" calls `window.show()`; closing the window (X button)
  hides it instead of destroying it (`window.events.closing` handler calls
  `window.hide()` and returns `False` to cancel the actual close), so the
  app keeps running in tray.

### Tray menu (`jarvis/tray.py`, new module)

- **Open Jarvis** — `window.show()`.
- **Stop** (checkbox, reflects `main._muted` state) — calls the existing
  `toggle_mute()` from `main.py`.
- **Start with Windows** (checkbox, reflects current registry state) —
  toggles a `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` value
  pointing at `start_silent.vbs` (new file, wraps `pythonw.exe -m
  jarvis.main` so no console flashes on boot).
- **Exit** — `icon.stop()` (tray), `window.destroy()` (window), then the
  process exits naturally once `webview.start()` returns (all other
  threads are daemons and die with the process — no explicit wake-loop
  shutdown needed since the PyAudio stream closes with the process).

### Keyboard listener guard

`_keyboard_listener()` uses `msvcrt`, which requires an attached console.
When launched via `start_silent.vbs`/`pythonw.exe` (autostart path), there
is no console. Guard the thread start in `main()`:

```python
import sys
if sys.stdin is not None and sys.stdin.isatty():
    threading.Thread(target=_keyboard_listener, daemon=True).start()
```

This avoids starting a thread that would otherwise loop on caught
exceptions every 100ms indefinitely for no benefit. When launched from
`start.bat` (console attached), behavior is unchanged — Esc/F2/Insert keep
working exactly as before.

### Removed

- `webbrowser.open("http://localhost:7860")` call in `main()` — replaced
  by the hidden pywebview window.

## New files

- `jarvis/tray.py` — tray icon, menu, autostart registry helpers
  (`enable_autostart()`, `disable_autostart()`, `is_autostart_enabled()`),
  window show/hide/exit wiring.
- `start_silent.vbs` — autostart launcher; runs `pythonw.exe -m jarvis.main`
  with the working directory set to the project root, no console window.
- `jarvis/assets/icon.ico`, `tray_icon.png`, `favicon.png`,
  `favicon-32.png`, `icon_master.png` — already generated from the user's
  logo (`logojarvis.png`), cropped to the circular emblem only.

## Config / dependencies

- `requirements.txt`: add `pywebview`, `pystray`.
- No `config.yaml` changes needed for this feature.

## Testing

- Unit tests for `jarvis/tray.py` autostart helpers: mock `winreg` calls,
  verify `enable_autostart()` writes the expected Run key value,
  `disable_autostart()` removes it, `is_autostart_enabled()` reflects
  current state.
- Manual/integration verification (not unit-testable): run `start.bat`,
  confirm no browser tab opens, tray icon appears, window opens/hides
  correctly, Stop mutes, Exit fully quits (no orphan python process), and
  autostart toggle actually registers/unregisters in
  `HKCU\...\Run` (checked via `reg query`).

## Error handling

- If `pywebview` fails to create a window (e.g. WebView2 runtime missing),
  print a clear error and fall back to `webbrowser.open()` so the app is
  still usable rather than crashing outright.
- If tray icon creation fails (rare, e.g. no shell notification area),
  log and continue — voice pipeline and web UI still function without it,
  just no tray affordance.
- Autostart registry writes wrapped in try/except; failure (e.g. permission
  issue) surfaces as a printed error, doesn't crash the app.

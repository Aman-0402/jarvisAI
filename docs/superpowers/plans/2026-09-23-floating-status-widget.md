# Floating Status Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, draggable, always-on-top floating widget (a spinning/glowing ring matching the JARVIS emblem) that shows Jarvis's live state and opens the main HUD window on click.

**Architecture:** A new `jarvis/widget.py` creates a second `pywebview` window (frameless, transparent, always-on-top, `easy_drag=True` for built-in dragging) pointed at a new single-file `jarvis/static/widget.html`. State updates arrive via the existing in-process `register_event_listener()` hook already used by `jarvis/web.py` — no new plumbing, no network round-trip. Position persists to a small JSON file next to the exe (via the existing `get_base_dir()` helper), read on startup and written on a periodic JS-side poll (window position isn't reliably observable from a "move" event across pywebview's backends, so polling `window.screenX/screenY` every 2s is the robust option).

**Tech Stack:** pywebview 6.2.1 (already a dependency — `frameless`, `transparent`, `on_top`, `easy_drag`, `x`/`y`, `js_api` are all supported by the installed version), plain HTML/CSS/JS (no build step, matches `jarvis/static/index.html`'s existing single-file convention).

Spec: `docs/superpowers/specs/2026-09-23-floating-status-widget-design.md`

---

### Task 1: `jarvis/widget.py` — position persistence (TDD)

**Files:**
- Create: `jarvis/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_widget.py
from unittest.mock import patch


def test_save_and_load_widget_position_round_trip(tmp_path):
    """Saving a position and loading it back returns the same (x, y)."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        widget_mod.save_widget_position(120, 340)
        result = widget_mod.load_widget_position()
    assert result == (120, 340)


def test_load_widget_position_returns_none_when_no_file(tmp_path):
    """No saved position yet (first run) — returns None, doesn't raise."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        result = widget_mod.load_widget_position()
    assert result is None


def test_load_widget_position_returns_none_on_corrupt_file(tmp_path):
    """A corrupt/partial JSON file (e.g. killed mid-write) shouldn't crash
    startup — treat it the same as no saved position."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        data_dir = tmp_path / "jarvis" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "widget_position.json").write_text("{not valid json")
        result = widget_mod.load_widget_position()
    assert result is None


def test_save_widget_position_creates_data_dir_if_missing(tmp_path):
    """jarvis/data/ might not exist yet on a fresh install (memory.py
    creates it lazily too) — save must create it, not assume it exists."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        widget_mod.save_widget_position(10, 20)
    assert (tmp_path / "jarvis" / "data" / "widget_position.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_widget.py -v`
Expected: `ModuleNotFoundError: No module named 'jarvis.widget'`.

- [ ] **Step 3: Create `jarvis/widget.py` with the position-persistence functions**

```python
"""Floating status widget — a small always-on-top pywebview window showing
Jarvis's live state (idle/listening/thinking/speaking), draggable, opens
the main HUD window on click. See
docs/superpowers/specs/2026-09-23-floating-status-widget-design.md."""
from __future__ import annotations
import json
from pathlib import Path

from jarvis.paths import get_base_dir

_WIDGET_WIDTH = 120
_WIDGET_HEIGHT = 120


def _position_path() -> Path:
    return get_base_dir() / "jarvis" / "data" / "widget_position.json"


def load_widget_position() -> tuple[int, int] | None:
    """Returns the last saved (x, y), or None if there's no valid saved
    position (first run, or the file is missing/corrupt)."""
    path = _position_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return (int(data["x"]), int(data["y"]))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_widget_position(x: int, y: int) -> None:
    path = _position_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"x": x, "y": y}))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_widget.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add jarvis/widget.py tests/test_widget.py
git commit -m "feat: add widget position persistence (TDD)"
git push origin worktree-standalone-exe
```

---

### Task 2: Default position + state-to-visual mapping (TDD)

**Files:**
- Modify: `jarvis/widget.py`
- Test: `tests/test_widget.py`

Two more pure-logic pieces worth testing before the GUI wiring: computing a
bottom-right default position from screen size, and mapping a `_broadcast()`
status message to the widget's CSS state class.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_widget.py`:

```python
def test_default_position_is_bottom_right_with_margin():
    """No saved position — defaults to the bottom-right corner of the
    screen, with a margin so it's not flush against the edge/taskbar."""
    import jarvis.widget as widget_mod
    x, y = widget_mod.default_widget_position(screen_width=1920, screen_height=1080)
    assert x == 1920 - widget_mod._WIDGET_WIDTH - 20
    assert y == 1080 - widget_mod._WIDGET_HEIGHT - 60


def test_status_to_state_known_messages():
    import jarvis.widget as widget_mod
    assert widget_mod.status_to_state("Ready.") == "idle"
    assert widget_mod.status_to_state("Wake.") == "wake"
    assert widget_mod.status_to_state("Listening...") == "listening"
    assert widget_mod.status_to_state("Thinking...") == "thinking"
    assert widget_mod.status_to_state("Speaking...") == "speaking"


def test_status_to_state_unknown_message_returns_none():
    """Unrelated status messages (e.g. the Ollama-not-reachable banner)
    shouldn't change the widget's visual state."""
    import jarvis.widget as widget_mod
    assert widget_mod.status_to_state("Ollama not detected at ...") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_widget.py -v`
Expected: 3 new failures (`AttributeError: module 'jarvis.widget' has no attribute 'default_widget_position'`, etc).

- [ ] **Step 3: Add the two functions to `jarvis/widget.py`**

Add near the top, after the existing constants:

```python
_STATE_MAP = {
    "Ready.": "idle",
    "Wake.": "wake",
    "Listening...": "listening",
    "Thinking...": "thinking",
    "Speaking...": "speaking",
}


def status_to_state(message: str) -> str | None:
    """Maps a _broadcast() status message to the widget's CSS state class,
    or None if this message isn't one of the widget's known states (e.g.
    the Ollama-not-reachable banner) — the widget should ignore it."""
    return _STATE_MAP.get(message)


def default_widget_position(screen_width: int, screen_height: int) -> tuple[int, int]:
    """Bottom-right corner, with a margin so it clears the taskbar and
    isn't flush against the screen edge."""
    x = screen_width - _WIDGET_WIDTH - 20
    y = screen_height - _WIDGET_HEIGHT - 60
    return (x, y)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_widget.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add jarvis/widget.py tests/test_widget.py
git commit -m "feat: add widget default-position and status-mapping logic (TDD)"
git push origin worktree-standalone-exe
```

---

### Task 3: `jarvis/static/widget.html` — the widget UI

**Files:**
- Create: `jarvis/static/widget.html`

Not unit tested — this is the GUI content, same convention as
`jarvis/static/index.html` (no JS test infrastructure in this project, per
the design spec's Testing section). Verified manually in Task 5.

- [ ] **Step 1: Create the file**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {
    margin: 0; padding: 0; overflow: hidden;
    background: transparent;
    width: 120px; height: 120px;
  }
  .ring-wrap {
    width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    -webkit-user-select: none; user-select: none;
  }
  .ring {
    width: 70px; height: 70px;
    border-radius: 50%;
    border: 3px solid #2a5a7a;
    position: relative;
    display: flex; align-items: center; justify-content: center;
    transition: border-color 0.4s ease;
  }
  .ring::before {
    content: "";
    position: absolute; inset: -3px;
    border-radius: 50%;
    border: 3px solid transparent;
    transition: opacity 0.3s ease;
    opacity: 0;
  }
  .core {
    width: 26px; height: 26px;
    border-radius: 50%;
    background: #0a3a5c;
    box-shadow: 0 0 6px rgba(79, 216, 255, 0.4);
    transition: box-shadow 0.4s ease, background 0.4s ease;
  }

  /* idle: dim, no animation (default state above is already idle-styled) */

  /* wake: brief bright pulse */
  .ring-wrap.wake .ring { border-color: #4fd8ff; }
  .ring-wrap.wake .core {
    background: #1a6fa0;
    box-shadow: 0 0 16px #4fd8ff;
    animation: pulse 0.6s ease-in-out 2;
  }

  /* listening / speaking: steady bright glow, slow pulse */
  .ring-wrap.listening .ring,
  .ring-wrap.speaking .ring { border-color: #4fd8ff; }
  .ring-wrap.listening .core,
  .ring-wrap.speaking .core {
    background: #1a6fa0;
    box-shadow: 0 0 16px #4fd8ff;
    animation: pulse 1.8s ease-in-out infinite;
  }

  /* thinking: ring rotates continuously */
  .ring-wrap.thinking .ring::before {
    opacity: 1;
    border-top-color: #4fd8ff;
    border-right-color: #4fd8ff;
    animation: spin 1s linear infinite;
  }
  .ring-wrap.thinking .core {
    background: #1a6fa0;
    box-shadow: 0 0 12px #4fd8ff;
  }

  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 10px #4fd8ff; }
    50% { box-shadow: 0 0 22px #4fd8ff; }
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
</head>
<body>
  <div class="ring-wrap idle" id="ringWrap" onclick="handleClick()">
    <div class="ring"><div class="core"></div></div>
  </div>

<script>
  const ringWrap = document.getElementById('ringWrap');
  const STATES = ['idle', 'wake', 'listening', 'thinking', 'speaking'];

  function setState(state) {
    STATES.forEach(s => ringWrap.classList.remove(s));
    ringWrap.classList.add(state);
  }

  function handleClick() {
    if (window.pywebview) {
      window.pywebview.api.open_main();
    }
  }

  // Position isn't reliably observable via a native "window moved" event
  // across pywebview's backends — poll instead. Only calls into Python
  // when the position actually changed, so this is cheap.
  let lastPos = null;
  setInterval(() => {
    const pos = window.screenX + ',' + window.screenY;
    if (pos !== lastPos) {
      lastPos = pos;
      if (window.pywebview) {
        window.pywebview.api.save_position(window.screenX, window.screenY);
      }
    }
  }, 2000);
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add jarvis/static/widget.html
git commit -m "feat: add floating widget HTML/CSS/JS"
git push origin worktree-standalone-exe
```

---

### Task 4: Wire the widget window into `main()`

**Files:**
- Modify: `jarvis/widget.py`
- Modify: `jarvis/main.py:493-528`

Not unit tested — window creation/lifecycle wiring, same convention as the
existing tray/main-window setup in `main()`. Verified manually in Task 5.

- [ ] **Step 1: Add `create_widget_window()` and the exposed API class to `jarvis/widget.py`**

Add at the end of the file:

```python
import ctypes


class _WidgetApi:
    """Exposed to the widget's JS via js_api — methods callable as
    `window.pywebview.api.<name>(...)` from widget.html."""

    def __init__(self, main_window):
        self._main_window = main_window

    def save_position(self, x, y) -> None:
        save_widget_position(int(x), int(y))

    def open_main(self) -> None:
        self._main_window.show()


def create_widget_window(main_window):
    """Creates the floating status widget window. Call before
    webview.start() — pywebview requires all windows to exist before the
    GUI event loop starts. Returns the widget's Window object, or None if
    window creation failed (non-critical — caller should catch and
    continue without the widget, same pattern as the main window's own
    webview.create_window() try/except)."""
    import webview

    pos = load_widget_position()
    if pos is None:
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        pos = default_widget_position(screen_width, screen_height)

    widget_html_path = Path(__file__).parent / "static" / "widget.html"

    window = webview.create_window(
        "Jarvis Widget",
        str(widget_html_path),
        js_api=_WidgetApi(main_window),
        width=_WIDGET_WIDTH,
        height=_WIDGET_HEIGHT,
        x=pos[0],
        y=pos[1],
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        resizable=False,
        shadow=False,
    )
    return window


def register_widget_listener(widget_window) -> None:
    """Wires the widget to the app's existing in-process broadcast hook
    (register_event_listener, same mechanism jarvis/web.py uses for the
    WebSocket HUD) so it updates live without any new plumbing."""
    from jarvis.main import register_event_listener

    def _on_event(event: dict) -> None:
        if event.get("type") != "status":
            return
        state = status_to_state(event.get("message", ""))
        if state is None:
            return
        try:
            widget_window.evaluate_js(f"setState('{state}')")
        except Exception:
            pass  # widget window may have been closed

    register_event_listener(_on_event)
```

**Correction (caught in final review, after this task originally shipped with `get_base_dir()` here — that was wrong):** `widget_html_path` must use `Path(__file__).parent / "static" / "widget.html"`, the same pattern `jarvis/web.py`'s `_STATIC_DIR` already uses — NOT `get_base_dir()`. `get_base_dir()` resolves to the exe's own directory when frozen, but PyInstaller onedir puts bundled `datas` (`jarvis/static/` included, per `jarvis.spec`) inside `dist/Jarvis/_internal/`, not next to the exe — this is the exact same pitfall `jarvis/paths.py`'s `ensure_config_exists()` and its `_MEIPASS` fallback already had to work around for `config.yaml.example`. `get_base_dir()` is still correct for `widget_position.json` (genuinely exe-adjacent user data, same as `config.yaml`) — only the bundled-asset path was wrong.

- [ ] **Step 2: Wire it into `main.py`**

The widget window must be created *before* `_on_closing` is defined (not
after, alongside the tray) so that handler can close the widget too when
the app truly exits — otherwise the widget window is orphaned (stays open,
floating) after "Exit" closes the main window, since pywebview's event
loop only ends once every window it knows about is closed.

Current (`jarvis/main.py:493-531`):
```python
    try:
        import webview
        window = webview.create_window(
            "Jarvis", "http://localhost:7860", width=1200, height=800, hidden=True,
        )
    except Exception as e:
        # pywebview unavailable, or its WebView2 runtime is missing/broken —
        # fall back to a browser tab rather than crashing.
        print(f"[Jarvis] Native window unavailable ({e}) — opening in browser instead.")
        import webbrowser
        webbrowser.open("http://localhost:7860")
        _speak_if_unmuted("Good morning. Jarvis online.")
        listen_for_wake_word(handle_wake)
        return

    _exiting = threading.Event()

    def _on_closing():
        if _exiting.is_set():
            return True  # allow the close — this is a real exit, not hide-to-tray
        window.hide()
        return False  # cancel the real close — keep running in tray

    window.events.closing += _on_closing

    def _wake_loop():
        _speak_if_unmuted("Good morning. Jarvis online.")
        listen_for_wake_word(handle_wake)

    wake_thread = threading.Thread(target=_wake_loop, daemon=True)
    wake_thread.start()

    try:
        tray.create_tray_icon(window, is_muted=is_muted, toggle_mute=toggle_mute, exiting_event=_exiting)
    except Exception as e:
        print(f"[Jarvis] Tray icon unavailable ({e}) — continuing without it.")

    try:
        webview.start()
```

Replace with:
```python
    try:
        import webview
        window = webview.create_window(
            "Jarvis", "http://localhost:7860", width=1200, height=800, hidden=True,
        )
    except Exception as e:
        # pywebview unavailable, or its WebView2 runtime is missing/broken —
        # fall back to a browser tab rather than crashing.
        print(f"[Jarvis] Native window unavailable ({e}) — opening in browser instead.")
        import webbrowser
        webbrowser.open("http://localhost:7860")
        _speak_if_unmuted("Good morning. Jarvis online.")
        listen_for_wake_word(handle_wake)
        return

    widget_window = None
    try:
        from jarvis.widget import create_widget_window, register_widget_listener
        widget_window = create_widget_window(window)
        register_widget_listener(widget_window)
    except Exception as e:
        print(f"[Jarvis] Floating widget unavailable ({e}) — continuing without it.")

    _exiting = threading.Event()

    def _on_closing():
        if _exiting.is_set():
            if widget_window is not None:
                try:
                    widget_window.destroy()
                except Exception:
                    pass
            return True  # allow the close — this is a real exit, not hide-to-tray
        window.hide()
        return False  # cancel the real close — keep running in tray

    window.events.closing += _on_closing

    def _wake_loop():
        _speak_if_unmuted("Good morning. Jarvis online.")
        listen_for_wake_word(handle_wake)

    wake_thread = threading.Thread(target=_wake_loop, daemon=True)
    wake_thread.start()

    try:
        tray.create_tray_icon(window, is_muted=is_muted, toggle_mute=toggle_mute, exiting_event=_exiting)
    except Exception as e:
        print(f"[Jarvis] Tray icon unavailable ({e}) — continuing without it.")

    try:
        webview.start()
```

- [ ] **Step 3: Run the full test suite**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest -v`
Expected: same pass/fail counts as before this task (the 3 pre-existing
`test_llm.py` failures), plus the 7 new `test_widget.py` passes. No new
failures.

- [ ] **Step 4: Commit**

```bash
git add jarvis/widget.py jarvis/main.py
git commit -m "feat: wire floating widget window into main()"
git push origin worktree-standalone-exe
```

---

### Task 5: Manual verification

**Files:** none (verification only)

No GUI-click tooling is available to an implementer subagent — same
reasoning as prior manual-verification tasks in this project's other
plans.

- [ ] **Step 1: Source run**

Run `python -m jarvis.main` (or `start.bat`) from a terminal. Confirm:
- The widget appears in the screen's bottom-right corner on first run (no
  saved position yet).
- Ring is dim/idle at startup, brief pulse on "Hey Jarvis" (wake), steady
  glow while listening, spins while thinking, steady glow while speaking,
  back to dim after.
- Dragging the widget (click and hold, move, release) relocates it
  smoothly.
- Clicking the widget (no drag) opens the main HUD window.
- Restart the app — widget reappears at the last dragged-to position, not
  back at the default corner.

- [ ] **Step 2: Packaged exe**

Rebuild (`pyinstaller jarvis.spec --clean`) and repeat Step 1 against
`dist/Jarvis/Jarvis.exe`. `jarvis/static/` is already fully bundled as a
`datas` entry in `jarvis.spec` (`('jarvis/static', 'jarvis/static')`) —
`widget.html` needs no new spec changes to be included.

No commit for this task — it's verification, not code changes. If issues
are found, report them rather than attempting fixes without confirming
scope first.

---

### Task 6: Update docs

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add a bullet under "Key Conventions"**

```
- **Floating status widget**: `jarvis/widget.py` creates a second, small, frameless/transparent/always-on-top pywebview window (`jarvis/static/widget.html`) showing Jarvis's live state as an animated ring. Updates via the same in-process `register_event_listener()` hook `jarvis/web.py` uses for the WebSocket HUD — no new plumbing. Position persists to `jarvis/data/widget_position.json` (via `get_base_dir()`), polled from JS every 2s rather than relying on a native "window moved" event (unreliable across pywebview's backends). Defaults to the screen's bottom-right corner on first run.
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: document floating status widget"
git push origin worktree-standalone-exe
```

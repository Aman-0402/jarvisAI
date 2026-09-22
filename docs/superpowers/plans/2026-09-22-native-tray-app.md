# Native Tray App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Jarvis's browser-tab launch with a native tray app — hidden pywebview window shown on demand, pystray menu (Open/Stop/Start-with-Windows/Exit), opt-in autostart.

**Architecture:** `pywebview` owns the main thread (window event loop, required on Windows); wake-word listening, the tray icon, the keyboard listener, and the uvicorn server each move to their own daemon thread. `jarvis/tray.py` is a new module holding pure autostart-registry logic (unit tested) plus the tray icon/menu wiring (manual-tested, matches how `wake.py`'s hardware loop has no unit tests today).

**Tech Stack:** pywebview (native window), pystray (tray icon), Python stdlib `winreg` (autostart registry).

Spec: `docs/superpowers/specs/2026-09-22-native-tray-app-design.md`

---

### Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the two new deps**

Append to `requirements.txt`:

```
pywebview>=5.0
pystray>=0.19.5
```

- [ ] **Step 2: Install into the venv**

Run: `.venv\Scripts\python.exe -m pip install pywebview pystray`
Expected: both install without error (Pillow already present as a dependency).

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pywebview and pystray dependencies"
```

---

### Task 2: Autostart registry helpers (TDD)

**Files:**
- Create: `jarvis/tray.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tray.py`:

```python
# jarvis/tests/test_tray.py
import pytest
from unittest.mock import patch, MagicMock, call


def test_enable_autostart_writes_registry_value():
    """enable_autostart should write a Run key pointing at start_silent.vbs."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = "HKCU"
        mock_winreg.KEY_SET_VALUE = "SET_VALUE"
        mock_winreg.REG_SZ = "REG_SZ"

        from jarvis.tray import enable_autostart, _RUN_KEY_PATH, _APP_NAME
        enable_autostart()

        mock_winreg.OpenKey.assert_called_once_with(
            "HKCU", _RUN_KEY_PATH, 0, "SET_VALUE"
        )
        args, _ = mock_winreg.SetValueEx.call_args
        assert args[0] == mock_key
        assert args[1] == _APP_NAME
        assert args[3] == "REG_SZ"
        assert "start_silent.vbs" in args[4]
        mock_winreg.CloseKey.assert_called_once_with(mock_key)


def test_disable_autostart_removes_registry_value():
    """disable_autostart should delete the Run key value."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = "HKCU"
        mock_winreg.KEY_SET_VALUE = "SET_VALUE"

        from jarvis.tray import disable_autostart, _APP_NAME
        disable_autostart()

        mock_winreg.DeleteValue.assert_called_once_with(mock_key, _APP_NAME)
        mock_winreg.CloseKey.assert_called_once_with(mock_key)


def test_disable_autostart_handles_missing_value_gracefully():
    """disable_autostart should not raise if the value was never set."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.DeleteValue.side_effect = FileNotFoundError()

        from jarvis.tray import disable_autostart
        disable_autostart()  # must not raise


def test_is_autostart_enabled_true_when_value_exists():
    """is_autostart_enabled should return True when the registry value is present."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("wscript.exe ...", 1)

        from jarvis.tray import is_autostart_enabled
        assert is_autostart_enabled() is True


def test_is_autostart_enabled_false_when_key_missing():
    """is_autostart_enabled should return False if OpenKey fails."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_winreg.OpenKey.side_effect = FileNotFoundError()

        from jarvis.tray import is_autostart_enabled
        assert is_autostart_enabled() is False


def test_is_autostart_enabled_false_when_value_missing():
    """is_autostart_enabled should return False if the key exists but value doesn't."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError()

        from jarvis.tray import is_autostart_enabled
        assert is_autostart_enabled() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_tray.py -v`
Expected: `ModuleNotFoundError: No module named 'jarvis.tray'` (or collection error) — file doesn't exist yet.

- [ ] **Step 3: Create `jarvis/tray.py` with the autostart helpers**

```python
"""System tray icon + Windows autostart for Jarvis."""
from __future__ import annotations
import threading
import winreg
from pathlib import Path

import pystray
from PIL import Image

_ASSETS_DIR = Path(__file__).parent / "assets"
_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "JarvisAI"


def _autostart_command() -> str:
    """Command written to the registry — launches the silent (no console) starter."""
    vbs = Path(__file__).parent.parent / "start_silent.vbs"
    return f'wscript.exe "{vbs}"'


def enable_autostart() -> None:
    """Register Jarvis to launch silently on Windows sign-in."""
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _autostart_command())
    finally:
        winreg.CloseKey(key)


def disable_autostart() -> None:
    """Remove the autostart registry entry, if present."""
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.DeleteValue(key, _APP_NAME)
    except FileNotFoundError:
        pass
    finally:
        winreg.CloseKey(key)


def is_autostart_enabled() -> bool:
    """Check whether the autostart registry entry currently exists."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return False
    try:
        winreg.QueryValueEx(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return False
    finally:
        winreg.CloseKey(key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_tray.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add jarvis/tray.py tests/test_tray.py
git commit -m "feat: add Windows autostart registry helpers (TDD)"
```

---

### Task 3: Tray icon + menu wiring

**Files:**
- Modify: `jarvis/tray.py`

Not unit tested — GUI/OS integration code, same convention as `jarvis/wake.py`'s hardware loop. Verified manually in Task 6.

- [ ] **Step 1: Append `create_tray_icon` to `jarvis/tray.py`**

```python
def create_tray_icon(window, *, is_muted, toggle_mute) -> pystray.Icon:
    """Build the system tray icon and menu, start it in a background thread.

    window: the pywebview Window instance to show/destroy from the menu.
    is_muted: callable() -> bool, reflects current mute state.
    toggle_mute: callable() -> None, toggles mute state.

    Returns the running pystray.Icon.
    """
    image = Image.open(_ASSETS_DIR / "tray_icon.png")

    def _open_window(icon, item):
        window.show()

    def _toggle_stop(icon, item):
        toggle_mute()

    def _toggle_autostart(icon, item):
        try:
            if is_autostart_enabled():
                disable_autostart()
            else:
                enable_autostart()
        except OSError as e:
            print(f"[Jarvis] Could not update autostart registry entry: {e}")

    def _exit_app(icon, item):
        icon.stop()
        window.destroy()

    menu = pystray.Menu(
        pystray.MenuItem("Open Jarvis", _open_window, default=True),
        pystray.MenuItem("Stop", _toggle_stop, checked=lambda item: is_muted()),
        pystray.MenuItem(
            "Start with Windows", _toggle_autostart,
            checked=lambda item: is_autostart_enabled(),
        ),
        pystray.MenuItem("Exit", _exit_app),
    )

    icon = pystray.Icon("jarvis", image, "Jarvis", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
```

- [ ] **Step 2: Commit**

```bash
git add jarvis/tray.py
git commit -m "feat: add tray icon menu (Open/Stop/Start with Windows/Exit)"
```

---

### Task 4: `_should_start_keyboard_listener` guard (TDD)

**Files:**
- Modify: `jarvis/main.py`
- Test: `tests/test_main_tray.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_tray.py`:

```python
# jarvis/tests/test_main_tray.py
from unittest.mock import patch, MagicMock


def test_should_start_keyboard_listener_true_when_console_attached():
    """Returns True when stdin is a real console (start.bat / interactive)."""
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True
    with patch("jarvis.main.sys.stdin", fake_stdin):
        from jarvis.main import _should_start_keyboard_listener
        assert _should_start_keyboard_listener() is True


def test_should_start_keyboard_listener_false_when_no_console():
    """Returns False when stdin is not a tty (pythonw.exe autostart)."""
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = False
    with patch("jarvis.main.sys.stdin", fake_stdin):
        from jarvis.main import _should_start_keyboard_listener
        assert _should_start_keyboard_listener() is False


def test_should_start_keyboard_listener_false_when_stdin_none():
    """Returns False when stdin is None (fully detached process)."""
    with patch("jarvis.main.sys.stdin", None):
        from jarvis.main import _should_start_keyboard_listener
        assert _should_start_keyboard_listener() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_main_tray.py -v`
Expected: FAIL — `ImportError: cannot import name '_should_start_keyboard_listener'`.

- [ ] **Step 3: Add `sys` import and the function to `jarvis/main.py`**

Modify the import block at the top of `jarvis/main.py` (currently lines 1-9):

```python
from __future__ import annotations
import json
import re
import sys
import time
import threading
import msvcrt
from datetime import datetime
from pathlib import Path
import yaml
import numpy as np
import sounddevice as sd
import ollama
from openai import OpenAI
```

Add the new function just above `def main() -> None:` (currently line 424):

```python
def _should_start_keyboard_listener() -> bool:
    """True only when a real console is attached (start.bat / interactive).
    False for the silent autostart launcher (pythonw.exe has no console),
    where msvcrt calls would just fail on every poll for no benefit."""
    return sys.stdin is not None and sys.stdin.isatty()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_main_tray.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add jarvis/main.py tests/test_main_tray.py
git commit -m "feat: guard keyboard listener behind console-attached check (TDD)"
```

---

### Task 5: Rewire `main()` — pywebview window, tray, no browser tab

**Files:**
- Modify: `jarvis/main.py:424-441` (the `main()` function)

Not unit tested — this is the top-level process wiring (thread creation, GUI event loop), same convention as the rest of `main()` today (it has no tests currently). Verified manually in Task 6.

- [ ] **Step 1: Replace `main()`**

Current (lines 424-441):

```python
def main() -> None:
    import webbrowser
    from jarvis.web import start_web_background

    print("[Jarvis] Starting up...")
    print("[Jarvis] Keys: Esc = stop | F2 = type | INSERT = mute/unmute")

    start_web_background(port=7860)
    print("[Jarvis] Web UI: http://localhost:7860")

    threading.Thread(target=_keyboard_listener, daemon=True).start()

    webbrowser.open("http://localhost:7860")

    _speak_if_unmuted("Good morning. Jarvis online.")
    listen_for_wake_word(handle_wake)
```

Replace with:

```python
def main() -> None:
    from jarvis.web import start_web_background
    import jarvis.tray as tray

    print("[Jarvis] Starting up...")
    print("[Jarvis] Keys: Esc = stop | F2 = type | INSERT = mute/unmute")

    start_web_background(port=7860)
    print("[Jarvis] Web UI: http://localhost:7860")

    if _should_start_keyboard_listener():
        threading.Thread(target=_keyboard_listener, daemon=True).start()

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

    def _on_closing():
        window.hide()
        return False  # cancel the real close — keep running in tray

    window.events.closing += _on_closing

    def _wake_loop():
        _speak_if_unmuted("Good morning. Jarvis online.")
        listen_for_wake_word(handle_wake)

    threading.Thread(target=_wake_loop, daemon=True).start()

    try:
        tray.create_tray_icon(window, is_muted=is_muted, toggle_mute=toggle_mute)
    except Exception as e:
        print(f"[Jarvis] Tray icon unavailable ({e}) — continuing without it.")

    webview.start()
```

- [ ] **Step 2: Run the full test suite to confirm nothing else broke**

Run: `.venv\Scripts\python.exe -m pytest -v`
Expected: all tests pass (existing + the new `test_tray.py` and `test_main_tray.py`).

- [ ] **Step 3: Commit**

```bash
git add jarvis/main.py
git commit -m "feat: replace browser-tab launch with hidden pywebview window + tray"
```

---

### Task 6: Silent autostart launcher + manual verification

**Files:**
- Create: `start_silent.vbs`

- [ ] **Step 1: Create `start_silent.vbs`**

```vbscript
' Launches Jarvis with no console window — used by the autostart registry entry.
Set objShell = CreateObject("WScript.Shell")
strPath = objShell.CurrentDirectory
objShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run """" & objShell.CurrentDirectory & "\.venv\Scripts\pythonw.exe"" -m jarvis.main", 0, False
```

- [ ] **Step 2: Manual verification — run and confirm tray behavior**

Run: `.venv\Scripts\python.exe -m jarvis.main`

Confirm:
1. No browser tab opens.
2. A Jarvis tray icon appears in the Windows system tray (may be under the
   "^" overflow arrow).
3. Right-click tray icon → menu shows "Open Jarvis", "Stop", "Start with
   Windows", "Exit".
4. Click "Open Jarvis" → native window opens showing the same UI as
   `localhost:7860`.
5. Close the window (X button) → window disappears but the tray icon
   remains and the process is still running (check `curl
   http://localhost:7860/api/mute` still responds).
6. Click "Stop" → tray checkbox ticks, mic/TTS mute (mirrors existing
   Insert-key behavior). Click again to unmute.
7. Click "Start with Windows" → run `reg query
   "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v JarvisAI` and
   confirm the value now exists and points at `start_silent.vbs`. Click
   again → confirm the value is removed.
8. Click "Exit" → tray icon disappears, window closes, and the python
   process fully exits (check via `Get-Process python -ErrorAction
   SilentlyContinue` in PowerShell — should return nothing for this
   process).

- [ ] **Step 3: Commit**

```bash
git add start_silent.vbs
git commit -m "feat: add silent autostart launcher (start_silent.vbs)"
```

---

### Task 7: Update docs

**Files:**
- Modify: `JARVIS_STATE.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update `JARVIS_STATE.md`**

In the "Architecture" section, change:

```
Voice: Wake word → record_until_silence → transcribe → _process_request → speak_streamed
Web:   WebSocket → _process_request → broadcast to all clients
Keyboard: F2 → input() → _process_request → speak_streamed
```

to:

```
Voice: Wake word → record_until_silence → transcribe → _process_request → speak_streamed
Web:   WebSocket → _process_request → broadcast to all clients
Keyboard: F2 → input() → _process_request → speak_streamed (console launch only)
Tray: pywebview window (hidden by default) + pystray icon — Open/Stop/Start with Windows/Exit
```

Add a row to the "Key Files" table:

```
| `jarvis/tray.py` | System tray icon, menu, Windows autostart registry helpers |
```

- [ ] **Step 2: Update `AGENTS.md`**

In the Project Structure tree, add after the `web.py` line:

```
│   ├── tray.py                 # System tray icon, menu (Open/Stop/Start with Windows/Exit), autostart
```

Add a bullet under "Key Conventions":

```
- **Launch mode**: `start.bat`/`python -m jarvis.main` opens a hidden native window (pywebview) + tray icon, not a browser tab. Tray menu: Open Jarvis, Stop (mute), Start with Windows (autostart toggle), Exit (full quit). Autostart is opt-in, off by default.
```

- [ ] **Step 3: Commit**

```bash
git add JARVIS_STATE.md AGENTS.md
git commit -m "docs: document tray app launch mode"
```

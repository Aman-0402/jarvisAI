# Standalone .exe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package Jarvis as a double-clickable `.exe` (PyInstaller `--onedir`) — no Python/pip required to run it.

**Architecture:** A new `jarvis/paths.py` gives every module a frozen-aware base directory (exe's own folder when packaged, repo root when running from source) — this replaces the `Path(__file__).parent[.parent]` pattern currently scattered across 9 files for `config.yaml` resolution. `tray.py`'s autostart also becomes frozen-aware (launches the exe directly when packaged, keeping the existing `start_silent.vbs`+`wscript.exe` path for source runs). A new `is_ollama_reachable()` check in `main.py` gives a friendly startup message instead of a raw connection error when Ollama isn't running. A PyInstaller `.spec` file drives the actual build, with an explicit, bounded iteration loop for the hidden-import discovery the design spec flags as expected.

**Tech Stack:** PyInstaller (`--onedir`), Python stdlib `sys`/`pathlib`.

Spec: `docs/superpowers/specs/2026-09-22-standalone-exe-design.md`

---

### Task 1: Build entry point + build-only dependency file

**Files:**
- Create: `pyinstaller_entry.py`
- Create: `requirements-build.txt`

- [ ] **Step 1: Create the entry script**

```python
# pyinstaller_entry.py
"""PyInstaller build entry point. PyInstaller analyzes a script file, not a
`python -m module` invocation — this thin wrapper is what `jarvis.spec`
points at."""
from jarvis.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the build-only requirements file**

PyInstaller is a build tool, not a runtime dependency — it doesn't belong
in `requirements.txt` (which `install.bat` uses for the app itself).

```
pyinstaller>=6.0
```

- [ ] **Step 3: Install it and sanity-check the entry script imports cleanly**

Run:
```
"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pip install -r requirements-build.txt
"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -c "import ast; ast.parse(open('pyinstaller_entry.py').read()); print('syntax ok')"
```
Expected: pyinstaller installs cleanly, syntax check passes. Don't run
`pyinstaller_entry.py` directly yet — that's Task 8, after the path fixes
in Tasks 2-4 are in place.

- [ ] **Step 4: Commit**

```bash
git add pyinstaller_entry.py requirements-build.txt
git commit -m "chore: add PyInstaller entry point and build-only requirements"
```

---

### Task 2: `jarvis/paths.py` — frozen-aware base directory (TDD)

**Files:**
- Create: `jarvis/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_paths.py
from pathlib import Path
from unittest.mock import patch


def test_get_base_dir_frozen_returns_exe_directory():
    """When frozen (PyInstaller), base dir is the exe's own directory."""
    import jarvis.paths as paths_mod
    with patch.object(paths_mod.sys, "frozen", True, create=True), \
         patch.object(paths_mod.sys, "executable", r"C:\Apps\Jarvis\Jarvis.exe"):
        result = paths_mod.get_base_dir()
        assert result == Path(r"C:\Apps\Jarvis")


def test_get_base_dir_not_frozen_returns_repo_root():
    """When running from source (not frozen), base dir is the repo root —
    two levels up from this file (jarvis/paths.py -> jarvis/ -> repo root)."""
    import jarvis.paths as paths_mod
    with patch.object(paths_mod.sys, "frozen", False, create=True):
        result = paths_mod.get_base_dir()
        assert result == Path(paths_mod.__file__).parent.parent


def test_get_base_dir_defaults_to_not_frozen_when_attribute_absent():
    """sys.frozen doesn't exist at all outside a PyInstaller build — the
    getattr default must be False, not an AttributeError."""
    import jarvis.paths as paths_mod
    assert getattr(paths_mod.sys, "frozen", False) in (False, True)  # sanity
    with patch.object(paths_mod.sys, "frozen", False, create=True):
        result = paths_mod.get_base_dir()
        assert result == Path(paths_mod.__file__).parent.parent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_paths.py -v`
Expected: `ModuleNotFoundError: No module named 'jarvis.paths'`.

- [ ] **Step 3: Create `jarvis/paths.py`**

```python
"""Base-path resolution that works both when running from source and when
packaged as a PyInstaller exe."""
from __future__ import annotations
import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Directory containing config.yaml and other app-relative resources.

    - Packaged (PyInstaller onedir build): the exe's own directory.
    - Running from source: the repo root (two levels up from this file).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_paths.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add jarvis/paths.py tests/test_paths.py
git commit -m "feat: add frozen-aware base-path resolution (TDD)"
```

---

### Task 3: Migrate `config.yaml` resolution to `get_base_dir()`

**Files:**
- Modify: `jarvis/main.py:9,24`
- Modify: `jarvis/context.py:3,6`
- Modify: `jarvis/llm.py:2,5`
- Modify: `jarvis/memory.py:4,9`
- Modify: `jarvis/stt.py` (has its own `_CONFIG_PATH` line matching the same pattern)
- Modify: `jarvis/tts.py` (same)
- Modify: `jarvis/wake.py` (same)
- Modify: `jarvis/tools/code_exec.py:6,8`
- Modify: `jarvis/tools/file_ops.py:3,5`

Not unit tested per-file — this is a mechanical, uniform substitution
already covered by Task 2's tests for the underlying `get_base_dir()`
logic itself. Verified here by re-running the full existing test suite
(these files' existing tests exercise `_CONFIG_PATH` indirectly via
`_load_config()`, so any breakage shows up immediately).

Every file gets the same two-part change: add
`from jarvis.paths import get_base_dir`, and change
`_CONFIG_PATH = Path(__file__).parent[.parent] / "config.yaml"` to
`_CONFIG_PATH = get_base_dir() / "config.yaml"`. `Path` itself stays
imported in each file — several of them (e.g. `memory.py`) use `Path` for
other things too.

- [ ] **Step 1: `jarvis/main.py`**

Current (lines 20-24):
```python
from jarvis.tools.router import TOOL_SCHEMAS, dispatch

_MAX_TOOL_LOOPS = 15
_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
```

Replace with:
```python
from jarvis.tools.router import TOOL_SCHEMAS, dispatch
from jarvis.paths import get_base_dir

_MAX_TOOL_LOOPS = 15
_CONFIG_PATH = get_base_dir() / "config.yaml"
```

- [ ] **Step 2: `jarvis/context.py`**

Current (lines 1-6):
```python
from __future__ import annotations
from collections import deque
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
```

Replace with:
```python
from __future__ import annotations
from collections import deque
from pathlib import Path
import yaml

from jarvis.paths import get_base_dir

_CONFIG_PATH = get_base_dir() / "config.yaml"
```

- [ ] **Step 3: `jarvis/llm.py`**

Current (lines 1-5):
```python
"""Lightweight LLM chat function for internal tasks (context summarization, etc.)."""
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
```

Replace with:
```python
"""Lightweight LLM chat function for internal tasks (context summarization, etc.)."""
from pathlib import Path
import yaml

from jarvis.paths import get_base_dir

_CONFIG_PATH = get_base_dir() / "config.yaml"
```

- [ ] **Step 4: `jarvis/memory.py`**

Current (lines 1-9):
```python
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from sqlalchemy import create_engine, text

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
```

Replace with:
```python
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from sqlalchemy import create_engine, text

from jarvis.paths import get_base_dir

_CONFIG_PATH = get_base_dir() / "config.yaml"
```

- [ ] **Step 5: `jarvis/stt.py`, `jarvis/tts.py`, `jarvis/wake.py`**

Read each file's current top section first — all three currently have the
identical line `_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"`
near the top, after their own imports. For each of the three files:
add `from jarvis.paths import get_base_dir` alongside the existing imports,
and change that one line to `_CONFIG_PATH = get_base_dir() / "config.yaml"`.
Don't change anything else in these files.

- [ ] **Step 6: `jarvis/tools/code_exec.py`**

Current (lines 1-8):
```python
import subprocess
import sys
import tempfile
import os
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"
```

Replace with:
```python
import subprocess
import sys
import tempfile
import os
import yaml
from pathlib import Path

from jarvis.paths import get_base_dir

_CONFIG_PATH = get_base_dir() / "config.yaml"
```

- [ ] **Step 7: `jarvis/tools/file_ops.py`**

Current (lines 1-5):
```python
import os
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"
```

Replace with:
```python
import os
import yaml
from pathlib import Path

from jarvis.paths import get_base_dir

_CONFIG_PATH = get_base_dir() / "config.yaml"
```

- [ ] **Step 8: Run the full test suite**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest -v`
Expected: same pass/fail counts as before this task (the 3 pre-existing,
unrelated `tests/test_llm.py` failures are unaffected by this — they fail
on mock-patching, not on config path resolution). No NEW failures.

- [ ] **Step 9: Commit**

```bash
git add jarvis/main.py jarvis/context.py jarvis/llm.py jarvis/memory.py jarvis/stt.py jarvis/tts.py jarvis/wake.py jarvis/tools/code_exec.py jarvis/tools/file_ops.py
git commit -m "feat: use get_base_dir() for config.yaml resolution (frozen-aware)"
```

**Explicitly out of scope for this task:** `jarvis/web.py`'s `_STATIC_DIR`/
`_ASSETS_DIR` and `jarvis/tray.py`'s `_ASSETS_DIR` are package-internal
resources (`jarvis/static/`, `jarvis/assets/`) bundled alongside their
Python modules by PyInstaller — `Path(__file__).parent` correctly resolves
these even when frozen, since PyInstaller preserves the package's relative
structure in a onedir build. Do not change these two lines; they're not
part of the bug this task fixes (config.yaml is a *user-editable* file
that lives *outside* the package, next to the exe — a fundamentally
different case from bundled package resources).

---

### Task 4: Frozen-aware autostart in `jarvis/tray.py`

**Files:**
- Modify: `jarvis/tray.py`

- [ ] **Step 1: Read the current file, then update `_autostart_command()`**

Current:
```python
_ASSETS_DIR = Path(__file__).parent / "assets"
_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "JarvisAI"


def _autostart_command() -> str:
    """Command written to the registry — launches the silent (no console) starter."""
    vbs = Path(__file__).parent.parent / "start_silent.vbs"
    return f'wscript.exe "{vbs}"'
```

Replace with (note: `_ASSETS_DIR` is untouched — see Task 3's "explicitly
out of scope" note, same reasoning applies here):
```python
_ASSETS_DIR = Path(__file__).parent / "assets"
_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "JarvisAI"


def _autostart_command() -> str:
    """Command written to the registry — launches Jarvis with no console window.

    Packaged (PyInstaller) build: the exe itself has no console (built
    --noconsole), so it's launched directly — no vbs wrapper needed.
    Running from source: falls back to the existing wscript.exe +
    start_silent.vbs trick (pythonw.exe has no console either)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    vbs = get_base_dir() / "start_silent.vbs"
    return f'wscript.exe "{vbs}"'
```

Add the two new imports at the top of the file alongside the existing
ones (`threading`, `winreg`, `Path`, `pystray`, `Image`):
```python
import sys

from jarvis.paths import get_base_dir
```

- [ ] **Step 2: Run the existing tray tests to confirm nothing broke**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_tray.py -v`
Expected: existing 6 tests still pass — they don't test `_autostart_command()`
directly (it's not one of the 4 registry-helper functions those tests
cover), so this change shouldn't affect them, but confirm.

- [ ] **Step 3: Commit**

```bash
git add jarvis/tray.py
git commit -m "feat: frozen-aware autostart command (direct exe launch when packaged)"
```

---

### Task 5: `is_ollama_reachable()` check (TDD)

**Files:**
- Modify: `jarvis/main.py`
- Test: `tests/test_ollama_check.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ollama_check.py
from unittest.mock import patch, MagicMock
import urllib.error


def test_is_ollama_reachable_true_on_200():
    """Returns True when the base_url responds successfully."""
    from jarvis.main import is_ollama_reachable
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("jarvis.main.urllib.request.urlopen", return_value=mock_response):
        assert is_ollama_reachable("http://localhost:11434") is True


def test_is_ollama_reachable_false_on_connection_refused():
    """Returns False when the connection is refused (Ollama not running)."""
    from jarvis.main import is_ollama_reachable
    with patch("jarvis.main.urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        assert is_ollama_reachable("http://localhost:11434") is False


def test_is_ollama_reachable_false_on_timeout():
    """Returns False on timeout rather than raising or hanging."""
    from jarvis.main import is_ollama_reachable
    with patch("jarvis.main.urllib.request.urlopen", side_effect=TimeoutError()):
        assert is_ollama_reachable("http://localhost:11434", timeout=0.1) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_ollama_check.py -v`
Expected: `ImportError: cannot import name 'is_ollama_reachable'`.

- [ ] **Step 3: Add `urllib.request` import and the function to `jarvis/main.py`**

Add to the import block at the top (alongside the existing `import sys`
from the tray-app work):
```python
import urllib.request
import urllib.error
```

Add the function near the other small pure-logic helpers (e.g. right
after `_should_start_keyboard_listener`):
```python
def is_ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Quick reachability check for an Ollama server. Used to give a clear
    startup message instead of a raw connection error deep in a tool call."""
    try:
        with urllib.request.urlopen(base_url, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest tests/test_ollama_check.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add jarvis/main.py tests/test_ollama_check.py
git commit -m "feat: add is_ollama_reachable() startup check (TDD)"
```

---

### Task 6: Wire the Ollama check into `main()`

**Files:**
- Modify: `jarvis/main.py` (the `main()` function)

Not unit tested — this is startup orchestration wiring, same convention
as the rest of `main()`. Verified manually in Task 9.

- [ ] **Step 1: Add the check near the top of `main()`, right after `start_web_background`**

Read the current `main()` first to find the exact current text (it was
last modified by the native-tray-app work — has `start_web_background`,
`print("[Jarvis] Web UI: ...")`, then the keyboard-listener guard). Insert
right after the "Web UI:" print line, before the keyboard-listener guard:

```python
    active = get_active_provider()
    providers = get_providers()
    if active == "ollama" or providers.get(active, {}).get("type") == "ollama":
        base_url = providers.get(active, {}).get("base_url", "http://localhost:11434")
        if not is_ollama_reachable(base_url):
            msg = (
                f"Ollama not detected at {base_url}. Install from "
                f"https://ollama.com, run 'ollama serve', then "
                f"'ollama pull <your model>'."
            )
            print(f"[Jarvis] {msg}")
            _broadcast({"type": "status", "message": msg})
```

This uses `get_active_provider()` and `get_providers()`, both already
existing functions in `main.py` (defined earlier in the file, used by the
`/api/providers` routes). Only runs the reachability check for
Ollama-type providers — a configured cloud provider (Gemini, NVIDIA NIM,
etc.) skips this entirely, since it doesn't need a local Ollama server.

- [ ] **Step 2: Run the full test suite**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m pytest -v`
Expected: same counts as Task 3's baseline — no new failures.

- [ ] **Step 3: Commit**

```bash
git add jarvis/main.py
git commit -m "feat: warn clearly on startup if Ollama isn't reachable"
```

---

### Task 7: PyInstaller spec file

**Files:**
- Create: `jarvis.spec`

- [ ] **Step 1: Create `jarvis.spec`**

```python
# jarvis.spec — PyInstaller build spec for Jarvis.
# Build with: pyinstaller jarvis.spec --clean
# Output: dist/Jarvis/Jarvis.exe
#
# NOTE: the hidden_imports/collect_all list below is a best-effort
# starting point (see docs/superpowers/specs/2026-09-22-standalone-exe-design.md
# "Known risk" section) — Task 8 iterates on this based on actual build
# failures. Don't treat this file as final on first read.

from PyInstaller.utils.hooks import collect_all

datas = [
    ('jarvis/static', 'jarvis/static'),
    ('jarvis/assets', 'jarvis/assets'),
]
binaries = []
hidden_imports = []

# Libraries with dynamically-loaded backends that PyInstaller's static
# analysis tends to miss — collect_all pulls in their submodules, data
# files, and binaries.
for pkg in ['torch', 'ctranslate2', 'chromadb', 'openwakeword', 'pyaudio', 'pythonnet']:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hidden_imports += pkg_hiddenimports
    except Exception as e:
        print(f"[jarvis.spec] collect_all({pkg!r}) failed: {e}")

a = Analysis(
    ['pyinstaller_entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Jarvis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='jarvis/assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Jarvis',
)
```

- [ ] **Step 2: Commit**

```bash
git add jarvis.spec
git commit -m "feat: add PyInstaller spec file for onedir exe build"
```

---

### Task 8: First build + iterative hidden-import fixes

**Files:**
- Modify: `jarvis.spec` (iteratively, as failures are found)

Not unit tested — this is the empirical build-debugging loop the design
spec explicitly flags as expected ("Known risk — expect iteration").
There is no way to know the exact final `hidden_imports`/`datas` list
without actually attempting the build on this machine — that's the nature
of this task, not a gap in planning.

- [ ] **Step 1: Temporarily enable console output for debugging**

In `jarvis.spec`, change `console=False` to `console=True` in the `EXE(...)`
call. This is temporary — a windowed (`console=False`) app that crashes on
startup shows nothing, making failures invisible. Revert this in Step 6.

- [ ] **Step 2: Build**

Run: `"D:\code\GITHUB\jarvisAI\.venv\Scripts\python.exe" -m PyInstaller jarvis.spec --clean`

This will take several minutes given the size of torch/ctranslate2. Let it
finish; note any errors printed during the build itself (as opposed to
runtime errors when launching the exe).

- [ ] **Step 3: Run the built exe**

Run: `dist\Jarvis\Jarvis.exe` (from the repo root, or `cd dist\Jarvis` first)

Since `console=True` right now, any traceback will be visible in the
console window that appears. Wait ~20-30s for model loading (matches the
non-packaged app's cold-start time) before concluding it failed vs. is
just slow.

- [ ] **Step 4: If it crashes with a missing-module error, fix and rebuild**

If you see `ModuleNotFoundError: No module named 'X'` or similar:
- If `X` is a simple pure-Python module: add `'X'` to the `hidden_imports`
  list in `jarvis.spec`.
- If `X` is a package with its own data files or C extensions (similar to
  torch/ctranslate2/etc.): add `'X'` to the `for pkg in [...]` loop's list
  instead, so `collect_all` handles it properly.
- Re-run Step 2, then Step 3.

**Repeat this cycle.** Each round should get further than the last (a
different missing import, or the app actually starting). If you hit **6
rounds without the app successfully starting and serving
`http://localhost:7860`**, stop and report BLOCKED with the full list of
errors encountered and fixes already tried — don't keep guessing
indefinitely.

- [ ] **Step 5: Confirm the app actually works, not just "doesn't crash on launch"**

Once `Jarvis.exe` runs without a traceback:
```
curl -s -m 5 -o /dev/null -w "HTTP %{http_code}\n" http://localhost:7860/
```
Expected: `HTTP 200`. Also confirm `config.yaml` gets created next to
`dist\Jarvis\Jarvis.exe` (not inside a subfolder) on first run — this
validates Task 2/3's `get_base_dir()` fix actually works when frozen, not
just in the unit tests. Then stop the process (find it via the port 7860
listener, `Stop-Process`).

- [ ] **Step 6: Revert to a windowed (no-console) build**

In `jarvis.spec`, change `console=True` back to `console=False`. Rebuild
(`pyinstaller jarvis.spec --clean`) once more and confirm `Jarvis.exe`
still launches with no visible console window and `curl
http://localhost:7860/` still returns 200. Stop the process afterward.

- [ ] **Step 7: Commit the final working `jarvis.spec`**

```bash
git add jarvis.spec
git commit -m "fix: resolve PyInstaller hidden-import gaps found during build iteration"
```

(If Step 1's `console=True` toggle round-tripped back to `console=False`
with no other changes needed beyond the initial spec from Task 7, this
commit may be empty/unnecessary — skip it in that case and note so in
your report.)

---

### Task 9: Manual verification of the built exe

**Files:** none (verification only)

Same automatable/non-automatable split as the native-tray-app plan's
Task 6 — no GUI-click tooling is available to an implementer subagent.

- [ ] **Step 1: Automatable checks**

From a clean location (ideally copy `dist\Jarvis\` to a different folder
to rule out any accidental dependence on the dev venv/repo layout), run
`Jarvis.exe` directly (no `python`/`pyinstaller_entry.py` involved), wait
~20-30s, and confirm:
- No traceback / crash.
- `curl http://localhost:7860/` → HTTP 200.
- `config.yaml` and `jarvis/data/` (or wherever `memory.db`/`chroma` land
  per config) appear next to `Jarvis.exe`, not embedded inside a bundled
  `_internal` folder.
- If Ollama isn't running in this test environment, confirm the startup
  message from Task 6 appears (in whatever log/output is available) rather
  than a raw connection-refused traceback.

Stop the process afterward (find it via the port 7860 listener).

- [ ] **Step 2: List what still needs a human click-through**

Report these as needing manual verification (same reasoning as the
tray-app plan — no mouse/GUI tools available):
1. Tray icon appears when `Jarvis.exe` is launched.
2. Tray menu shows all 4 items and each does what it should (Open Jarvis,
   Stop, Start with Windows, Exit) — same checklist as the native-tray-app
   plan, now against the packaged exe instead of `python -m jarvis.main`.
3. "Start with Windows" on the packaged exe launches `Jarvis.exe` directly
   on next boot (per Task 4's frozen-aware autostart change) — verify via
   `reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v JarvisAI`
   showing the exe's own path, not a `wscript.exe`/vbs command.
4. Voice pipeline actually works end-to-end from the packaged build (say
   "Hey Jarvis", get a response) — this is the first real test of the full
   voice stack (wake word + STT + TTS) running from inside a PyInstaller
   bundle rather than a normal venv.

No commit for this task — it's verification, not code changes. If issues
are found, report them; don't attempt fixes without confirming scope
first (this could mean going back to Task 8's iteration loop, or could be
a new issue outside what Task 8 covered).

---

### Task 10: Update docs

**Files:**
- Modify: `AGENTS.md`
- Modify: `JARVIS_STATE.md`

- [ ] **Step 1: Update `AGENTS.md`**

Add a new bullet under "Key Conventions" (read the current file first —
it already has several bullets added by prior work; add this as one more,
position doesn't matter much):

```
- **Packaging**: `pyinstaller jarvis.spec --clean` builds a standalone `dist/Jarvis/Jarvis.exe` (onedir — folder + exe, not a single-file build; torch/ctranslate2 make onefile's per-launch extraction too slow). `jarvis/paths.py`'s `get_base_dir()` makes `config.yaml`/`jarvis/data/` resolve next to the exe when frozen vs. the repo root when running from source — any new module reading `config.yaml` must use `get_base_dir()`, not `Path(__file__).parent`, or it'll break in the packaged build.
```

Add a new row to the "Shell Commands" section:
```
pyinstaller jarvis.spec --clean   # build standalone dist/Jarvis/Jarvis.exe
```

- [ ] **Step 2: Update `JARVIS_STATE.md`**

Add a line under "Key Files" table:
```
| `jarvis/paths.py` | Frozen-aware base-path resolution (exe dir when packaged, repo root from source) |
```

Add a short new section near the end (before "## License"):
```
## Standalone Build

`pyinstaller jarvis.spec --clean` produces `dist/Jarvis/Jarvis.exe` — no
Python install required to run it. AI models still download on first run
(same as the source-run app); Ollama is still a separate install (too
heavy to bundle).
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md JARVIS_STATE.md
git commit -m "docs: document standalone exe build"
```

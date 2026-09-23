"""PyInstaller build entry point. PyInstaller analyzes a script file, not a
`python -m module` invocation — this thin wrapper is what `jarvis.spec`
points at."""
import os
import sys

# A windowed (console=False) PyInstaller build has sys.stdout/sys.stderr set
# to None — there's no console to attach them to. Any code that assumes a
# stream exists there (print(), or uvicorn's logging setup calling
# sys.stderr.isatty()) raises AttributeError and, if that happens inside a
# daemon thread, kills the thread silently with no visible error. Must be
# fixed here, before any other import, since jarvis.main/jarvis.web run
# code that touches these streams as soon as they're imported.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from jarvis.main import main

if __name__ == "__main__":
    main()

"""PyInstaller build entry point. PyInstaller analyzes a script file, not a
`python -m module` invocation — this thin wrapper is what `jarvis.spec`
points at."""
from jarvis.main import main

if __name__ == "__main__":
    main()

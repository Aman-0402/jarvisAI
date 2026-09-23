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


def ensure_config_exists() -> None:
    """Copy config.yaml.example -> config.yaml next to the exe/repo root if
    config.yaml doesn't exist yet. Source installs get this from install.bat;
    the packaged exe has no equivalent step, so this covers a truly fresh
    machine with nothing placed next to Jarvis.exe yet.

    PyInstaller onedir bundles `datas` into `_internal/`, not next to the
    exe itself, so config.yaml.example isn't at get_base_dir() when frozen
    — fall back to sys._MEIPASS (PyInstaller's bundle dir, set in both
    onedir and onefile builds) to find the bundled copy."""
    import shutil
    base = get_base_dir()
    config_path = base / "config.yaml"
    if config_path.exists():
        return
    example_path = base / "config.yaml.example"
    if not example_path.exists():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            example_path = Path(meipass) / "config.yaml.example"
    if example_path.exists():
        shutil.copy(example_path, config_path)

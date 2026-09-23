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
    machine with nothing placed next to Jarvis.exe yet."""
    import shutil
    base = get_base_dir()
    config_path = base / "config.yaml"
    example_path = base / "config.yaml.example"
    if not config_path.exists() and example_path.exists():
        shutil.copy(example_path, config_path)

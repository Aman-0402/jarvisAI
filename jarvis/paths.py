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

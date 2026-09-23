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

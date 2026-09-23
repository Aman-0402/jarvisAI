"""Floating status widget — a small always-on-top pywebview window showing
Jarvis's live state (idle/listening/thinking/speaking), draggable, opens
the main HUD window on click. See
docs/superpowers/specs/2026-09-23-floating-status-widget-design.md."""
from __future__ import annotations
import ctypes
import json
from pathlib import Path

from jarvis.paths import get_base_dir

_WIDGET_WIDTH = 120
_WIDGET_HEIGHT = 120

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

    # get_base_dir() is wrong here: it resolves to the exe's own directory
    # when frozen, but PyInstaller onedir puts bundled datas (jarvis/static/
    # included) in _internal/, not next to the exe. Use the same
    # __file__-relative pattern jarvis/web.py's _STATIC_DIR already uses for
    # this exact reason — module __file__ resolves correctly against
    # sys._MEIPASS (_internal/) when frozen.
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

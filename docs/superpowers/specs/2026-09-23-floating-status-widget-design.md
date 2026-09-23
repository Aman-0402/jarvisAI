# Floating Status Widget

## Context

Jarvis currently gives no persistent visual feedback that it's alive and
listening. The only signals are: audio ("Yes?" on wake, spoken responses),
a tray icon (often hidden in Windows' overflow area, no visual state), and
the full HUD window (`jarvis/static/index.html`), which stays hidden unless
explicitly opened via the tray's "Open Jarvis" menu item. A user has no
quick way to glance and confirm Jarvis is running and in what state
(idle / listening / thinking / speaking) without opening that window.

## Goals

1. A small, always-visible widget on the desktop showing Jarvis's current
   state at a glance.
2. Visually consistent with the JARVIS brand (the circular HUD emblem).
3. Draggable — user positions it once, it stays there across launches.
4. Clicking it opens the full HUD window (same as the tray's "Open Jarvis").

## Non-goals

- Not replacing the tray icon or its menu — this is an additional,
  always-visible indicator, not a replacement for existing controls.
- Not adding new interaction beyond click-to-open (no right-click menu on
  the widget itself, no mute-toggle-on-click — that stays in the tray menu).
- Not building a settings UI to disable/reposition it beyond drag — a
  future pass could add a "hide widget" toggle if wanted, out of scope here.

## Design

### Approach: second pywebview window

A second `pywebview` window — frameless, transparent, always-on-top,
non-resizable — renders a small HTML/CSS/JS page showing an animated ring
(matching the JARVIS emblem's circular HUD look, per the approved visual
mockup: a thin ring that's dim/still when idle and spins/glows when active).
This reuses the existing pywebview dependency and the app's existing
HTML/CSS styling conventions rather than introducing a second UI toolkit
(e.g. tkinter) or hand-rolled native window code (ctypes/Win32 layered
windows) — both considered and rejected as unnecessary complexity for a
small status indicator, given pywebview already does everything needed
(transparency, frameless, always-on-top are all supported window options).

### New files

- `jarvis/widget.py` — creates/owns the widget window; exposes
  `create_widget_window()`, called from `main()` right after the existing
  tray/main-window setup.
- `jarvis/static/widget.html` — the widget's content: a `<canvas>` or pure
  CSS ring, JS listeners for drag and click, no external dependencies
  (single-file, matching `jarvis/static/index.html`'s existing convention).

### State → visuals

Five states, driven by status strings `main.py`'s `_broadcast()` already
sends today (used by the WebSocket/HUD) — all already exist in the
codebase, no new broadcast calls needed:

| Status string       | Visual                                    |
|----------------------|--------------------------------------------|
| `"Ready."`            | Dim ring, no animation (idle)             |
| `"Wake."`              | Bright ring, brief pulse (wake detected)  |
| `"Listening..."`        | Steady bright glow, slow pulse            |
| `"Thinking..."`          | Ring rotates continuously                 |
| `"Speaking..."`           | Steady bright glow (same as listening)    |

### Data flow: in-process listener, not WebSocket

`jarvis/main.py` already has `register_event_listener(fn)` — an in-process
callback list that `jarvis/web.py` uses today to relay `_broadcast()` calls
to WebSocket clients. `jarvis/widget.py` registers its own listener the
same way; when it fires, calls `widget_window.evaluate_js(...)` directly to
update the ring's CSS class. No network round-trip, no new state-sync
mechanism — same pattern already in use, just a second consumer.

### Interaction

- **Click** (no drag): call `webview.windows[<main_window_index>].show()` —
  the same call the tray's "Open Jarvis" menu item already makes. A short
  JS `mousedown`/`mouseup` timing+distance check distinguishes a click from
  the start of a drag (standard pattern — if mouse moved more than a few
  pixels between down and up, treat it as a drag, not a click).
- **Drag**: JS tracks `mousemove` deltas while the mouse button is held,
  calling an exposed Python function (`window.expose`'d, e.g.
  `move_widget(dx, dy)`) that repositions the pywebview window via its
  `move(x, y)` method. On `mouseup`, the final position is written to
  `get_base_dir() / "jarvis" / "data" / "widget_position.json"` (same data
  directory `memory.db`/`chroma` already live in, per `jarvis/paths.py`'s
  `get_base_dir()`).
- **Startup position**: `create_widget_window()` reads
  `widget_position.json` if present; otherwise defaults to the primary
  screen's bottom-right corner (computed from `pywebview`'s screen-size
  API), consistent with the approved "bottom-right default, draggable"
  design.

### Lifecycle

Created in `main()` right after the existing tray/main-window setup (same
place `tray.create_tray_icon()` is called today). Destroyed only on full
app exit (tray's "Exit" item, which already sets `_exiting` and closes the
main window) — hiding the main window to tray does *not* close the widget,
since the whole point is that it stays visible while Jarvis runs in the
background.

### Error handling

If the widget window fails to create (same category of risk as the main
window's existing `webview.create_window()` try/except — a broken
WebView2/pythonnet install), catch and log via the same pattern already
used for the main window: print a message, continue without the widget
rather than crashing the app. The app is fully functional without it (tray
+ voice already work), so this is a non-critical enhancement, not a
hard dependency.

## Testing

Not unit-testable — GUI/window-management code, matching this project's
existing convention (`wake.py`'s hardware loop, the main window/tray wiring
from the prior feature). The state→CSS-class mapping logic in
`widget.html`'s JS could theoretically be tested with a JS test runner, but
this project has no JS test infrastructure and adding one for a single
small state-mapping function isn't justified. Verified manually: widget
appears on launch in the last-saved (or default) position, visibly changes
per state during a real wake-word interaction, drags smoothly and persists
position across a restart, and click opens the main HUD window.

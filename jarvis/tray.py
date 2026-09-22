"""System tray icon + Windows autostart for Jarvis."""
from __future__ import annotations
import sys
import threading
import winreg
from pathlib import Path

import pystray
from PIL import Image

from jarvis.paths import get_base_dir

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


def create_tray_icon(window, *, is_muted, toggle_mute, exiting_event) -> pystray.Icon:
    """Build the system tray icon and menu, start it in a background thread.

    window: the pywebview Window instance to show/destroy from the menu.
    is_muted: callable() -> bool, reflects current mute state.
    toggle_mute: callable() -> None, toggles mute state.
    exiting_event: threading.Event — set() before window.destroy() so the
        closing handler allows the real close instead of hiding.

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
        exiting_event.set()
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

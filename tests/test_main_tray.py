# jarvis/tests/test_main_tray.py
from unittest.mock import patch, MagicMock


def test_should_start_keyboard_listener_true_when_console_attached():
    """Returns True when stdin is a real console (start.bat / interactive)."""
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True
    with patch("jarvis.main.sys.stdin", fake_stdin):
        from jarvis.main import _should_start_keyboard_listener
        assert _should_start_keyboard_listener() is True


def test_should_start_keyboard_listener_false_when_no_console():
    """Returns False when stdin is not a tty (pythonw.exe autostart)."""
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = False
    with patch("jarvis.main.sys.stdin", fake_stdin):
        from jarvis.main import _should_start_keyboard_listener
        assert _should_start_keyboard_listener() is False


def test_should_start_keyboard_listener_false_when_stdin_none():
    """Returns False when stdin is None (fully detached process)."""
    with patch("jarvis.main.sys.stdin", None):
        from jarvis.main import _should_start_keyboard_listener
        assert _should_start_keyboard_listener() is False

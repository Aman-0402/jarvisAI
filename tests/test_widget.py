from unittest.mock import patch


def test_save_and_load_widget_position_round_trip(tmp_path):
    """Saving a position and loading it back returns the same (x, y)."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        widget_mod.save_widget_position(120, 340)
        result = widget_mod.load_widget_position()
    assert result == (120, 340)


def test_load_widget_position_returns_none_when_no_file(tmp_path):
    """No saved position yet (first run) — returns None, doesn't raise."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        result = widget_mod.load_widget_position()
    assert result is None


def test_load_widget_position_returns_none_on_corrupt_file(tmp_path):
    """A corrupt/partial JSON file (e.g. killed mid-write) shouldn't crash
    startup — treat it the same as no saved position."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        data_dir = tmp_path / "jarvis" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "widget_position.json").write_text("{not valid json")
        result = widget_mod.load_widget_position()
    assert result is None


def test_save_widget_position_creates_data_dir_if_missing(tmp_path):
    """jarvis/data/ might not exist yet on a fresh install (memory.py
    creates it lazily too) — save must create it, not assume it exists."""
    import jarvis.widget as widget_mod
    with patch.object(widget_mod, "get_base_dir", return_value=tmp_path):
        widget_mod.save_widget_position(10, 20)
    assert (tmp_path / "jarvis" / "data" / "widget_position.json").exists()


def test_default_position_is_bottom_right_with_margin():
    """No saved position — defaults to the bottom-right corner of the
    screen, with a margin so it's not flush against the edge/taskbar."""
    import jarvis.widget as widget_mod
    x, y = widget_mod.default_widget_position(screen_width=1920, screen_height=1080)
    assert x == 1920 - widget_mod._WIDGET_WIDTH - 20
    assert y == 1080 - widget_mod._WIDGET_HEIGHT - 60


def test_status_to_state_known_messages():
    import jarvis.widget as widget_mod
    assert widget_mod.status_to_state("Ready.") == "idle"
    assert widget_mod.status_to_state("Wake.") == "wake"
    assert widget_mod.status_to_state("Listening...") == "listening"
    assert widget_mod.status_to_state("Thinking...") == "thinking"
    assert widget_mod.status_to_state("Speaking...") == "speaking"


def test_status_to_state_unknown_message_returns_none():
    """Unrelated status messages (e.g. the Ollama-not-reachable banner)
    shouldn't change the widget's visual state."""
    import jarvis.widget as widget_mod
    assert widget_mod.status_to_state("Ollama not detected at ...") is None

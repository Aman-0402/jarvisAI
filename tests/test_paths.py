from pathlib import Path
from unittest.mock import patch


def test_get_base_dir_frozen_returns_exe_directory():
    """When frozen (PyInstaller), base dir is the exe's own directory."""
    import jarvis.paths as paths_mod
    with patch.object(paths_mod.sys, "frozen", True, create=True), \
         patch.object(paths_mod.sys, "executable", r"C:\Apps\Jarvis\Jarvis.exe"):
        result = paths_mod.get_base_dir()
        assert result == Path(r"C:\Apps\Jarvis")


def test_get_base_dir_not_frozen_returns_repo_root():
    """When running from source (not frozen), base dir is the repo root —
    two levels up from this file (jarvis/paths.py -> jarvis/ -> repo root)."""
    import jarvis.paths as paths_mod
    with patch.object(paths_mod.sys, "frozen", False, create=True):
        result = paths_mod.get_base_dir()
        assert result == Path(paths_mod.__file__).parent.parent


def test_get_base_dir_defaults_to_not_frozen_when_attribute_absent():
    """sys.frozen doesn't exist at all outside a PyInstaller build — the
    getattr default must be False, not an AttributeError."""
    import jarvis.paths as paths_mod
    assert getattr(paths_mod.sys, "frozen", False) in (False, True)  # sanity
    with patch.object(paths_mod.sys, "frozen", False, create=True):
        result = paths_mod.get_base_dir()
        assert result == Path(paths_mod.__file__).parent.parent


def test_ensure_config_exists_copies_example_next_to_config(tmp_path):
    """config.yaml.example sitting right next to get_base_dir() gets copied
    to config.yaml when config.yaml is missing."""
    import jarvis.paths as paths_mod
    (tmp_path / "config.yaml.example").write_text("example: true")
    with patch.object(paths_mod, "get_base_dir", return_value=tmp_path):
        paths_mod.ensure_config_exists()
    assert (tmp_path / "config.yaml").read_text() == "example: true"


def test_ensure_config_exists_noop_when_config_already_present(tmp_path):
    """Never overwrites an existing config.yaml."""
    import jarvis.paths as paths_mod
    (tmp_path / "config.yaml").write_text("real: config")
    (tmp_path / "config.yaml.example").write_text("example: true")
    with patch.object(paths_mod, "get_base_dir", return_value=tmp_path):
        paths_mod.ensure_config_exists()
    assert (tmp_path / "config.yaml").read_text() == "real: config"


def test_ensure_config_exists_falls_back_to_meipass(tmp_path):
    """PyInstaller onedir puts datas in _internal/ (sys._MEIPASS), not next
    to the exe — must find config.yaml.example there when it's absent from
    get_base_dir() directly."""
    import jarvis.paths as paths_mod
    internal = tmp_path / "_internal"
    internal.mkdir()
    (internal / "config.yaml.example").write_text("from: meipass")
    with patch.object(paths_mod, "get_base_dir", return_value=tmp_path), \
         patch.object(paths_mod.sys, "_MEIPASS", str(internal), create=True):
        paths_mod.ensure_config_exists()
    assert (tmp_path / "config.yaml").read_text() == "from: meipass"


def test_ensure_config_exists_noop_when_no_example_anywhere(tmp_path):
    """No example next to base dir, no _MEIPASS set — does nothing, doesn't
    raise."""
    import jarvis.paths as paths_mod
    with patch.object(paths_mod, "get_base_dir", return_value=tmp_path):
        paths_mod.ensure_config_exists()
    assert not (tmp_path / "config.yaml").exists()

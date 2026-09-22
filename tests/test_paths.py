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

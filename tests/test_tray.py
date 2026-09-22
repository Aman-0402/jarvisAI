# jarvis/tests/test_tray.py
from unittest.mock import patch, MagicMock


def test_enable_autostart_writes_registry_value():
    """enable_autostart should write a Run key pointing at start_silent.vbs."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = "HKCU"
        mock_winreg.KEY_SET_VALUE = "SET_VALUE"
        mock_winreg.REG_SZ = "REG_SZ"

        from jarvis.tray import enable_autostart, _RUN_KEY_PATH, _APP_NAME
        enable_autostart()

        mock_winreg.OpenKey.assert_called_once_with(
            "HKCU", _RUN_KEY_PATH, 0, "SET_VALUE"
        )
        args, _ = mock_winreg.SetValueEx.call_args
        assert args[0] == mock_key
        assert args[1] == _APP_NAME
        assert args[3] == "REG_SZ"
        assert "start_silent.vbs" in args[4]
        mock_winreg.CloseKey.assert_called_once_with(mock_key)


def test_disable_autostart_removes_registry_value():
    """disable_autostart should delete the Run key value."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = "HKCU"
        mock_winreg.KEY_SET_VALUE = "SET_VALUE"

        from jarvis.tray import disable_autostart, _APP_NAME
        disable_autostart()

        mock_winreg.DeleteValue.assert_called_once_with(mock_key, _APP_NAME)
        mock_winreg.CloseKey.assert_called_once_with(mock_key)


def test_disable_autostart_handles_missing_value_gracefully():
    """disable_autostart should not raise if the value was never set."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.DeleteValue.side_effect = FileNotFoundError()

        from jarvis.tray import disable_autostart
        disable_autostart()  # must not raise


def test_is_autostart_enabled_true_when_value_exists():
    """is_autostart_enabled should return True when the registry value is present."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("wscript.exe ...", 1)

        from jarvis.tray import is_autostart_enabled
        assert is_autostart_enabled() is True


def test_is_autostart_enabled_false_when_key_missing():
    """is_autostart_enabled should return False if OpenKey fails."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_winreg.OpenKey.side_effect = FileNotFoundError()

        from jarvis.tray import is_autostart_enabled
        assert is_autostart_enabled() is False


def test_is_autostart_enabled_false_when_value_missing():
    """is_autostart_enabled should return False if the key exists but value doesn't."""
    with patch("jarvis.tray.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError()

        from jarvis.tray import is_autostart_enabled
        assert is_autostart_enabled() is False

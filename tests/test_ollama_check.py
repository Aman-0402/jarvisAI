from unittest.mock import patch, MagicMock
import urllib.error


def test_is_ollama_reachable_true_on_200():
    """Returns True when the base_url responds successfully."""
    from jarvis.main import is_ollama_reachable
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("jarvis.main.urllib.request.urlopen", return_value=mock_response):
        assert is_ollama_reachable("http://localhost:11434") is True


def test_is_ollama_reachable_false_on_connection_refused():
    """Returns False when the connection is refused (Ollama not running)."""
    from jarvis.main import is_ollama_reachable
    with patch("jarvis.main.urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        assert is_ollama_reachable("http://localhost:11434") is False


def test_is_ollama_reachable_false_on_timeout():
    """Returns False on timeout rather than raising or hanging."""
    from jarvis.main import is_ollama_reachable
    with patch("jarvis.main.urllib.request.urlopen", side_effect=TimeoutError()):
        assert is_ollama_reachable("http://localhost:11434", timeout=0.1) is False

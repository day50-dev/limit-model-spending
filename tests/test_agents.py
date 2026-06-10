"""Tests for capit agents interface."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from capit.agents import claude, cursor, windsurf, hermes, opencode, openclaw


class TestAgentInterface:
    """Test that all agents implement the required interface."""

    @pytest.mark.parametrize("agent_module", [
        claude,
        cursor,
        windsurf,
        hermes,
        opencode,
        openclaw,
    ])
    def test_agent_has_show_diff(self, agent_module):
        """All agents must have show_diff function."""
        assert hasattr(agent_module, "show_diff")
        assert callable(getattr(agent_module, "show_diff"))

    @pytest.mark.parametrize("agent_module", [
        claude,
        cursor,
        windsurf,
        hermes,
        opencode,
        openclaw,
    ])
    def test_agent_has_send(self, agent_module):
        """All agents must have send function."""
        assert hasattr(agent_module, "send")
        assert callable(getattr(agent_module, "send"))

    @pytest.mark.parametrize("agent_module", [
        claude,
        cursor,
        windsurf,
        hermes,
        opencode,
        openclaw,
    ])
    def test_agent_has_preview(self, agent_module):
        """All agents must have preview function."""
        assert hasattr(agent_module, "preview")
        assert callable(getattr(agent_module, "preview"))


class TestClaudeAgent:
    """Tests for Claude agent."""

    def test_get_credentials_path(self):
        """Should return correct credentials path."""
        path = claude.get_credentials_path()
        assert path.name == ".credentials.json"
        assert ".claude" in str(path)

    def test_show_diff_signature(self, tmp_path, monkeypatch):
        """show_diff should have correct signature."""
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)
        # Should not raise
        mock_path = tmp_path / ".credentials.json"
        with patch.object(claude, 'get_credentials_path', return_value=mock_path):
            result = claude.show_diff("openrouter", "5.00", "claude")
            assert isinstance(result, bool)

    def test_send_returns_key(self, tmp_path, monkeypatch):
        """send should return the key."""
        # Mock the credentials path
        mock_path = tmp_path / ".credentials.json"
        with patch.object(claude, 'get_credentials_path', return_value=mock_path):
            result = claude.send("sk-test-key", "openrouter", "5.00", confirm=False)
            assert result == "sk-test-key"

    def test_send_creates_config(self, tmp_path):
        """send should create config file."""
        mock_path = tmp_path / ".credentials.json"
        # Create a new agent instance with mocked path
        from capit.agents.claude import ClaudeAgent
        agent = ClaudeAgent()
        with patch.object(agent, 'get_config_path', return_value=mock_path):
            agent.send("sk-test-key", "openrouter", "5.00", confirm=False)

        assert mock_path.exists()
        config = json.loads(mock_path.read_text())
        assert "api_key" in config


class TestCursorAgent:
    """Tests for Cursor agent."""

    def test_get_settings_path(self):
        """Should return correct settings path."""
        path = cursor.get_settings_path()
        assert path.name == "settings.json"
        assert "Cursor" in str(path)

    def test_send_returns_key(self, tmp_path):
        """send should return the key."""
        mock_path = tmp_path / "settings.json"
        with patch.object(cursor, 'get_settings_path', return_value=mock_path):
            result = cursor.send("sk-test-key", "openrouter", "5.00", confirm=False)
            assert result == "sk-test-key"


class TestWindsurfAgent:
    """Tests for Windsurf agent."""

    def test_get_settings_path(self):
        """Should return correct settings path."""
        path = windsurf.get_settings_path()
        assert path.name == "settings.json"
        assert "Windsurf" in str(path)

    def test_send_returns_key(self, tmp_path):
        """send should return the key."""
        mock_path = tmp_path / "settings.json"
        with patch.object(windsurf, 'get_settings_path', return_value=mock_path):
            result = windsurf.send("sk-test-key", "openrouter", "5.00", confirm=False)
            assert result == "sk-test-key"


class TestOpencodeAgent:
    """Tests for Opencode agent."""

    def test_get_auth_path(self):
        """Should return correct auth path."""
        path = opencode.get_auth_path()
        assert path.name == "auth.json"
        assert "opencode" in str(path)

    def test_send_returns_key(self, tmp_path):
        """send should return the key."""
        mock_path = tmp_path / "auth.json"
        with patch.object(opencode, 'get_auth_path', return_value=mock_path):
            result = opencode.send("sk-test-key", "openrouter", "5.00", confirm=False)
            assert result == "sk-test-key"

    def test_send_creates_provider(self, tmp_path):
        """send should create provider entry."""
        mock_path = tmp_path / "auth.json"
        from capit.agents.opencode import OpencodeAgent
        agent = OpencodeAgent()
        with patch.object(agent, 'get_config_path', return_value=mock_path):
            agent.send("sk-test-key", "openrouter", "5.00", confirm=False)

        assert mock_path.exists()
        auth = json.loads(mock_path.read_text())
        assert "openrouter" in auth
        assert auth["openrouter"]["type"] == "api"
        assert auth["openrouter"]["key"] == "sk-test-key"


class TestOpenclawAgent:
    """Tests for OpenClaw agent."""

    def test_get_config_dir(self):
        """Should return correct config directory."""
        path = openclaw.get_config_dir()
        assert path.name == ".openclaw"

    def test_get_secrets_path(self):
        """Should return correct secrets path."""
        path = openclaw.get_secrets_path()
        assert path.name == "secrets.json"
        assert ".openclaw" in str(path)

    def test_get_config_path(self):
        """Should return correct config path."""
        path = openclaw.get_config_path()
        assert path.name == "openclaw.json"
        assert ".openclaw" in str(path)

    def test_send_returns_key(self, tmp_path):
        """send should return the key."""
        mock_secrets = tmp_path / "secrets.json"
        mock_config = tmp_path / "openclaw.json"
        with patch.object(openclaw, 'get_secrets_path', return_value=mock_secrets):
            with patch.object(openclaw, 'get_config_path', return_value=mock_config):
                result = openclaw.send("sk-test-key", "openrouter", "5.00", confirm=False)
                assert result == "sk-test-key"

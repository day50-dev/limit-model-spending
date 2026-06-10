"""Cursor IDE agent for capit.

Automatically configures the API key in Cursor's settings.
"""

from pathlib import Path

from capit.agents.base import SimpleAgent


class CursorAgent(SimpleAgent):
    """Cursor IDE agent."""

    name = "cursor"
    key_path = "openrouter.apiKey"

    def get_config_path(self) -> Path:
        """Get the path to Cursor settings file."""
        return Path.home() / ".config" / "Cursor" / "User" / "settings.json"


# Module-level functions for backwards compatibility
_agent = CursorAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_settings_path = _agent.get_config_path

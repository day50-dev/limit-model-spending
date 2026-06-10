"""Windsurf IDE agent for capit.

Automatically configures the API key in Windsurf's settings.
"""

from pathlib import Path

from capit.agents.base import SimpleAgent


class WindsurfAgent(SimpleAgent):
    """Windsurf IDE agent."""

    name = "windsurf"
    key_path = "openrouter.apiKey"

    def get_config_path(self) -> Path:
        """Get the path to Windsurf settings file."""
        return Path.home() / ".config" / "Windsurf" / "User" / "settings.json"


# Module-level functions for backwards compatibility
_agent = WindsurfAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_settings_path = _agent.get_config_path

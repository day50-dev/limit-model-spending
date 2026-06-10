"""Claude Code agent for capit.

Automatically configures the API key in Claude Code's credentials file.
"""

from pathlib import Path
import os

from capit.agents.base import SimpleAgent


class ClaudeAgent(SimpleAgent):
    """Claude Code agent."""

    name = "claude"
    key_path = "api_key"

    def get_config_path(self) -> Path:
        """Get the path to Claude Code credentials file."""
        # Check for custom config dir
        config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
        if config_dir:
            return Path(config_dir) / ".credentials.json"

        # Default location
        return Path.home() / ".claude" / ".credentials.json"


# Module-level functions for backwards compatibility
_agent = ClaudeAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_credentials_path = _agent.get_config_path

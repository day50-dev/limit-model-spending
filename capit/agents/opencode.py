"""Opencode agent for capit.

Automatically configures the API key in Opencode's auth file.
"""

import copy
import json
from pathlib import Path

from capit.agents.base import Agent, create_backup, show_multi_file_diff, get_multi_file_preview


class OpencodeAgent(Agent):
    """Opencode agent."""

    name = "opencode"

    def get_config_path(self) -> Path:
        """Get the path to Opencode auth file."""
        return Path.home() / ".local" / "share" / "opencode" / "auth.json"

    def preview(self, platform: str, spend_cap: str, agent: str = None) -> dict:
        """Get preview of changes without displaying."""
        agent = agent or self.name
        auth_path = self.get_config_path()

        if auth_path.exists():
            try:
                with open(auth_path, "r") as f:
                    auth = json.load(f)
                old_auth = copy.deepcopy(auth)
            except json.JSONDecodeError:
                old_auth = None
        else:
            old_auth = None
            auth = {}

        new_auth = copy.deepcopy(auth) if auth else {}
        new_auth[platform] = {
            "type": "api",
            "key": "<new key>"
        }

        return get_multi_file_preview(
            files=[(old_auth, new_auth, "auth.json")],
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def show_diff(self, platform: str, spend_cap: str, agent: str = None) -> bool:
        """Show diff with opencode-specific provider structure."""
        agent = agent or self.name
        auth_path = self.get_config_path()

        # Load existing auth
        if auth_path.exists():
            try:
                with open(auth_path, "r") as f:
                    auth = json.load(f)
                old_auth = copy.deepcopy(auth)
            except json.JSONDecodeError:
                old_auth = None
        else:
            old_auth = None
            auth = {}

        # Prepare new auth with placeholder
        new_auth = copy.deepcopy(auth) if auth else {}
        new_auth[platform] = {
            "type": "api",
            "key": "<new key>"
        }

        # Use base class diff function
        from capit.agents.base import show_multi_file_diff
        return show_multi_file_diff(
            files=[(old_auth, new_auth, "auth.json")],
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def _prepare_config(self, config: dict, key: str, platform: str) -> dict:
        """Prepare opencode config with provider structure."""
        config[platform] = {
            "type": "api",
            "key": key
        }
        return config


# Module-level functions for backwards compatibility
_agent = OpencodeAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_auth_path = _agent.get_config_path

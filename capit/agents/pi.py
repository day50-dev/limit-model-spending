"""Pi coding agent for capit.

Automatically configures the API key in Pi's auth file
(~/.pi/agent/auth.json, or $PI_CODING_AGENT_DIR/auth.json).
"""

import copy
import json
import os
from pathlib import Path

from capit.agents.base import Agent, show_multi_file_diff, get_multi_file_preview


class PiAgent(Agent):
    """Pi coding agent."""

    name = "pi"

    def get_config_path(self) -> Path:
        """Get the path to Pi's auth file."""
        agent_dir = os.environ.get("PI_CODING_AGENT_DIR")
        if agent_dir:
            return Path(agent_dir).expanduser() / "auth.json"
        return Path.home() / ".pi" / "agent" / "auth.json"

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
            "type": "api_key",
            "key": "<new key>"
        }

        return get_multi_file_preview(
            files=[(old_auth, new_auth, "auth.json")],
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def show_diff(self, platform: str, spend_cap: str, agent: str = None) -> bool:
        """Show diff with pi-specific provider structure."""
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
            "type": "api_key",
            "key": "<new key>"
        }

        return show_multi_file_diff(
            files=[(old_auth, new_auth, "auth.json")],
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def _prepare_config(self, config: dict, key: str, platform: str) -> dict:
        """Prepare pi config with provider structure."""
        config[platform] = {
            "type": "api_key",
            "key": key
        }
        return config


# Module-level functions for backwards compatibility
_agent = PiAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_auth_path = _agent.get_config_path

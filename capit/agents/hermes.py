"""Hermes agent for capit.

Automatically configures the API key in Hermes's .env file.
"""

import os
from pathlib import Path
import click
import tempfile
import subprocess

from capit.agents.base import Agent, create_backups


class HermesAgent(Agent):
    """Hermes AI agent."""

    name = "hermes"

    def get_config_path(self) -> Path:
        """Get the path to Hermes .env file."""
        return Path.home() / ".hermes" / ".env"

    def _load_env(self, path: Path) -> dict:
        """Load .env file into a dict."""
        env_data = {}
        if path.exists():
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_data[key.strip()] = value.strip()
        return env_data

    def _save_env(self, path: Path, env_data: dict):
        """Save dict to .env file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for key, value in sorted(env_data.items()):
                f.write(f"{key}={value}\n")
        path.chmod(0o600)

    def get_key_name(self, platform: str) -> str:
        """Get the environment variable name for the platform."""
        # Map common platforms to Hermes env var names
        mapping = {
            "openrouter": "OPENROUTER_API_KEY",
            "google": "GOOGLE_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        return mapping.get(platform.lower(), f"{platform.upper()}_API_KEY")

    def preview(self, platform: str, spend_cap: str, agent: str = None) -> dict:
        """Get preview of .env changes without displaying."""
        agent = agent or self.name
        config_path = self.get_config_path()
        key_name = self.get_key_name(platform)

        old_env = self._load_env(config_path)
        new_env = old_env.copy()
        new_env[key_name] = "<new key>"

        with tempfile.NamedTemporaryFile(mode="w", prefix="capit-old-", suffix=".env", delete=False) as old_f:
            for k, v in sorted(old_env.items()):
                old_f.write(f"{k}={v}\n")
            old_path = old_f.name

        with tempfile.NamedTemporaryFile(mode="w", prefix="capit-new-", suffix=".env", delete=False) as new_f:
            for k, v in sorted(new_env.items()):
                new_f.write(f"{k}={v}\n")
            new_path = new_f.name

        try:
            from capit.agents.base import _get_diff_text
            diff_text = _get_diff_text(old_path, new_path)
            return {
                "diff": diff_text,
                "files": [str(config_path)],
                "is_new_config": not old_env
            }
        finally:
            Path(old_path).unlink(missing_ok=True)
            Path(new_path).unlink(missing_ok=True)

    def show_diff(self, platform: str, spend_cap: str, agent: str = None) -> bool:
        """Show diff of .env changes and ask for confirmation."""
        agent = agent or self.name
        config_path = self.get_config_path()
        key_name = self.get_key_name(platform)

        # Load existing
        old_env = self._load_env(config_path)
        new_env = old_env.copy()
        new_env[key_name] = "<new key>"

        # Create temp files for diff
        with tempfile.NamedTemporaryFile(mode="w", prefix="capit-old-", suffix=".env", delete=False) as old_f:
            for k, v in sorted(old_env.items()):
                old_f.write(f"{k}={v}\n")
            old_path = old_f.name

        with tempfile.NamedTemporaryFile(mode="w", prefix="capit-new-", suffix=".env", delete=False) as new_f:
            for k, v in sorted(new_env.items()):
                new_f.write(f"{k}={v}\n")
            new_path = new_f.name

        try:
            click.echo(click.style("Impacted Changes", bold=True), err=True)
            click.echo("", err=True)
            
            # Simple diff output
            subprocess.run(["diff", "--color=auto", "-u", old_path, new_path])
            
            click.echo("", err=True)
            click.echo("─" * 60, err=True)
            return click.confirm(
                f"Configure {agent} with a new {platform} key (limit: ${spend_cap})?",
                default=True,
                err=True
            )
        finally:
            Path(old_path).unlink(missing_ok=True)
            Path(new_path).unlink(missing_ok=True)

    def send(self, key: str, platform: str, spend_cap: str, confirm: bool = True) -> str:
        """Send key to Hermes by updating .env file."""
        config_path = self.get_config_path()
        key_name = self.get_key_name(platform)

        # Create backup
        backup_paths = create_backups(self.get_config_files(), self.name)

        # Update
        env_data = self._load_env(config_path)
        env_data[key_name] = key
        self._save_env(config_path, env_data)

        click.echo(f"${spend_cap} {platform} key installed into {self.name}")

        if backup_paths:
            backup_locations = ", ".join(str(p) for p in backup_paths.values())
            click.echo(f"Old configuration backed up to {backup_locations}")

        return key


# Module-level functions for backwards compatibility
_agent = HermesAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_config_path = _agent.get_config_path

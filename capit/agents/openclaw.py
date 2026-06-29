"""OpenClaw agent for capit.

Automatically configures API keys in OpenClaw's configuration.
OpenClaw uses a gateway-based system with secrets management.
https://docs.openclaw.ai/
"""

import copy
import json
from pathlib import Path

import click

from capit.agents.base import Agent, create_backups, get_multi_file_preview


def _get_provider_config(platform: str):
    """Get provider name and env var for a platform."""
    platform_mapping = {
        "openrouter": ("openrouter", "OPENROUTER_API_KEY"),
        "openai": ("openai", "OPENAI_API_KEY"),
        "anthropic": ("anthropic", "ANTHROPIC_API_KEY"),
        "groq": ("groq", "GROQ_API_KEY"),
        "google": ("google", "GOOGLE_API_KEY"),
        "gemini": ("google", "GOOGLE_API_KEY"),
    }
    return platform_mapping.get(
        platform.lower(),
        (platform.lower(), f"{platform.upper()}_API_KEY")
    )


class OpenclawAgent(Agent):
    """OpenClaw agent - manages two config files."""

    name = "openclaw"

    def get_config_path(self) -> Path:
        """Get the main config file path."""
        return Path.home() / ".openclaw" / "openclaw.json"

    def get_secrets_path(self) -> Path:
        """Get the secrets file path."""
        return Path.home() / ".openclaw" / "secrets.json"

    def get_config_dir(self) -> Path:
        """Get the config directory."""
        return Path.home() / ".openclaw"

    def get_config_files(self) -> list:
        """Get both config files for backup."""
        return [
            (self.get_secrets_path(), "secrets.json"),
            (self.get_config_path(), "openclaw.json")
        ]

    def preview(self, platform: str, spend_cap: str, agent: str = None) -> dict:
        """Get preview of changes without displaying."""
        agent = agent or self.name
        config_dir = self.get_config_dir()
        secrets_path = self.get_secrets_path()
        config_path = self.get_config_path()

        config_dir.mkdir(parents=True, exist_ok=True)
        provider_name, env_var = _get_provider_config(platform)

        # Load existing secrets
        if secrets_path.exists():
            try:
                with open(secrets_path, "r") as f:
                    secrets = json.load(f)
                old_secrets = copy.deepcopy(secrets)
            except json.JSONDecodeError:
                old_secrets = None
        else:
            old_secrets = None
            secrets = {}

        # Prepare new secrets with placeholder
        new_secrets = copy.deepcopy(secrets) if secrets else {}
        if "providers" not in new_secrets:
            new_secrets["providers"] = {}
        new_secrets["providers"][provider_name] = {
            "source": "env",
            "value": "<new key>"
        }

        # Load existing config
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                old_config = copy.deepcopy(config)
            except json.JSONDecodeError:
                old_config = None
        else:
            old_config = None
            config = {}

        # Prepare new config with placeholder
        new_config = copy.deepcopy(config) if config else {}
        if "models" not in new_config:
            new_config["models"] = {}
        if "providers" not in new_config["models"]:
            new_config["models"]["providers"] = {}
        new_config["models"]["providers"][provider_name] = {
            "apiKey": {
                "source": "env",
                "provider": provider_name,
                "id": env_var
            }
        }

        return get_multi_file_preview(
            files=[
                (old_secrets, new_secrets, "secrets.json"),
                (old_config, new_config, "openclaw.json")
            ],
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def show_diff(self, platform: str, spend_cap: str, agent: str = None) -> bool:
        """Show diff for both config files."""
        agent = agent or self.name
        config_dir = self.get_config_dir()
        secrets_path = self.get_secrets_path()
        config_path = self.get_config_path()

        config_dir.mkdir(parents=True, exist_ok=True)
        provider_name, env_var = _get_provider_config(platform)

        # Load existing secrets
        if secrets_path.exists():
            try:
                with open(secrets_path, "r") as f:
                    secrets = json.load(f)
                old_secrets = copy.deepcopy(secrets)
            except json.JSONDecodeError:
                old_secrets = None
        else:
            old_secrets = None
            secrets = {}

        # Prepare new secrets with placeholder
        new_secrets = copy.deepcopy(secrets) if secrets else {}
        if "providers" not in new_secrets:
            new_secrets["providers"] = {}
        new_secrets["providers"][provider_name] = {
            "source": "env",
            "value": "<new key>"
        }

        # Load existing config
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                old_config = copy.deepcopy(config)
            except json.JSONDecodeError:
                old_config = None
        else:
            old_config = None
            config = {}

        # Prepare new config with placeholder
        new_config = copy.deepcopy(config) if config else {}
        if "models" not in new_config:
            new_config["models"] = {}
        if "providers" not in new_config["models"]:
            new_config["models"]["providers"] = {}
        new_config["models"]["providers"][provider_name] = {
            "apiKey": {
                "source": "env",
                "provider": provider_name,
                "id": env_var
            }
        }

        # Use the base class multi-file diff
        from capit.agents.base import show_multi_file_diff
        return show_multi_file_diff(
            files=[
                (old_secrets, new_secrets, "secrets.json"),
                (old_config, new_config, "openclaw.json")
            ],
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def send(self, key: str, platform: str, spend_cap: str, confirm: bool = True) -> str:
        """Configure API key in OpenClaw."""
        config_dir = self.get_config_dir()
        secrets_path = self.get_secrets_path()
        config_path = self.get_config_path()
        agent = self.name

        config_dir.mkdir(parents=True, exist_ok=True)
        provider_name, env_var = _get_provider_config(platform)

        # Load or create secrets
        if secrets_path.exists():
            try:
                with open(secrets_path, "r") as f:
                    secrets = json.load(f)
            except json.JSONDecodeError:
                secrets = {}
        else:
            secrets = {}

        # Load or create config
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                config = {}
        else:
            config = {}

        # Create backups
        backup_paths = create_backups(self.get_config_files(), agent)

        # Update secrets
        if "providers" not in secrets:
            secrets["providers"] = {}
        secrets["providers"][provider_name] = {
            "source": "env",
            "value": key
        }

        # Update config
        if "models" not in config:
            config["models"] = {}
        if "providers" not in config["models"]:
            config["models"]["providers"] = {}
        config["models"]["providers"][provider_name] = {
            "apiKey": {
                "source": "env",
                "provider": provider_name,
                "id": env_var
            }
        }

        # Write secrets
        with open(secrets_path, "w") as f:
            json.dump(secrets, f, indent=2)
            f.write("\n")
        secrets_path.chmod(0o600)

        # Write config
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            f.write("\n")

        click.echo(f"${spend_cap} {platform} key installed into {agent}", err=True)

        if backup_paths:
            backup_locations = ", ".join(str(p) for p in backup_paths.values())
            click.echo(f"Old configuration backed up to {backup_locations}", err=True)

        return key


# Module-level functions for backwards compatibility
_agent = OpenclawAgent()
show_diff = _agent.show_diff
send = _agent.send
preview = _agent.preview
get_config_dir = _agent.get_config_dir
get_secrets_path = _agent.get_secrets_path
get_config_path = _agent.get_config_path

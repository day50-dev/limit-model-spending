"""Base module for capit agents.

This module provides the Agent base class and helper functions for configuring
API keys in various AI agents. Most agents can simply inherit from Agent and
provide configuration - complex agents can override methods as needed.

This file should NOT be listed as an agent - it's a library module.
"""

import copy
import json
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

import click


def create_backup(file_path: Path, agent: str) -> Path:
    """Create a backup of a file before modification.

    Args:
        file_path: Path to the file to backup
        agent: Agent name (used in backup directory prefix)

    Returns:
        Path to the backup file, or None if original doesn't exist
    """
    if not file_path.exists():
        return None

    backup_dir = tempfile.mkdtemp(prefix=f"capit-{agent}-")
    backup_path = Path(backup_dir) / file_path.name
    shutil.copy2(file_path, backup_path)
    return backup_path


def create_backups(files: list, agent: str) -> dict:
    """Create backups of multiple files before modification.

    Args:
        files: List of (file_path, name) tuples
        agent: Agent name (used in backup directory prefix)

    Returns:
        Dict mapping original paths to backup paths
    """
    backup_dir = tempfile.mkdtemp(prefix=f"capit-{agent}-")
    backup_paths = {}

    for file_path, name in files:
        if file_path.exists():
            backup_file = Path(backup_dir) / name
            shutil.copy2(file_path, backup_file)
            backup_paths[file_path] = backup_file

    return backup_paths


def _set_nested_value(data: dict, path: str, value):
    """Set a nested value in a dict using dot notation."""
    keys = path.split(".")
    for key in keys[:-1]:
        if key not in data:
            data[key] = {}
        data = data[key]
    data[keys[-1]] = value


def _get_nested_value(data: dict, path: str, default=None):
    """Get a nested value from a dict using dot notation."""
    keys = path.split(".")
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data


def _display_diff(old_path: str, new_path: str):
    """Display diff between two files."""
    diff_tool = os.environ.get("DIFFTOOL", "diff --color=auto")

    try:
        if diff_tool == "diff --color=auto":
            result = subprocess.run(
                ["diff", "--color=auto", "-u", old_path, new_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                click.echo(result.stdout, err=True)
        elif diff_tool == "diff":
            result = subprocess.run(
                ["diff", "-u", old_path, new_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                click.echo(result.stdout, err=True)
        else:
            subprocess.run([diff_tool, old_path, new_path])
    except FileNotFoundError:
        result = subprocess.run(
            ["diff", "-u", old_path, new_path],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            click.echo(result.stdout, err=True)


def _get_diff_text(old_path: str, new_path: str) -> str:
    """Get unified diff text between two files as a string."""
    try:
        result = subprocess.run(
            ["diff", "-u", old_path, new_path],
            capture_output=True, text=True
        )
        return result.stdout
    except FileNotFoundError:
        return ""


def get_json_preview(
    config_path: Path,
    key_path: str,
    new_value: str,
    agent: str,
    platform: str,
    spend_cap: str
) -> dict:
    """Get preview of JSON config changes without displaying or prompting.

    Args:
        config_path: Path to the config file
        key_path: Dot-notation path to the key field
        new_value: The new value to show in the diff
        agent: Agent name for display
        platform: Platform name for display
        spend_cap: Spending cap for display

    Returns:
        Dict with 'diff' (str), 'files' (list of str), 'is_new_config' (bool)
    """
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

    # Prepare new config with placeholder - handle nested paths
    new_config = copy.deepcopy(config) if config else {}
    keys = key_path.split(".")
    if len(keys) == 1:
        new_config[key_path] = new_value
    else:
        parent_key = ".".join(keys[:-1])
        field_key = keys[-1]
        if parent_key in new_config and isinstance(new_config[parent_key], dict):
            new_config[parent_key][field_key] = new_value
        else:
            new_config[parent_key] = {field_key: new_value}

    # Create temp files for diff
    temp_fd, temp_path = tempfile.mkstemp(prefix="capit-staged-", suffix=".json")
    try:
        with os.fdopen(temp_fd, "w") as f:
            json.dump(new_config, f, indent=2)
            f.write("\n")

        diff_text = ""
        is_new = True
        file_paths = [str(config_path)]

        if old_config is not None:
            old_fd, old_path = tempfile.mkstemp(prefix="capit-current-", suffix=".json")
            try:
                with os.fdopen(old_fd, "w") as f:
                    json.dump(old_config, f, indent=2)
                    f.write("\n")
                diff_text = _get_diff_text(old_path, temp_path)
                is_new = False
            finally:
                try:
                    Path(old_path).unlink()
                except OSError:
                    pass
        else:
            with open(temp_path, "r") as f:
                diff_text = f.read()

        return {
            "diff": diff_text,
            "files": file_paths,
            "is_new_config": is_new
        }
    finally:
        try:
            Path(temp_path).unlink()
        except OSError:
            pass


def show_json_diff(
    config_path: Path,
    key_path: str,
    new_value: str,
    agent: str,
    platform: str,
    spend_cap: str
) -> bool:
    """Show diff of JSON config changes and ask for confirmation.

    Args:
        config_path: Path to the config file
        key_path: Dot-notation path to the key field
        new_value: The new value to show in the diff
        agent: Agent name for display
        platform: Platform name for display
        spend_cap: Spending cap for display

    Returns:
        True if user confirmed, False if aborted
    """
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

    # Prepare new config with placeholder - handle nested paths
    new_config = copy.deepcopy(config) if config else {}
    keys = key_path.split(".")
    if len(keys) == 1:
        new_config[key_path] = new_value
    else:
        parent_key = ".".join(keys[:-1])
        field_key = keys[-1]
        if parent_key in new_config and isinstance(new_config[parent_key], dict):
            new_config[parent_key][field_key] = new_value
        else:
            new_config[parent_key] = {field_key: new_value}

    # Create temp files for diff
    temp_fd, temp_path = tempfile.mkstemp(prefix="capit-staged-", suffix=".json")
    try:
        with os.fdopen(temp_fd, "w") as f:
            json.dump(new_config, f, indent=2)
            f.write("\n")

        # Show diff if old config exists
        if old_config is not None:
            old_fd, old_path = tempfile.mkstemp(prefix="capit-current-", suffix=".json")
            try:
                with os.fdopen(old_fd, "w") as f:
                    json.dump(old_config, f, indent=2)
                    f.write("\n")

                click.echo(click.style("Impacted Changes", bold=True), err=True)
                click.echo("", err=True)
                _display_diff(old_path, temp_path)
            finally:
                try:
                    Path(old_path).unlink()
                except OSError:
                    pass
        else:
            # No existing config, show what will be created
            click.echo(click.style("Impacted Changes", bold=True), err=True)
            click.echo("", err=True)
            click.echo("New configuration:", err=True)
            with open(temp_path, "r") as f:
                click.echo(f.read(), err=True)

        # Ask for confirmation
        click.echo("", err=True)
        click.echo("─" * 60, err=True)
        return click.confirm(
            f"Configure {agent} with a new {platform} key (limit: ${spend_cap})?",
            default=True,
            err=True
        )

    finally:
        try:
            Path(temp_path).unlink()
        except OSError:
            pass


def show_multi_file_diff(
    files: list,
    agent: str,
    platform: str,
    spend_cap: str
) -> bool:
    """Show diffs for multiple config files and ask for confirmation.

    Args:
        files: List of (old_data, new_data, label) tuples
        agent: Agent name for display
        platform: Platform name for display
        spend_cap: Spending cap for display

    Returns:
        True if user confirmed, False if aborted
    """
    click.echo(click.style("Impacted Changes", bold=True), err=True)
    click.echo("", err=True)

    for old_data, new_data, label in files:
        if old_data is not None:
            # Create temp files for diff
            old_fd, old_path = tempfile.mkstemp(prefix=f"capit-old-{label}-", suffix=".json")
            new_fd, new_path = tempfile.mkstemp(prefix=f"capit-new-{label}-", suffix=".json")
            try:
                with os.fdopen(old_fd, "w") as f:
                    json.dump(old_data, f, indent=2)
                    f.write("\n")
                with os.fdopen(new_fd, "w") as f:
                    json.dump(new_data, f, indent=2)
                    f.write("\n")

                _display_diff(old_path, new_path)
                click.echo("", err=True)  # Space between file diffs
            finally:
                try:
                    Path(old_path).unlink()
                    Path(new_path).unlink()
                except OSError:
                    pass
        else:
            # No old data, show new config
            click.echo(f"{label} (new):", err=True)
            temp_fd, temp_path = tempfile.mkstemp(prefix=f"capit-{label}-", suffix=".json")
            try:
                with os.fdopen(temp_fd, "w") as f:
                    json.dump(new_data, f, indent=2)
                    f.write("\n")
                with open(temp_path, "r") as f:
                    click.echo(f.read(), err=True)
                click.echo("", err=True)
            finally:
                try:
                    Path(temp_path).unlink()
                except OSError:
                    pass

    # Ask for confirmation
    click.echo("─" * 60, err=True)
    return click.confirm(
        f"Configure {agent} with a new {platform} key (limit: ${spend_cap})?",
        default=True,
        err=True
    )


def get_multi_file_preview(
    files: list,
    agent: str,
    platform: str,
    spend_cap: str
) -> dict:
    """Get preview of multi-file config changes without displaying or prompting.

    Args:
        files: List of (old_data, new_data, label) tuples
        agent: Agent name for display
        platform: Platform name for display
        spend_cap: Spending cap for display

    Returns:
        Dict with 'diff' (str), 'files' (list of str), 'is_new_config' (bool)
    """
    all_diff_parts = []
    file_paths = []
    is_new_config = True

    for old_data, new_data, label in files:
        if old_data is not None:
            old_fd, old_path = tempfile.mkstemp(prefix=f"capit-old-{label}-", suffix=".json")
            new_fd, new_path = tempfile.mkstemp(prefix=f"capit-new-{label}-", suffix=".json")
            try:
                with os.fdopen(old_fd, "w") as f:
                    json.dump(old_data, f, indent=2)
                    f.write("\n")
                with os.fdopen(new_fd, "w") as f:
                    json.dump(new_data, f, indent=2)
                    f.write("\n")

                diff = _get_diff_text(old_path, new_path)
                if diff:
                    if len(files) > 1:
                        all_diff_parts.append(f"=== {label} ===\n{diff}")
                    else:
                        all_diff_parts.append(diff)
                is_new_config = False
            finally:
                try:
                    Path(old_path).unlink()
                    Path(new_path).unlink()
                except OSError:
                    pass
        else:
            temp_fd, temp_path = tempfile.mkstemp(prefix=f"capit-{label}-", suffix=".json")
            try:
                with os.fdopen(temp_fd, "w") as f:
                    json.dump(new_data, f, indent=2)
                    f.write("\n")
                with open(temp_path, "r") as f:
                    content = f.read()
                if len(files) > 1:
                    all_diff_parts.append(f"=== {label} (new) ===\n{content}")
                else:
                    all_diff_parts.append(content)
            finally:
                try:
                    Path(temp_path).unlink()
                except OSError:
                    pass

    return {
        "diff": "\n".join(all_diff_parts),
        "files": file_paths,
        "is_new_config": is_new_config
    }


def install_key(
    config_path: Path,
    key_path: str,
    key_value: str,
    platform: str,
    agent: str,
    spend_cap: str,
    mode: int = 0o600
) -> str:
    """Install an API key to a config file with backup.

    Args:
        config_path: Path to the config file
        key_path: Dot-notation path to the key field
        key_value: The actual API key value
        platform: Platform name for display
        agent: Agent name for display
        spend_cap: Spending cap for display
        mode: File permissions (default 0o600)

    Returns:
        The key value
    """
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    # Create backup
    backup_path = create_backup(config_path, agent)

    # Update key - handle nested paths
    keys = key_path.split(".")
    if len(keys) == 1:
        config[key_path] = key_value
    else:
        parent_key = ".".join(keys[:-1])
        field_key = keys[-1]
        if parent_key not in config:
            config[parent_key] = {}
        if not isinstance(config[parent_key], dict):
            config[parent_key] = {}
        config[parent_key][field_key] = key_value

    # Write with secure permissions
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    config_path.chmod(mode)

    click.echo(f"${spend_cap} {platform} key installed into {agent}", err=True)

    if backup_path:
        click.echo(f"Old configuration backed up to {backup_path}", err=True)

    return key_value


class Agent(ABC):
    """Base class for capit agents.

    Subclass this to create a new agent. For simple agents that just need to
    set a single key field in a JSON config file, you only need to set class
    attributes. For complex agents, override the methods as needed.

    Example (simple agent):
        class MyAgent(Agent):
            name = "myagent"
            config_path = Path.home() / ".myagent" / "config.json"
            key_path = "api_key"  # or "{platform}.key" for nested

    Example (complex agent):
        class MyAgent(Agent):
            name = "myagent"

            def get_config_files(self) -> list:
                return [self._get_secrets_path(), self._get_config_path()]

            def _update_config(self, config: dict, key: str, platform: str) -> dict:
                # Custom config update logic
                return config
    """

    # Class attributes for simple agents
    name: str = None
    config_path: Path = None
    key_path: str = "api_key"

    @abstractmethod
    def get_config_path(self) -> Path:
        """Get the primary config file path for this agent.

        Returns:
            Path to the config file
        """
        pass

    def get_config_files(self) -> list:
        """Get all config files that need backup.

        Override this for agents that manage multiple config files.

        Returns:
            List of (Path, name) tuples for files to backup
        """
        return [(self.get_config_path(), self.get_config_path().name)]

    def get_key_path(self, platform: str = None) -> str:
        """Get the key path for this agent.

        Override to support dynamic key paths based on platform.

        Args:
            platform: The platform name (e.g., "openrouter")

        Returns:
            Dot-notation path to the key field
        """
        return self.key_path

    def preview(self, platform: str, spend_cap: str, agent: str = None) -> dict:
        """Get preview of changes without displaying or prompting.

        Override this for agents with custom preview logic.

        Args:
            platform: Platform name
            spend_cap: Spending cap
            agent: Agent name (defaults to self.name)

        Returns:
            Dict with 'diff' (str), 'files' (list of str), 'is_new_config' (bool)
        """
        agent = agent or self.name
        config_path = self.get_config_path()
        key_path = self.get_key_path(platform)

        return get_json_preview(
            config_path=config_path,
            key_path=key_path,
            new_value="<new key>",
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def show_diff(self, platform: str, spend_cap: str, agent: str = None) -> bool:
        """Show diff of changes and ask for confirmation.

        Override this for agents with custom diff logic.

        Args:
            platform: Platform name
            spend_cap: Spending cap
            agent: Agent name (defaults to self.name)

        Returns:
            True if user confirmed, False if aborted
        """
        agent = agent or self.name
        config_path = self.get_config_path()
        key_path = self.get_key_path(platform)

        return show_json_diff(
            config_path=config_path,
            key_path=key_path,
            new_value="<new key>",
            agent=agent,
            platform=platform,
            spend_cap=spend_cap
        )

    def _prepare_config(self, config: dict, key: str, platform: str) -> dict:
        """Prepare the config with the new key.

        Override this for custom config preparation logic.

        Args:
            config: Current config dict
            key: The API key to set
            platform: Platform name

        Returns:
            Updated config dict
        """
        key_path = self.get_key_path(platform)
        keys = key_path.split(".")

        if len(keys) == 1:
            config[key_path] = key
        else:
            parent_key = ".".join(keys[:-1])
            field_key = keys[-1]
            if parent_key not in config:
                config[parent_key] = {}
            if not isinstance(config[parent_key], dict):
                config[parent_key] = {}
            config[parent_key][field_key] = key

        return config

    def _write_config(self, config_path: Path, config: dict, mode: int = 0o600):
        """Write config to file with secure permissions.

        Override this for custom config writing logic.

        Args:
            config_path: Path to write to
            config: Config dict to write
            mode: File permissions
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        config_path.chmod(mode)

    def send(self, key: str, platform: str, spend_cap: str, confirm: bool = True) -> str:
        """Send key to agent by updating config file.

        Override this for agents with custom installation logic.

        Args:
            key: The API key to install
            platform: Platform name
            spend_cap: Spending cap
            confirm: Ignored (confirmation handled in show_diff)

        Returns:
            The key (for potential chaining)
        """
        config_path = self.get_config_path()
        agent = self.name

        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config
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

        # Update config
        config = self._prepare_config(config, key, platform)

        # Write config
        self._write_config(config_path, config)

        click.echo(f"${spend_cap} {platform} key installed into {agent}", err=True)

        if backup_paths:
            backup_locations = ", ".join(str(p) for p in backup_paths.values())
            click.echo(f"Old configuration backed up to {backup_locations}", err=True)

        return key


class SimpleAgent(Agent):
    """Convenience base class for simple JSON config agents.

    Just set the class attributes and you're done:

        class MyAgent(SimpleAgent):
            name = "myagent"
            config_path = Path.home() / ".myagent" / "config.json"
            key_path = "api_key"  # or "{platform}.key" for nested
    """

    def get_config_path(self) -> Path:
        """Get the config file path."""
        return self.config_path


def simple_agent_send(
    key: str,
    platform: str,
    spend_cap: str,
    agent: str,
    config_path: Path,
    key_path: str = "api_key",
    mode: int = 0o600
) -> str:
    """Simple agent send function for basic JSON config updates.

    This is for agents that just need to set a single key field.

    Args:
        key: The API key to install
        platform: Platform name
        spend_cap: Spending cap
        agent: Agent name
        config_path: Path to config file
        key_path: Dot-notation path to key field
        mode: File permissions

    Returns:
        The key value
    """
    return install_key(config_path, key_path, key, platform, agent, spend_cap, mode)

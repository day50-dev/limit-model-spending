# capit Agents

Agents are AI tools and assistants that capit can automatically configure with capped API keys.

When you run `capit openrouter 5.00 --agent claude`, capit:
1. Shows a diff of what will change (with `<new key>` placeholder)
2. Asks for confirmation
3. Creates the limited key only after you confirm
4. Updates the agent's config file
5. Backs up the old configuration

## Built-in Agents

| Agent | Config File | Command |
|-------|-------------|---------|
| **claude** | `~/.claude/.credentials.json` | `capit openrouter 5.00 --agent claude` |
| **cursor** | `~/.config/Cursor/User/settings.json` | `capit openrouter 10.00 --agent cursor` |
| **windsurf** | `~/.config/Windsurf/User/settings.json` | `capit openrouter 5.00 --agent windsurf` |
| **hermes** | `~/.hermes/.env` | `capit openrouter 5.00 --agent hermes` |
| **openclaw** | `~/.openclaw/secrets.json` + `openclaw.json` | `capit openrouter 5.00 --agent openclaw` |
| **opencode** | `~/.local/share/opencode/auth.json` | `capit openrouter 5.00 --agent opencode` |

## Output Format

All agents use the same clean output:

```bash
$ capit openrouter 5.00 --agent claude

Configure claude with a new openrouter key (limit: $5.00)?
Changes:
--- /tmp/capit-current-xxx.json
+++ /tmp/capit-staged-yyy.json
@@ -1,3 +1,3 @@
 {
-  "api_key": "sk-or-v1-oldkey..."
+  "api_key": "<new key>"
 }

Continue? [Y/n]: y
$5.00 openrouter key installed into claude
Old configuration backed up to /tmp/capit-abc123/.credentials.json
```

## Adding a Custom Agent

### Option 1: Ask Claude

Use the agent-creator skill:

```
Add a new agent for my-agent that writes the API key to ~/.myagent/config.json
```

See [skills/agent-creator.md](../skills/agent-creator.md) for details.

### Option 2: Manual

#### Simple Agent (recommended)

For most agents, just inherit from `SimpleAgent`:

```python
"""MyAgent agent for capit."""

from pathlib import Path
from capit.agents.base import SimpleAgent


class MyAgent(SimpleAgent):
    """MyAgent integration."""

    name = "myagent"
    config_path = Path.home() / ".myagent" / "config.json"
    key_path = "api_key"  # or "{platform}.key" for nested like "openrouter.key"
```

That's it! The base class provides `show_diff()` and `send()` methods.

#### Nested Key Agent

For agents with nested config like `{"openrouter": {"key": "..."}}`:

```python
"""MyAgent agent for capit."""

from pathlib import Path
from capit.agents.base import SimpleAgent


class MyAgent(SimpleAgent):
    name = "myagent"
    config_path = Path.home() / ".myagent" / "config.json"
    key_path = "{platform}.key"  # Dynamic based on platform

    def get_key_path(self, platform: str = None) -> str:
        return f"{platform}.key"
```

#### Complex Agent (multiple files)

For agents that need to update multiple config files (like OpenClaw), inherit from `Agent` and override methods:

```python
"""MyAgent agent for capit."""

from pathlib import Path
from capit.agents.base import Agent, create_backups


class MyAgent(Agent):
    name = "myagent"

    def get_config_path(self) -> Path:
        return Path.home() / ".myagent" / "config.json"

    def get_config_files(self) -> list:
        """Return multiple files for backup."""
        return [
            (self.get_secrets_path(), "secrets.json"),
            (self.get_config_path(), "config.json")
        ]

    def _prepare_config(self, config: dict, key: str, platform: str) -> dict:
        """Custom config preparation logic."""
        config[platform] = {"key": key}
        return config
```

See `capit/agents/openclaw.py` for a full reference implementation.

## Agent Interface

Every agent must implement:

```python
def show_diff(platform: str, spend_cap: str, agent: str) -> bool:
    """Show diff of changes and ask for confirmation.
    
    Returns True if user confirmed, False if aborted.
    """


def send(key: str, platform: str, spend_cap: str, confirm: bool = True) -> str:
    """Configure the API key for this agent.
    
    Args:
        key: The generated limited API key
        platform: The platform name (e.g., "openrouter")
        spend_cap: The spending cap (e.g., "5.00")
        confirm: Ignored (confirmation already handled by show_diff)
    
    Returns:
        The key (for potential chaining)
    
    Output:
        Must print: f"${spend_cap} {platform} key installed into <agent>"
        Should also print backup location if backup was created.
    """
```

## Library Functions

The `capit.agents.base` module provides helper functions and base classes:

### `Agent` (base class)

Abstract base class for all agents. Provides default implementations of `show_diff()` and `send()`.

### `SimpleAgent` (base class)

Convenience base class for simple JSON config agents. Just set class attributes:

```python
class MyAgent(SimpleAgent):
    name = "myagent"
    config_path = Path.home() / ".myagent" / "config.json"
    key_path = "api_key"
```

### `show_json_diff()`

Shows a staged diff with `<new key>` placeholder and asks for confirmation.

### `install_key()`

Installs the key to a JSON config file with backup.

### `create_backup()` / `create_backups()`

Create backups of files before modification.

## Listing Agents

```bash
capit --agents
# claude
# cursor
# windsurf
# openclaw
# opencode
# example
```

## Testing

After creating an agent:

```bash
capit --agents  # Should list your agent
capit openrouter 5.00 --agent myagent  # Test it
```

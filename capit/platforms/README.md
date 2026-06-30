# capit Platforms

Platforms define how capit creates limited keys for different services.

## Built-in Platforms

### OpenRouter (LLM APIs)

**Best for:** AI agents (Claude Code, Cursor, Windsurf, etc.)

```bash
capit openrouter 5.00 --agent openclaw -y
```

Creates API keys with USD spending caps enforced by OpenRouter. The key literally cannot spend more than the cap.

**Features:**
- Hard USD spending cap
- Enforced by OpenRouter
- Works with 100+ LLM models
- Auto-created guardrails

### aihubmix (LLM APIs)

**Best for:** AI agents with alternative pricing

```bash
capit aihubmix 5.00 --agent claude -y
```

Creates API keys with spending caps for aihubmix services.

### Concentrate (LLM Gateway)

**Best for:** AI agents using any major model provider through a single gateway

```bash
capit concentrate 5.00 --agent claude -y
```

Creates deterministic offline API keys for Concentrate, an LLM gateway that unifies 120+ models across 16+ providers. Since Concentrate manages keys through the dashboard, limits are applied manually when creating the key.

**Features:**
- Single key for 120+ models across providers
- Guardrails (PII redaction) configurable via dashboard
- Zero Data Retention (ZDR) and logging per key
- Spend tracking by org, team, and key

## Adding Platforms

### Ask Claude

Use the platform-creator skill in the `skills/` directory:

```
Add a new platform for Anthropic that creates API keys with spending limits
```

See [skills/platform-creator.md](../skills/platform-creator.md) for details.

### Manual

1. Copy the template:
   ```bash
   cp capit/platforms/example.py capit/platforms/anthropic.py
   ```

2. Implement the `create_limited_key()` function

3. Test:
   ```bash
   capit --platforms  # Should list anthropic
   capit anthropic 5.00
   ```

## Platform Interface

```python
"""MyPlatform implementation for capit."""

PLATFORM_NAME = "myplatform"
PLATFORM_URL = "https://myplatform.com"
API_BASE = "https://api.myservice.com/v1"  # Required for online mode


def create_limited_key(
    master_key: str,
    spend_cap: str,
    salt: str,
    prefix: str = None
) -> str:
    """Create a limited key with spending/rate limits.

    Args:
        master_key: The master API key
        spend_cap: The spending cap (e.g., "5.00" for $5)
        salt: Random salt for uniqueness
        prefix: Optional prefix for organization (defaults to "capit")

    Returns:
        The created API key string
    """
    # Build key name from prefix and salt
    prefix = prefix or "capit"
    key_name = f"{prefix.rstrip('-')}-{salt[:8]}"
    
    # Call platform API to create key with limits
    ...
    return key
```

## Listing Platforms

```bash
capit --platforms
# aihubmix
# concentrate
# openrouter
```

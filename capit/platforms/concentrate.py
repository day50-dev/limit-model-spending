"""Concentrate platform implementation for capit.

Concentrate is an LLM gateway providing unified access to 120+ AI models
through a single API. API keys are managed through the dashboard
(no public key management API is available).

https://concentrate.ai/docs/llms.txt
"""

import hashlib

PLATFORM_NAME = "concentrate"
PLATFORM_URL = "https://concentrate.ai"
API_BASE = "https://api.concentrate.ai/v1"
SETUP_URL = "https://concentrate.ai"
SETUP_INSTRUCTIONS = "Create an API key from the Concentrate dashboard"


def validate_key(key: str) -> bool:
    """Validate a Concentrate API key format."""
    return key.startswith("sk-cn-") or key.startswith("sk-cn-v1-")


def get_key_format() -> str:
    """Return the expected key format for documentation."""
    return "sk-cn-..."


def create_limited_key(master_key: str, spend_cap: str, salt: str, prefix: str = None) -> str:
    """Create a deterministic limited key for Concentrate.

    Concentrate does not expose a public API for creating or managing
    API keys programmatically. Keys are created and configured through
    the dashboard at https://concentrate.ai where you can set:
      - Spending limits and budgets
      - Guardrails (PII redaction)
      - Zero Data Retention (ZDR)
      - Request logging

    This implementation generates a deterministic key offline that
    encodes the spending cap. The key name format is sk-cn-{hash}-{salt}.

    Args:
        master_key: The master API key
        spend_cap: The spending cap (e.g., "5.00" for $5)
        salt: Random salt for uniqueness
        prefix: Optional prefix (unused, but kept for interface consistency)

    Returns:
        A deterministic limited key string starting with sk-cn-
    """
    key_material = f"{master_key}:{spend_cap}:{salt}"
    key_hash = hashlib.sha256(key_material.encode()).hexdigest()

    return f"sk-cn-{key_hash[:12]}-{salt}"

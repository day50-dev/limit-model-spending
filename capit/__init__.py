#!/usr/bin/env python3
"""capit - Issue authentication keys with spending caps.

Usage:
    capit openrouter 1.00                    # Issue a limited key
    capit openrouter 1.00 --prefix prod      # With a prefix
    capit openrouter 1.00 --agent openclaw   # Send to agent
    capit --keys list                        # List master keys
    capit --keys remote openrouter           # List API keys from platform
    capit --platforms                        # List platforms
"""

import sys
import os
import signal
import json
import hashlib
import secrets
import logging
import shutil
from pathlib import Path
from datetime import datetime

import click

# Configuration directory
CAPIT_DIR = Path.home() / ".local" / "capit"
SCRIPT_DIR = Path(__file__).parent
PLATFORMS_DIR = SCRIPT_DIR / "platforms"
STORES_DIR = SCRIPT_DIR / "stores"
MASTER_LOOKUP_FILE = CAPIT_DIR / "master-lookup"

# Handle Ctrl+C gracefully
def handle_sigint(signum, frame):
    click.echo("", err=True)
    logger.error("User interrupted.")
    sys.exit(130)

signal.signal(signal.SIGINT, handle_sigint)

# Setup logging - respect LOGLEVEL environment variable
log_level = os.getenv('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.WARNING)
)
logger = logging.getLogger('capit')


def ensure_capit_dir():
    """Ensure the capit configuration directory exists."""
    CAPIT_DIR.mkdir(parents=True, exist_ok=True)


def load_master_lookup():
    """Load the master key lookup table."""
    if not MASTER_LOOKUP_FILE.exists():
        return {}
    with open(MASTER_LOOKUP_FILE, "r") as f:
        return json.load(f)


def save_master_lookup(lookup):
    """Save the master key lookup table."""
    ensure_capit_dir()
    with open(MASTER_LOOKUP_FILE, "w") as f:
        json.dump(lookup, f, indent=2)


def get_module(directory: Path, module_name: str):
    """Dynamically load a module from a directory."""
    module_file = directory / f"{module_name}.py"
    if not module_file.exists():
        raise click.ClickException(f"Module '{module_name}' not found")

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_platform_module(platform_name):
    return get_module(PLATFORMS_DIR, platform_name)


def get_store_module(store_name):
    return get_module(STORES_DIR, store_name)


def list_modules(directory: Path) -> list:
    """List all modules in a directory, filtering out internal files.
    
    Skips:
    - __init__.py
    - Files starting with _ (private/internal modules)
    - Files ending with .disabled
    
    Args:
        directory: Path to the directory to scan
        
    Returns:
        List of module names (without .py extension)
    """
    modules = []
    if directory.exists():
        for f in directory.glob("*.py"):
            if f.name != "__init__.py" and not f.name.startswith("_") and not f.name.endswith(".disabled"):
                modules.append(f.stem)
    return modules


def list_platforms():
    """List all available platforms."""
    return list_modules(PLATFORMS_DIR)


def show_platforms(lookup=None, indent=0):
    """Display platforms with their configuration status.
    
    Args:
        lookup: Master key lookup dict (loaded if None)
        indent: Number of spaces to indent each line (default 0)
    """
    if lookup is None:
        lookup = load_master_lookup()
    
    platforms = list_platforms()
    if not platforms:
        click.echo("No platforms installed")
        return
    
    click.echo(click.style("Platforms", bold=True), err=True)
    prefix = " " * indent
    for platform in platforms:
        status = "✓ configured" if platform in lookup else "✗ not configured"
        click.echo(f"{prefix}{platform:<20} {status}")


def list_stores():
    """List all available stores."""
    return list_modules(STORES_DIR)


def prompt_for_master_key(platform: str) -> str:
    """Prompt user for a master key with platform-specific instructions.
    
    Args:
        platform: The platform name
        
    Returns:
        The entered master key
    """
    # Try to get platform-specific setup info
    platform_file = PLATFORMS_DIR / f"{platform}.py"
    setup_url = None
    setup_instructions = None
    
    if platform_file.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location(platform, platform_file)
        platform_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(platform_module)
        setup_url = getattr(platform_module, 'SETUP_URL', None)
        setup_instructions = getattr(platform_module, 'SETUP_INSTRUCTIONS', None)
    
    if setup_url:
        click.echo("", err=True)
        if setup_instructions:
            click.echo(f"  {setup_instructions}", err=True)
        else:
            click.echo("  You need a special key to create capped API keys", err=True)
        click.echo("  Create one and find out more at the link below", err=True)
        click.echo("", err=True)
        click.echo(f"  {setup_url}", err=True)
        click.echo("", err=True)
        click.echo("  Everything is stored local-only or, optionally, not at all.", err=True)
        click.echo("  There are no capit servers and nothing is sent to us.", err=True)
        click.echo("", err=True)
        click.echo("―" * 60, err=True)
        click.echo("", err=True)
        return click.prompt("Enter Key", hide_input=True, err=True)
    else:
        click.echo("", err=True)
        return click.prompt("Key", hide_input=True, err=True)


def get_master_key(platform, store_name=None):
    """Get master key for a platform, prompting if not stored.
    
    Returns:
        Tuple of (master_key, store_name, was_stored)
        - was_stored=True if key was found in storage
        - was_stored=False if user was prompted (ephemeral)
    """
    lookup = load_master_lookup()

    if platform in lookup:
        store_name = store_name or lookup[platform].get("store", "dotenv")
        store_module = get_store_module(store_name)
        master_key = store_module.retrieve_key(platform)
        if master_key:
            return master_key, store_name, True

    # Key not found - prompt for it
    master_key = prompt_for_master_key(platform)
    return master_key, "ephemeral", False


def do_issue(platform, spend_cap, prefix=None, verbose=False, send_to=None, confirm=True):
    """Issue a limited key for a platform with a spending cap."""
    ensure_capit_dir()

    # Handle unlimited budget (0)
    if spend_cap == "0":
        spend_cap = "unlimited"

    if verbose:
        logger.setLevel(logging.DEBUG)
        click.echo(f"Looking up platform: {platform}", err=True)

    # Get master key (prompts if not stored)
    master_key, store_name, was_stored = get_master_key(platform)

    # Nag user to store the key if they didn't have it stored
    if not was_stored:
        click.echo("", err=True)
        click.echo(f"To store this key for future use, run:", err=True)
        click.echo(f"  capit --platforms add {platform}", err=True)
        click.echo("", err=True)

    if verbose:
        if store_name == "ephemeral":
            click.echo("Using ephemeral key (not stored)", err=True)
        else:
            click.echo(f"Using store: {store_name}", err=True)
            click.echo(f"Master key found (format: {master_key[:12]}...)", err=True)

    # Load platform module
    platform_module = get_platform_module(platform)

    if verbose:
        click.echo(f"Loaded platform module: {platform_module.PLATFORM_NAME}", err=True)

    # Check if platform supports online key creation (has API_BASE constant)
    if hasattr(platform_module, 'create_limited_key') and hasattr(platform_module, 'API_BASE'):
        if verbose:
            click.echo("Platform uses online key creation (API calls)", err=True)

        # If sending to an agent, show diff FIRST, then create key after confirmation
        if send_to and confirm:
            # Get agent module to show diff
            agent_module = get_agent_module(send_to)
            if not agent_module:
                available = list_agents()
                logger.error(
                    "Unknown agent '%s'.\nSupported agents: %s",
                    send_to, ', '.join(available) if available else 'none'
                )
                sys.exit(1)

            if not hasattr(agent_module, 'show_diff'):
                # Agent doesn't support diff, just ask
                click.echo(f"\nConfigure {send_to} with a new {platform} key (spending limit: ${spend_cap})?", err=True)
                if not click.confirm("Continue?", default=True, err=True):
                    click.echo("Aborted.", err=True)
                    return None
            else:
                # Show diff with placeholder, ask for confirmation
                if not agent_module.show_diff(platform, spend_cap, send_to):
                    click.echo("Aborted.", err=True)
                    return None

            # Now create the key after confirmation
            salt = secrets.token_hex(8)
            try:
                limited_key = _create_limited_key_with_handler(platform_module, master_key, spend_cap, salt, prefix=prefix, verbose=verbose)
                return handle_send_to(send_to, limited_key, platform, spend_cap, confirm=False)
            except Exception as e:
                _handle_key_creation_error(e, platform_module)
        
        # No agent or no confirmation needed - just create the key
        salt = secrets.token_hex(8)
        try:
            limited_key = _create_limited_key_with_handler(platform_module, master_key, spend_cap, salt, prefix=prefix, verbose=verbose)
            if send_to:
                return handle_send_to(send_to, limited_key, platform, spend_cap, confirm=False)
            return limited_key
        except Exception as e:
            _handle_key_creation_error(e, platform_module)

    # Platform doesn't support online creation - use offline mode
    if verbose:
        click.echo("Platform uses offline key generation (no API calls)", err=True)

    salt = secrets.token_hex(8)
    key_material = f"{master_key}:{platform}:{spend_cap}:{salt}"
    key_hash = hashlib.sha256(key_material.encode()).hexdigest()
    platform_prefix = "".join([c for c in platform if c.isalpha()])[:6]
    # Handle unlimited in key format
    key_limit = "unlimited" if spend_cap == "unlimited" else spend_cap.replace('.', '')
    limited_key = f"sk-{platform_prefix}-{key_limit}-{key_hash[:12]}-{salt}"

    if verbose:
        click.echo(f"Generated offline key with format: sk-{platform_prefix}-...", err=True)

    return limited_key


def _handle_key_creation_error(e, platform_module):
    error_msg = str(e)
    if "401" in error_msg or "Unauthorized" in error_msg:
        setup_url = getattr(platform_module, 'SETUP_URL', f"{platform_module.PLATFORM_URL}/settings")
        logger.error(
            "API authentication failed. Your management key may be invalid.\n"
            "Get a new key from: %s",
            setup_url
        )
        sys.exit(1)
    elif "403" in error_msg or "Forbidden" in error_msg:
        logger.error(
            "API access forbidden. Your management key lacks required permissions."
        )
        sys.exit(1)
    elif "connection" in error_msg.lower() or "network" in error_msg.lower():
        logger.error(
            "Network error: Could not connect to %s", platform_module.PLATFORM_URL
        )
        sys.exit(1)
    else:
        logger.error("Failed to create limited key via API:\n%s", error_msg)
        sys.exit(1)


def _create_limited_key_with_handler(platform_module, master_key, spend_cap, salt, prefix=None, verbose=False):
    limited_key = platform_module.create_limited_key(master_key, spend_cap, salt, prefix=prefix)
    if verbose:
        click.echo(f"Key created successfully via API", err=True)
    return limited_key


AGENTS_DIR = SCRIPT_DIR / "agents"


def list_agents():
    """List all available agents."""
    # Get all modules, then filter out lib.py (shared library)
    modules = list_modules(AGENTS_DIR)
    return [m for m in modules if m != "lib"]


def get_agent_module(agent_name):
    """Dynamically load an agent module."""
    return get_module(AGENTS_DIR, agent_name)


def handle_send_to(agent, key, platform, spend_cap, confirm=True):
    """Send the generated key to an agent.

    Args:
        agent: The agent name
        key: The generated limited API key
        platform: The platform name
        spend_cap: The spending cap
        confirm: If False, skip diff and confirmation (key already confirmed)
    """
    # Try to load agent module dynamically
    agent_module = get_agent_module(agent)

    if not agent_module:
        available = list_agents()
        logger.error(
            "Unknown agent '%s'.\nSupported agents: %s",
            agent, ', '.join(available) if available else 'none (add one to capit/agents/)'
        )
        sys.exit(1)

    if not hasattr(agent_module, 'send'):
        logger.error(
            "Agent '%s' is missing a 'send' function.\n"
            "See capit/agents/example.py for the required interface.",
            agent
        )
        sys.exit(1)

    # Agent module handles diff and final confirmation
    # If confirm=False, skip all prompts and just install
    return agent_module.send(key, platform, spend_cap, confirm=confirm)


# =============================================================================
# MAIN CLI - Key issuance is the default
# =============================================================================

@click.command(context_settings=dict(
    ignore_unknown_options=False,
    allow_extra_args=False,
    help_option_names=['--help', '-h']
))
@click.argument("platform", required=False)
@click.argument("spend_cap", required=False)
@click.option("--prefix", "-p", help="Prefix for key organization")
@click.option("--agent", "-a", metavar="AGENT", help="Send key to AI agent (claude, cursor, hermes, windsurf, ...)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation when configuring agent")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
@click.pass_context
def main(ctx, platform, spend_cap, prefix, agent, yes, verbose):
    """capit - Cap spending on your AI agents.

\b
Issue a limited key:
  capit openrouter 1.00
  capit openrouter 5.00 --prefix prod
  capit openrouter 1.00 --agent openclaw
  capit openrouter 0        # Unlimited budget

\b
Administration:
  capit --keys list               List all keys with spending info
  capit --keys list openrouter    List keys from specific provider
  capit --keys delete <pattern>   Permanently delete key(s)
  capit --platforms               List platforms
  capit --platforms add           Add a master key
  capit --platforms remove        Remove a master key
  capit --stores                  List available stores
  capit --agents                  List available agents

\b
Capit is a DAY50 tool. day50.dev
"""
    # Check for help flag explicitly
    if '--help' in sys.argv or '-h' in sys.argv:
        click.echo(ctx.get_help())
        ctx.exit(0)

    # Show help if no arguments
    if platform is None and spend_cap is None:
        click.echo(ctx.get_help())
        ctx.exit(0)

    # Require both arguments for key issuance
    if not platform or not spend_cap:
        click.echo("Error: Both PLATFORM and SPEND_CAP are required")
        click.echo("Usage: capit <platform> <spend_cap>")
        click.echo("       capit --help")
        ctx.exit(1)

    # Auto-set prefix based on agent if not explicitly provided
    if agent and not prefix:
        prefix = agent

    try:
        key = do_issue(
            platform, spend_cap,
            prefix=prefix,
            verbose=verbose,
            send_to=agent,
            confirm=not yes
        )
        if not agent:
            click.echo(key)
    except Exception as e:
        if verbose:
            import traceback
            traceback.print_exc()
        logger.error(str(e))
        sys.exit(1)


# =============================================================================
# Administration commands (-- prefixed, Unix style)
# =============================================================================

@click.group()
def admin():
    """Administration commands."""
    pass


def _parse_key_pattern(pattern, lookup):
    """Parse a key pattern and return matching keys across providers.
    
    Patterns supported:
    - "name" - exact match or glob across all providers
    - "provider/name" - exact match or glob on specific provider
    - "name*" or "*name" or "name*pattern" - glob matching
    
    Returns list of tuples: (platform, key_id, key_data)
    """
    import fnmatch
    
    matches = []
    
    # Check if pattern includes provider prefix
    if "/" in pattern:
        parts = pattern.split("/", 1)
        provider_filter = parts[0]
        name_pattern = parts[1]
    else:
        provider_filter = None
        name_pattern = pattern
    
    # Determine which providers to search
    providers_to_search = []
    if provider_filter:
        if provider_filter in lookup:
            providers_to_search = [provider_filter]
        else:
            return []  # Provider not found
    else:
        providers_to_search = list(lookup.keys())
    
    # Search each provider
    for platform in providers_to_search:
        info = lookup[platform]
        store_module = get_store_module(info["store"])
        master_key = store_module.retrieve_key(platform)
        if not master_key:
            continue
        platform_module = get_platform_module(platform)
        if not hasattr(platform_module, 'list_keys'):
            continue
        try:
            keys = platform_module.list_keys(master_key)
            for key in keys:
                key_name = key.get("name", key.get("label", ""))
                # Check if name matches pattern (glob or exact)
                if fnmatch.fnmatch(key_name, name_pattern):
                    # Get key ID - try multiple field names
                    key_id = key.get("id") or key.get("hash") or key.get("key_id")
                    if key_id:
                        matches.append((platform, key_id, key))
        except Exception:
            continue
    
    return matches


def _find_key_by_name(platform_module, master_key, key_name):
    """Find a key by name and return its ID."""
    keys = platform_module.list_keys(master_key)
    for key in keys:
        name = key.get("name", key.get("label", ""))
        if name == key_name:
            return key.get("id"), key
    return None, None


@admin.command("keys", context_settings=dict(
    ignore_unknown_options=True,
    help_option_names=[]  # Disable click's built-in --help handling
))
@click.argument("subcommand", required=False)
@click.argument("args", nargs=-1)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def keys_cmd(subcommand, args, verbose):
    """Manage keys."""
    import fnmatch

    # Check for --help explicitly to show nice help screen
    if "--help" in sys.argv or "-h" in sys.argv:
        click.echo("Usage: capit --keys <command> [args]")
        click.echo("")
        click.echo("Commands:")
        click.echo("  list                     List all keys from all providers")
        click.echo("  list <provider>          List keys from specific provider")
        click.echo("  list <provider> <prefix> Filter keys by prefix")
        click.echo("  delete <pattern>         Permanently delete key(s)")
        click.echo("")
        click.echo("Patterns:")
        click.echo("  name              Exact match or glob across all providers")
        click.echo("  provider/name     Match on specific provider")
        click.echo("  name*             Glob pattern (e.g., 'capit-*')")
        click.echo("")
        click.echo("Examples:")
        click.echo("  capit --keys list")
        click.echo("  capit --keys list openrouter")
        click.echo("  capit --keys delete claude-71ad2519")
        click.echo("  capit --keys delete 'capit-*'")
        click.echo("  capit --keys delete 'openrouter/capit-*'")
        sys.exit(0)

    # If no subcommand, default to list all
    if subcommand is None:
        subcommand = "list"
        args = tuple()

    if subcommand == "list":
        if not args:
            # List keys from all registered providers with namespaced names
            lookup = load_master_lookup()
            if not lookup:
                click.echo("No keys registered")
                click.echo("")
                show_platforms(lookup=lookup, indent=2)
            else:
                all_keys = []
                for platform, info in lookup.items():
                    store_module = get_store_module(info["store"])
                    master_key = store_module.retrieve_key(platform)
                    if not master_key:
                        continue
                    platform_module = get_platform_module(platform)
                    if not hasattr(platform_module, 'list_keys'):
                        continue
                    try:
                        keys = platform_module.list_keys(master_key)
                        for key in keys:
                            key_with_provider = {
                                **key,
                                "_provider": platform,
                                "_namespaced_name": f"{platform}/{key.get('name', key.get('label', 'unnamed'))}"
                            }
                            all_keys.append(key_with_provider)
                    except Exception:
                        # Skip providers that can't be reached
                        pass
                # Sort by namespaced name
                all_keys = sorted(all_keys, key=lambda k: k.get("_namespaced_name", "").lower())
                # Print header with unicode box drawing
                click.echo(f"{'NAME':<40} {'USED':>8} {'LIMIT':>10} {'CREATED':<12}")
                click.echo("─" * 72)
                for key in all_keys:
                    key_name = key.get("_namespaced_name", "unknown")
                    limit_val = key.get("limit")
                    usage_val = key.get("usage", 0) or 0
                    if limit_val is not None:
                        limit_str = f"{limit_val:.2f}"
                        used_str = f"{usage_val:.2f}"
                        # Calculate percentage used
                        pct_used = (usage_val / limit_val * 100) if limit_val > 0 else 0
                        if pct_used >= 90:
                            used_str = click.style(used_str, fg="red")
                        elif pct_used >= 50:
                            used_str = click.style(used_str, fg="yellow")
                    else:
                        limit_str = "unlimited"
                        used_str = f"{usage_val:.2f}"
                    created = key.get("created_at", "")[:10] if key.get("created_at") else ""
                    click.echo(f"{key_name:<40} {used_str:>8} {limit_str:>10} {created:<12}")
                click.echo(f"\nTotal: {len(all_keys)} key(s)")
        else:
            # List keys from specific provider
            platform = args[0]
            # Support prefix as positional arg
            prefix = args[1] if len(args) > 1 else None
            ensure_capit_dir()
            lookup = load_master_lookup()
            if platform not in lookup:
                click.echo(f"No master key found for '{platform}'")
                sys.exit(1)
            store_module = get_store_module(lookup[platform]["store"])
            master_key = store_module.retrieve_key(platform)
            platform_module = get_platform_module(platform)
            if not hasattr(platform_module, 'list_keys'):
                click.echo(f"Provider '{platform}' doesn't support listing keys")
                sys.exit(1)
            keys = platform_module.list_keys(master_key)
            # Filter by prefix if specified (glob-style matching)
            if prefix:
                filtered_keys = [k for k in keys if fnmatch.fnmatch(k.get("name", k.get("label", "")), prefix)]
                keys = filtered_keys
            # Print header with unicode box drawing
            click.echo(f"{'NAME':<35} {'USED':>8} {'LIMIT':>10} {'CREATED':<12}")
            click.echo("─" * 67)
            # Sort by name for intuitive grouping
            keys = sorted(keys, key=lambda k: k.get("name", k.get("label", "")).lower())
            for key in keys:
                key_name = key.get("name", key.get("label", "unnamed"))
                limit_val = key.get("limit")
                usage_val = key.get("usage", 0) or 0
                if limit_val is not None:
                    limit_str = f"{limit_val:.2f}"
                    used_str = f"{usage_val:.2f}"
                    # Calculate percentage used
                    pct_used = (usage_val / limit_val * 100) if limit_val > 0 else 0
                    if pct_used >= 90:
                        used_str = click.style(used_str, fg="red")
                    elif pct_used >= 50:
                        used_str = click.style(used_str, fg="yellow")
                else:
                    limit_str = "unlimited"
                    used_str = f"{usage_val:.2f}"
                created = key.get("created_at", "")[:10] if key.get("created_at") else ""
                click.echo(f"{key_name:<35} {used_str:>8} {limit_str:>10} {created:<12}")
            click.echo(f"\nTotal: {len(keys)} key(s)")
        return

    if not args:
        click.echo("Usage: capit --keys <command> [args]")
        click.echo("")
        click.echo("Commands:")
        click.echo("  list                     List all keys from all providers")
        click.echo("  list <provider>          List keys from specific provider")
        click.echo("  list <provider> <prefix> Filter keys by prefix")
        click.echo("  delete <pattern>         Permanently delete key(s)")
        click.echo("")
        click.echo("Patterns:")
        click.echo("  name              Exact match or glob across all providers")
        click.echo("  provider/name     Match on specific provider")
        click.echo("  name*             Glob pattern (e.g., 'capit-*')")
        click.echo("")
        click.echo("Examples:")
        click.echo("  capit --keys delete claude-71ad2519")
        click.echo("  capit --keys delete 'capit-*'")
        click.echo("  capit --keys delete 'openrouter/capit-*'")
        return

    elif subcommand in ("delete", "remove"):
        if not args:
            click.echo("Usage: capit --keys delete <pattern>")
            sys.exit(1)
        pattern = args[0]
        ensure_capit_dir()
        lookup = load_master_lookup()
        matches = _parse_key_pattern(pattern, lookup)
        if not matches:
            click.echo(f"No keys matching '{pattern}'")
            sys.exit(1)
        deleted_count = 0
        for platform, key_id, key_data in matches:
            key_name = key_data.get("name", key_data.get("label", ""))
            store_module = get_store_module(lookup[platform]["store"])
            master_key = store_module.retrieve_key(platform)
            platform_module = get_platform_module(platform)
            if not hasattr(platform_module, 'delete_key'):
                click.echo(f"Provider '{platform}' doesn't support deleting keys")
                continue
            try:
                platform_module.delete_key(master_key, key_id)
                click.echo(f"Deleted: {platform}/{key_name}")
                deleted_count += 1
            except Exception as e:
                click.echo(f"Error deleting {platform}/{key_name}: {e}")
        click.echo(f"\nDeleted {deleted_count} key(s)")
        return

    else:
        click.echo(f"Unknown command: {subcommand}")
        sys.exit(1)


@admin.command("platforms")
@click.argument("subcommand", required=False)
@click.argument("args", nargs=-1)
def platforms_cmd(subcommand, args):
    """Manage platforms and master keys."""
    lookup = load_master_lookup()
    
    if subcommand is None:
        platforms = list_platforms()
        if not platforms:
            click.echo("No platforms installed")
        else:
            click.echo("Usage: capit --platforms <command> [args]")
            click.echo("")
            click.echo("Commands:")
            click.echo("  list    List available platforms")
            click.echo("  add     Add a master key")
            click.echo("  remove  Remove a master key")
            click.echo("")
            show_platforms(lookup=lookup, indent=2)
        return

    if subcommand == "list":
        show_platforms(lookup=lookup, indent=0)
        return

    if subcommand == "add":
        if not args:
            click.echo("Usage: capit --platforms add <platform>")
            sys.exit(1)
        platform = args[0]
        ensure_capit_dir()

        # Use shared prompt function for consistent UX
        master_key = prompt_for_master_key(platform)

        stores = list_stores()
        default_store = "dotenv" if "dotenv" in stores else stores[0]
        store_module = get_store_module(default_store)
        store_module.store_key(platform, master_key)
        lookup = load_master_lookup()
        lookup[platform] = {"store": default_store, "added_at": datetime.now().isoformat()}
        save_master_lookup(lookup)
        click.echo("Master key added")
        return

    if subcommand == "remove":
        if not args:
            click.echo("Usage: capit --platforms remove <platform>")
            sys.exit(1)
        platform = args[0]
        lookup = load_master_lookup()
        if platform not in lookup:
            click.echo(f"No master key found for '{platform}'")
            sys.exit(1)
        store_module = get_store_module(lookup[platform]["store"])
        store_module.delete_key(platform)
        del lookup[platform]
        save_master_lookup(lookup)
        click.echo("Master key removed")
        return

    click.echo(f"Unknown command: {subcommand}")
    sys.exit(1)


@admin.command("stores")
def stores_cmd():
    """List all available stores."""
    stores = list_stores()
    if not stores:
        click.echo("No stores installed")
    else:
        for store in stores:
            click.echo(store)


@admin.command("agents")
def agents_cmd():
    """List all available agents."""
    agents = list_agents()
    if not agents:
        click.echo("No agents installed")
    else:
        for agent in agents:
            click.echo(agent)


@admin.command("enable")
@click.argument("platform")
def enable_cmd(platform):
    """Enable a platform."""
    platform_file = PLATFORMS_DIR / f"{platform}.py"
    disabled_file = PLATFORMS_DIR / f"{platform}.py.disabled"
    if disabled_file.exists():
        disabled_file.rename(platform_file)
        click.echo(f"Platform '{platform}' enabled")
    elif platform_file.exists():
        click.echo(f"Platform '{platform}' is already enabled")
    else:
        click.echo(f"Platform '{platform}' not found")
        sys.exit(1)


@admin.command("disable")
@click.argument("platform")
def disable_cmd(platform):
    """Disable a platform."""
    platform_file = PLATFORMS_DIR / f"{platform}.py"
    disabled_file = PLATFORMS_DIR / f"{platform}.py.disabled"
    if platform_file.exists():
        platform_file.rename(disabled_file)
        click.echo(f"Platform '{platform}' disabled")
    elif disabled_file.exists():
        click.echo(f"Platform '{platform}' is already disabled")
    else:
        click.echo(f"Platform '{platform}' not found")
        sys.exit(1)


@admin.command("serve")
@click.option("--port", "-p", default=0, help="Port to listen on (0 for random)")
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
def serve_cmd(port, host):
    """Start the capit web server."""
    from capit.server import create_server
    # Port 0 means random available port
    if port == 0:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, 0))
        port = s.getsockname()[1]
        s.close()
    
    click.echo(f"capit web server running on http://{host}:{port}")
    create_server(port=port, host=host)


def cli():
    """Main entry point."""
    # Check for --help/-h/--version first - always handle these
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        main()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        from importlib.metadata import version
        click.echo(version("capit"))
        return

    # Check for -- prefixed admin commands and translate them
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # Map --command to command
        if arg.startswith("--") and len(arg) > 2:
            sys.argv[1] = arg[2:]  # Remove -- prefix

        # Check if it's an admin command
        admin_commands = {"keys", "platforms", "stores", "agents", "enable", "disable", "serve"}
        if sys.argv[1] in admin_commands:
            admin()
            return

    main()


if __name__ == "__main__":
    cli()

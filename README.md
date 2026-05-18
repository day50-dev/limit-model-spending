<p align="center">
<img width="500" alt="capit_500" src="https://github.com/user-attachments/assets/db22c959-ffee-4540-9108-2928e9c73f70" />
<br/>
<a href=https://pypi.org/project/capit><img src=https://badge.fury.io/py/capit.svg/></a>
<br/><strong>Budget per-agent, per-provider, as little or as much as you want</strong>
</p>

Ever been sticker shocked with a high inference bill only to find that the agent got stuck in some unproductive loop?

You need to manage the spending independent of the broken tool and broken agent. 

**capit**, part of the [DAY50](https://day50.dev) suite of open-source tools for AI workflows, allows for managing application-based key management with cost capping.

## GUI

```bash
$ uvx capit serve
```

<img width="1167" height="934" alt="capit-ss" src="https://github.com/user-attachments/assets/bd0ba5b4-3a01-4b25-b488-7317ba694d86" />


## TUI

```bash
$ uvx capit openrouter 5.00 --agent openclaw
$5.00 openrouter key installed into openclaw
Old configuration backed up to /tmp/capit-openclaw-no22x7b1
```

That's it. Openclaw now has a capped API key. If it goes rogue, it can only cost you $5.

**Everything is stored local-only or, optionally, not at all.**

**There are no capit servers and nothing is sent to us.**

---

## Install

```bash
uv tool install capit
```

## Usage

### Give an agent a budget

```bash
# Claude Code - $5 cap
capit openrouter 5.00 --agent claude

# Cursor - $10 cap
capit openrouter 10.00 --agent cursor

# Windsurf - $5 cap
capit openrouter 5.00 --agent windsurf

# Hermes - $5 cap
capit openrouter 5.00 --agent hermes

# OpenClaw - $5 cap
capit openrouter 5.00 --agent openclaw
```

Each agent gets its own capped key. Sleep soundly.

### More agents

```bash
capit --agents  # List all supported agents
```

See [agents/README.md](capit/agents/README.md) for the full list and adding custom agents.

## Platforms

The included platforms are [openrouter](https://openrouter.ai) and [aihubmix](https://aihubmix.com).

Platforms are easy to create with a claude skill located in `skills/platform-creator.md`.

See [platforms/README.md](capit/platforms/README.md) for more details.

---

## Administration

```bash
capit --keys list              # List all keys with spending info
capit --keys list openrouter   # List keys from specific provider
capit --keys delete <name>     # Delete a key (e.g., claude-71ad2519)
capit --keys delete 'capit-*'  # Delete keys matching pattern
capit --platforms              # List available platforms
capit --platforms add          # Add a master key
capit --platforms remove       # Remove a master key
capit --agents                 # List supported agents
```

---

## How It Works

1. You run `capit openrouter 5.00 --agent claude`
2. capit calls OpenRouter's API
3. capit creates a **guardrail** with $5 cap
4. capit creates an **API key** with that guardrail
5. capit writes the key to `~/.claude/.credentials.json`
6. Done

The cap is **enforced by OpenRouter**. The key literally cannot spend more than $5.

---

**MIT License**

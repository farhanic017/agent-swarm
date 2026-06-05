# Auto Model Switcher

**Never get blocked by "out of credits" again.** Auto-discovers all your AI
models across providers, monitors their health in parallel (<5s), and seamlessly
rotates when one runs out — all without you lifting a finger.

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-green)]()
[![License](https://img.shields.io/badge/license-GPLv3-purple)](LICENSE)
[![Author](https://img.shields.io/badge/author-Farhan%20Dhrubo-red)](https://github.com/farhanic017)

---

## Drop-in Install

Give this repo URL to **any AI agent** and say "install":

```
https://github.com/farhanic017/auto-model-switcher
```

The AI reads `SKILL.md`, clones, installs, and configures everything.
Zero manual steps.

### Manual Install

```bash
git clone https://github.com/farhanic017/auto-model-switcher.git
cd auto-model-switcher
python install.py
```

---

## The Problem

You're in the middle of work and suddenly get rate-limited or hit 0 credits.
Now you have to: stop, check which models have credits, dig into config files,
manually switch, and restart. **Every. Single. Time.**

## The Solution

```
python switcher.py watch
```

Scans your CLI configs (OpenCode, Claude Code, Cursor, Windsurf, Aider, etc.),
discovers every model you have access to, checks their health in parallel, and
when one fails — automatically rotates to the next working model.

**Free models get priority.** Paid models are fallbacks. Zero config needed.

---

## Supported Providers (48+ models auto-discovered)

| Provider | Models | Detection | Priority |
|----------|--------|-----------|----------|
| Google AI (free) | 4 Gemini models | Config + env | 1st — free |
| OpenRouter (free) | 30+ free models | `:free` suffix | 2nd — free |
| OpenRouter (paid) | 4+ paid models | No `:free` | 3rd — paid |
| Azure OpenAI | 10+ deployments | `azure-openai` provider | 4th — paid |
| OpenAI | Any GPT model | `OPENAI_API_KEY` env | Fallback |
| Anthropic | Claude models | `ANTHROPIC_API_KEY` env | Fallback |

### Local Models (auto-detected)

| Runtime | Endpoint | Detection |
|---------|----------|-----------|
| **Ollama** | `http://localhost:11434` | Auto-scans, lists all models |
| **LM Studio** | `http://localhost:1234` | Server running check |
| **vLLM** | `http://localhost:8000` | Server running check |

---

## Commands

| Command | What it does |
|---------|-------------|
| `python switcher.py discover` | Scans all configs + env, lists every model found |
| `python switcher.py status` | Shows active model, health, depletion ETAs |
| `python switcher.py switch --task coding` | Picks best model for a task (coding/chat/reasoning/general) |
| `python switcher.py watch` | Background daemon — checks every 2min, auto-rotates |

### Or use the `ams` command after install:

```bash
ams status      # Same as above
ams switch      # Rotate to best model
ams watch       # Background daemon
ams discover    # List all models
```

---

## Task-Aware Model Selection

The switcher doesn't just pick a random model — it picks the **best model for
what you're doing**:

| Task | Models preferred | Example scores |
|------|-----------------|---------------|
| **coding** | qwen3-coder, gpt-4.1, deepseek-coder | 55 bonus |
| **reasoning** | o4, o3, deepseek-r1, kimi, qwen3-next | 50 bonus |
| **chat** | gemma-4, nemotron, gpt-5.4, llama-3.3 | 40 bonus |
| **general** | Falls back to capability tiers | 15-25 bonus |

Auto-detects task from project files (`package.json`, `*.py`, `requirements.txt`,
`Cargo.toml`, etc.) or use `--task` to override.

---

## How It Works

### 1. Auto-Discovery

Reads your existing CLI configs — no extra setup:

- **OpenCode**: `opencode.jsonc` — extracts all `provider` sections
- **Claude Code**: `CLAUDE.md` — extracts `model:` line
- **Cursor**: `.cursorrules` / `settings.json`
- **Windsurf / Aider / Continue.dev**: Based on env configs
- **Environment**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`

### 2. Parallel Health Checking (<5s)

All 48+ models checked simultaneously via connection-pooled session:

| Optimization | Impact |
|-------------|--------|
| Connection pooling (keep-alive) | Eliminates TCP handshake per check |
| Cache for ALL healthy models (120s TTL) | Subsequent calls near-instant |
| Reduced timeouts (4s-5s) | Worst case bound at 5s |
| Deduplication by API key | One check per provider, not per model |

Before optimization: **~19s**. After: **~5s first call, ~0.1s cached calls**.

### 3. Smart Scoring (0-250)

Each model scored on: health (base 100) + free tier bonus (+50) + specialty
strength (+up to 55) + reliability (+15 Azure, -5 free OpenRouter).

### 4. Rotation & Recovery

- Failed models marked **depleted** with cooldown (respects `Retry-After` header)
- CLI config updated automatically (`opencode.jsonc` `model` field)
- After cooldown, model is re-checked and re-enters pool if healthy
- When ALL models depleted: shows **per-model recovery ETA** sorted fastest-first

---

## Context Passing (MCP Handoff)

When switching models mid-session, the switcher preserves:

- Which tools already executed (so new model doesn't repeat)
- Which files were modified
- Last 5 terminal commands
- Conversation summary

Saved to `~/.auto-model-switcher/context.json` for the next model to read.

---

## Always-On Integration

| Method | What it does |
|--------|-------------|
| **PowerShell Profile Hook** | Checks health on every shell start (<2s) |
| **PATH Wrappers** | `.bat` files intercept `opencode`/`claude`/`cursor`/`aider`/`windsurf` calls |
| **Watch Mode** | Background daemon checks every 2min, auto-rotates on failure |
| **Startup Task** | Windows Task Scheduler launches watch on boot |
| **WMI Watchdog** | Invisible background process, starts/stops with opencode.exe |
| **Desktop Shortcuts** | One-click status, switch, watch |

### Adding a new CLI

The auto-switch wrapper system is **future-proof**. To add support for any new
CLI or agent:

1. Add its path to `install.py` → `clis` dict (around line 119)
2. Re-run `python install.py`
3. Or manually create a `.bat` wrapper in `~/.auto-model-switcher/bin/`

The architecture is designed so **any future CLI, agent, or MCP server** can
be added by simply registering its path.

---

## For AI Agents (Drop-in Install)

Give this repo URL to **any AI assistant**:

```
https://github.com/farhanic017/auto-model-switcher
```

The AI reads `SKILL.md` and handles everything: cloning, installing, configuring.

---

## Project Structure

```
auto-model-switcher/
├── switcher.py          # Core engine (1222 lines)
├── install.py           # Universal installer
├── restore.ps1          # Windows restore script
├── SKILL.md             # AI agent instructions
├── README.md            # This file
├── LICENSE              # GPL-3.0
├── NOTICE               # Copyright and legal notices
├── .gitignore
├── data/                # Runtime state templates
├── hooks/               # CLI integration hooks
└── tests/
    ├── test_switcher.py # 26 test cases, all passing
    └── debug_speed.py   # Performance profiler
```

---

## Copyright & License

**Copyright (c) 2026 Farhan Dhrubo** — All rights reserved.

This project is licensed under the **GNU General Public License v3.0**.
See [LICENSE](LICENSE) and [NOTICE](NOTICE) for full details.

**You may NOT:**
- Remove or alter any copyright notice in any file
- Re-distribute this software or any derivative as your own work
  without clear attribution to the original author
- Sell this software or any derivative without explicit permission

**Required attribution:** Any use, distribution, or derivative work MUST include:
"Originally created by Farhan Dhrubo (github.com/farhanic017)"

Every source file in this repository contains an embedded copyright notice
making the origin unambiguous. The GPL-3.0 license ensures all derivative
works remain open-source and properly attributed.

---

*Built with Python, caffeine, and the frustration of getting 402 errors
mid-session.*

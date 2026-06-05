# Auto Model Switcher — AI Agent Install Skill

**Copyright (c) 2026 Farhan Dhrubo** — GPL-3.0 License

Auto-discovers all AI models from CLI configs and environment variables. Builds
a priority chain (free models first, paid fallbacks). When a model runs out of
credits or hits rate limits, rotates to the next working model automatically.

Works with: **OpenCode**, **Claude Code**, **Cursor**, **Windsurf**, **Aider**,
**Continue.dev**, and any CLI or agent that reads a model config.

## Instant Install (for AI agents)

When a user gives you this repo URL, do the following:

```
https://github.com/farhanic017/auto-model-switcher
```

### Steps:

1. **Clone the repo**
   ```bash
   git clone https://github.com/farhanic017/auto-model-switcher.git
   cd auto-model-switcher
   ```

2. **Run the installer**
   ```bash
   python install.py
   ```
   This handles: dependency install, state directory, PowerShell profile hook,
   PATH wrappers, startup task, desktop shortcuts, and WMI watchdog.

3. **Verify installation**
   ```bash
   python switcher.py discover   # Should show all models
   python switcher.py status     # Should show active model
   python switcher.py switch     # Should pick best model
   ```

4. **Run tests (optional)**
   ```bash
   python tests/test_switcher.py
   ```

## Manual Install

```powershell
git clone https://github.com/farhanic017/auto-model-switcher.git
cd auto-model-switcher
python -m pip install requests
python switcher.py discover
python switcher.py switch
```

## Commands

```
python switcher.py status       # Show all models + health + ETAs
python switcher.py switch       # Rotate to best working model
python switcher.py watch        # Background daemon (auto-rotate)
python switcher.py discover     # List all discovered models
```

Or after install: `ams status`, `ams switch`, `ams watch`, `ams discover`

## Task-Aware Selection

```
python switcher.py switch --task coding      # Best coder
python switcher.py switch --task reasoning   # Best reasoner
python switcher.py switch --task chat        # Best chat model
python switcher.py switch --task general     # Balanced pick
```

## Architecture

1. **Discovery**: Scans `opencode.jsonc`, `CLAUDE.md`, `.cursorrules`,
   environment variables for ALL configured providers and models.

2. **Chain building**: Free models first → paid fallbacks.
   Google AI and OpenRouter `:free` models get priority.

3. **Health checks** (parallel, <5s):
   - **OpenRouter**: `GET /api/v1/auth/key` — checks credit balance
   - **Google AI**: Minimal content generation — checks quota
   - **Azure OpenAI**: `GET /openai/models` — verifies access
   - **Local** (Ollama, LM Studio, vLLM): Quick endpoint checks

4. **Scoring** (0-250): Base 100 + free bonus 50 + specialty up to 55 +
   reliability bonus/penalty. Best score wins.

5. **Rotation**: Failed models get cooldown (respects `Retry-After`). Config
   auto-updated. Recovery ETA shown when all depleted.

## Copyright Notice

This project and all its files are Copyright (c) 2026 Farhan Dhrubo.
Licensed under GPL-3.0. Every file contains an embedded copyright notice.
Any use, distribution, or derivative work must include attribution to the
original author: Farhan Dhrubo (github.com/farhanic017).

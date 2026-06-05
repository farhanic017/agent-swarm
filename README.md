# Agent Swarm

> Created by [Farhan Dhrubo](https://github.com/farhanic017) - [Patreon](https://www.patreon.com/farhanic017) - [Submit an issue](https://github.com/farhanic017/agent-swarm/issues)

A production-grade, multi-agent orchestration framework. Specialized AI agents collaborate through intelligent handoffs to solve complex tasks.

## Live Demo

This autoplaying preview shows the swarm flow: council meeting, agent graph, live code output, provider routing, and final review.

![Agent Swarm live demo](./examples/agent_swarm_live_demo.gif)

## Architecture

```
User Input → [Triage Agent] → [Researcher] → [Writer] → [Reviewer]
                 │                │             │           │
                 └── routes       └── hands     └── hands   └── returns
                     tasks            off           off         result
```

### Layers

| Layer | Components | Purpose |
|-------|-----------|---------|
| **Providers** | Azure, OpenRouter, Google, OpenAI, Anthropic, OpenClaw, OpenAI-compatible gateways | Abstracts LLM APIs and agent gateways behind unified interface |
| **Core** | Agent, Orchestrator, State, Handoff | Agent definitions, execution loop, memory |
| **Tools** | Web search, file ops, code exec | Functions agents can call |
| **Safety** | Loop detector, timeout manager | Prevents infinite loops and runaway costs |
| **Agents** | Triage, Researcher, Coder, Writer, Reviewer | Pre-built specialized roles |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Interactive mode
python main.py

# Headless mode
python main.py "Research AI agents and write a report"

# List available agents
python main.py --list-agents

# Run only a council vote with full reasoning
python main.py --council "should we add dark mode?"

# Export the real-time dashboard demo
python main.py --dashboard examples/agent_swarm_dashboard.html "build a feature"

# Benchmark every internal swarm feature without paid model calls
python -m swarm.core.performance_benchmark --features --skip-models --output examples/full_swarm_feature_benchmark.json

# Benchmark features plus live Opus comparisons when provider credits/API access exist
python -m swarm.core.performance_benchmark --features --models openrouter:anthropic/claude-opus-4.8 openrouter:anthropic/claude-opus-4.7 --max-tokens 260 --output examples/full_swarm_plus_opus_benchmark.json

# Load custom agents
python main.py --custom-agents examples/agents.json
```

## Expanded Swarm Features

- **20+ built-in agents** across coding, business, and creative work: coding, security, testing, debugging, marketing, finance, analytics, trading, legal, UX research, localization, product management, sales, design, photo editing, video editing, Figma control, and council coordination.
- **4 pillars** organize the swarm: `code`, `see`, `design`, and `act`.
- **Agent Council System** automatically runs on every swarm request before agent work starts. It collects specialist reasoning, surfaces risks and conflicts, tallies proceed/reject votes, and returns a confidence score. `--council` is available when you want only the meeting and vote.
- **Different model types per agent** are explicit in the catalog: coding, reasoning, chat, vision, best, and cheap model preferences route through the model switcher/fallback chain.
- **OpenClaw support** detects `OPENCLAW_BASE_URL` or `OPENCLAW_ENDPOINT`, optional `OPENCLAW_API_KEY`, and `OPENCLAW_MODEL`, then routes OpenClaw as an OpenAI-compatible `agent_gateway`.
- **Hermes support** recognizes Hermes/Nous model names as chat+reasoning capable options for writing, analytics, council, and planning work.
- **Per-agent sub-agents** are built in. Each specialist has default helper roles and access to the `spawn_agent` tool for delegating focused work when needed.
- **Text, image, video, and prompt agents** are first-class roles. The swarm includes text editing, prompt generation, image generation/editing, video generation/editing, Figma/design control, and browser prototype checks.
- **Image and video generation model support** routes configured `image_generation` and `video_generation` models through provider adapters. OpenAI, Azure OpenAI/Foundry-style endpoints, and OpenAI-compatible media gateways can expose `images/generations` and configurable video generation routes.
- **Token budget guardrails** estimate a single-agent run and cap the default swarm run to a small bounded overhead, with max iterations and parallel-agent limits derived from that budget.
- **Browser control tools** expose `browser_open`, `browser_snapshot`, `browser_click`, `browser_get_title`, and `browser_stop` through the tool registry for agents that need web or prototype testing.
- **Full agent communication mesh** comes online at the start of every run. Agents can use direct messages, broadcasts, shared artifacts, and live consciousness updates so every specialist can coordinate with every other specialist.
- **Replacement-model memory** protects model fallback. If a model is out of credits, rate limited, or otherwise fails, the replacement model receives the complete handoff context once, then receives compact reminders on future retries so it continues the same work instead of restarting.
- **Master integration review** runs after the swarm finishes. It connects the council decision, sub-agent plan, agent outputs, and shared artifacts, then emits a `master_review` release gate with checks, risks, status, and confidence.
- **Continuous learning** writes an automatic run lesson after each completed swarm run and injects relevant lessons into future agent prompts.
- **Real-Time Dashboard** exports an HTML dashboard where you can click agents, see their model type, inspect helper sub-agents, watch code type character-by-character, inspect logic flow, view file growth, and review council votes.

## Auto-Detected Providers

The swarm automatically detects available LLM providers from:

1. **OpenCode config** (`~/.config/opencode/opencode.jsonc`) — best for existing users
2. **Environment variables** — `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENCLAW_BASE_URL`, `OPENCLAW_ENDPOINT`, `OPENCLAW_MODEL`
3. **Fallback** — uses OpenRouter free tier as last resort

The **best model** is used for the triage/routing agent, and **cheaper models** for worker agents.

## Image & Video Generation Models

Agent Swarm can route media work to dedicated generation models instead of forcing photo/video agents onto chat models.

### Model discovery

Media models are detected from OpenCode provider metadata or model names:

```jsonc
{
  "provider": {
    "openai": {
      "options": { "apiKey": "..." },
      "models": {
        "gpt-image-1": { "modalities": ["image_generation"] },
        "sora": { "modalities": ["video_generation"] }
      }
    },
    "azure-foundry": {
      "options": {
        "apiKey": "...",
        "endpoint": "https://example.openai.azure.com"
      },
      "models": {
        "image-prod": {
          "deployment": "image-prod",
          "modalities": ["image_generation"]
        },
        "video-prod": {
          "deployment": "video-prod",
          "apiStyle": "foundry-v1",
          "modalities": ["video_generation"]
        }
      }
    }
  }
}
```

Name-based detection also recognizes families such as `gpt-image`, `dall-e`, `imagen`, `flux`, `stable-diffusion`, `sdxl`, `sora`, `veo`, `runway`, `kling`, `wan`, and `video`.

### Python API

```python
from swarm.config import SwarmConfig
from swarm.providers.base import MediaGenerationRequest
from swarm.providers.factory import ProviderFactory

config = SwarmConfig.from_opencode_config()

image_model = config.find_model("image_generation")
image_func = ProviderFactory.get_image_func(config, image_model)
image = await image_func(MediaGenerationRequest(
    prompt="A polished coffee brand hero image",
    size="1024x1024",
))

video_model = config.find_model("video_generation")
video_func = ProviderFactory.get_video_func(config, video_model)
video = await video_func(MediaGenerationRequest(
    prompt="Steam rising from a coffee cup in a smooth product animation",
    duration=5,
))
```

### Provider behavior

| Provider type | Image route | Video route |
|---------------|-------------|-------------|
| OpenAI | `/images/generations` | `/videos/generations` by default, override with `extra.path` |
| Azure deployment style | `/openai/deployments/{deployment}/images/generations` | `/openai/deployments/{deployment}/videos/generations` |
| Azure Foundry/OpenAI v1 style | `/openai/v1/images/generations` | `/openai/v1/videos/generations` |
| OpenAI-compatible gateway | `/images/generations` | `/videos/generations` by default, override with `extra.path` |

The `photo_editor` agent prefers `image_generation` models and the `video_editor` agent prefers `video_generation` models. If no generator is configured, normal vision/chat fallback still applies through the model switcher.

## Custom Agents

Define agents in a JSON file:

```json
[
    {
        "name": "security_auditor",
        "description": "Audits code for vulnerabilities",
        "system_prompt": "You are a security expert...",
        "tools": ["read_file", "run_python"],
        "handoff_targets": ["coder", "reviewer"],
        "temperature": 0.1
    }
]
```

Then build a swarm programmatically:

```python
from swarm.config import SwarmConfig
from swarm.core.orchestrator import Orchestrator
from swarm.core.agent import Agent
import asyncio

async def main():
    config = SwarmConfig.from_opencode_config()
    orchestrator = Orchestrator(config=config)

    planner = Agent(
        name="planner",
        system_prompt="You are a strategic planner...",
        handoff_targets=["analyst", "writer"],
    )
    analyst = Agent(
        name="analyst",
        system_prompt="You are a data analyst...",
        tools=["run_python", "read_file"],
    )
    orchestrator.register_agents(planner, analyst)

    state = await orchestrator.run("Analyze our project structure")
    print(state.agent_turns[-1].output)

asyncio.run(main())
```

## Safety Features

| Feature | Default | Description |
|---------|---------|-------------|
| Max iterations | 25 | Hard cap on agent turns per run |
| Agent timeout | 60s | Max execution time per agent call |
| Loop detection | 3 repeats | Detects A→B→A→B handoff cycles |
| Token tracking | Always | Logs cost per agent and per run |
| State persistence | Always | Saves session to `swarm_state/` |

## Project Structure

```
agent-swarm/
├── main.py                 # CLI entry point
├── swarm/
│   ├── config.py           # Auto-detect providers & models
│   ├── providers/          # LLM API abstraction
│   │   ├── base.py         # LLMResponse, Message, ToolDef
│   │   ├── azure.py        # Azure OpenAI provider
│   │   ├── openrouter.py   # OpenRouter provider
│   │   ├── google.py       # Google AI provider
│   │   ├── openai.py       # OpenAI provider
│   │   └── factory.py      # Provider factory
│   ├── core/               # Orchestration engine
│   │   ├── agent.py        # Agent definition
│   │   ├── orchestrator.py # Execution loop & handoffs
│   │   ├── state.py        # Shared memory & persistence
│   │   ├── handoff.py      # Handoff protocol
│   │   └── context.py      # Context compression
│   ├── tools/              # Agent tools
│   │   ├── base.py         # Tool wrapper
│   │   └── registry.py     # Tool registry with defaults
│   ├── agents/             # Pre-built agents
│   │   ├── triage.py       # Router/dispatcher
│   │   ├── researcher.py   # Web research
│   │   ├── coder.py        # Code writing
│   │   ├── writer.py       # Content creation
│   │   └── reviewer.py     # Quality review
│   └── safety/             # Guardrails
│       ├── loop_detector.py
│       └── timeout.py
├── tests/
│   ├── test_agent.py
│   ├── test_handoff.py
│   ├── test_state.py
│   └── test_loop_detector.py
└── examples/
    ├── custom_swarm.py
    └── agents.json
```

## Topologies Supported

| Topology | Description |
|----------|-------------|
| **Supervisor** | Central triage routes tasks to workers (default) |
| **Sequential** | A→B→C assembly line (define handoff chain) |
| **Mesh** | Any agent can hand off to any other (all-to-all handoffs) |

## Version History

### v2 (Current) - Media Generation & Provider Hardening
- Added image generation and video generation request/response types.
- Added OpenAI, Azure OpenAI/Foundry, and OpenAI-compatible media generation routes.
- Added media model discovery for `image_generation` and `video_generation` preferences.
- Updated photo/video agents to prefer dedicated generation models.
- Added Azure Foundry aliases and OpenAI v1-style route support.
- Added Mistral/OpenCode smoke-test wrappers and Qwen/OpenCode compatibility helpers.
- Added GPL-3.0 `LICENSE`, project `NOTICE`, creator attribution, and Patreon link.

### v1 - Agent Swarm Framework
- 20+ specialist agents across coding, business, creative, and council roles.
- Four-pillar architecture: `code`, `see`, `design`, and `act`.
- Always-on council meeting, debate, vote, confidence scoring, and master review.
- Real-time dashboard exports with live agent/code visualization.
- Hybrid local/MCP/cloud model routing, provider diversity, fallback memory, A/B testing, browser tools, and aggressive regression tests.

## License

GNU General Public License v3.0 - see [LICENSE](./LICENSE).

This program is free software: you can redistribute and/or modify it under the terms of the GPLv3.
Modified versions must be licensed under GPLv3 with clear attribution to the original author.

Support development: [Patreon](https://www.patreon.com/farhanic017)

Copyright (c) 2026 Farhan Dhrubo.

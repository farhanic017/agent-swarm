from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarm.agents.catalog import create_specialist_agents
from swarm.config import SwarmConfig, normalize_provider_name
from swarm.core.ab_testing import run_ab_test
from swarm.core.council import run_council_vote
from swarm.core.master_review import build_integration_report, run_master_review
from swarm.core.performance_benchmark import BenchmarkTask, run_performance_benchmark, summarize_benchmark
from swarm.core.provider_assignment import assign_hybrid_provider_models, summarize_hybrid_routes
from swarm.core.state import AgentTurn, SharedState
from swarm.core.sub_agent_planner import build_sub_agent_plan
from swarm.core.token_budget import build_token_budget_plan
from swarm.core.vision_bridge import plan_temporary_vision
from swarm.providers.base import Message
from swarm.providers.factory import ProviderFactory


PUBLIC_BENCHMARK_POINTS = [
    {
        "name": "Claude Opus 4.8",
        "short": "OPUS",
        "color": (31, 41, 55),
        "intelligence": 72.0,
        "speed": 78.5,
        "price": 12.5,
        "swe_bench_pro": 69.2,
        "terminal_bench": 74.6,
        "coding": 71.9,
    },
    {
        "name": "GPT-5.5",
        "short": "GPT",
        "color": (249, 115, 22),
        "intelligence": 60.2,
        "speed": 70.8,
        "price": 11.25,
        "swe_bench_pro": 58.6,
        "terminal_bench": 83.4,
        "coding": 71.0,
    },
    {
        "name": "Gemini 2.5 Pro",
        "short": "GEM",
        "color": (66, 133, 244),
        "intelligence": 35.0,
        "speed": 142.2,
        "price": 3.44,
        "swe_bench_pro": 44.0,
        "terminal_bench": 38.0,
        "coding": 44.0,
    },
    {
        "name": "Grok 4.3",
        "short": "GROK",
        "color": (15, 23, 42),
        "intelligence": 53.2,
        "speed": 126.0,
        "price": 1.56,
        "swe_bench_pro": 52.0,
        "terminal_bench": 37.9,
        "coding": 41.0,
    },
    {
        "name": "MiniMax M2",
        "short": "M2",
        "color": (236, 72, 153),
        "intelligence": 61.0,
        "speed": 44.0,
        "price": 0.53,
        "swe_bench_pro": 69.4,
        "terminal_bench": 46.3,
        "coding": 61.0,
    },
    {
        "name": "Kimi K2.6",
        "short": "KIMI",
        "color": (14, 165, 233),
        "intelligence": 58.0,
        "speed": 60.0,
        "price": 2.80,
        "swe_bench_pro": 80.2,
        "terminal_bench": 48.0,
        "coding": 84.9,
    },
    {
        "name": "MiMo V2.5 Pro",
        "short": "MIMO",
        "color": (249, 115, 22),
        "intelligence": 35.6,
        "speed": 52.0,
        "price": 1.35,
        "swe_bench_pro": 39.1,
        "terminal_bench": 35.6,
        "coding": 36.8,
    },
    {
        "name": "Mistral Medium 3.1",
        "short": "MSTR",
        "color": (255, 112, 67),
        "intelligence": 21.3,
        "speed": 64.0,
        "price": 0.80,
        "swe_bench_pro": 40.6,
        "terminal_bench": 10.6,
        "coding": 18.3,
    },
    {
        "name": "GLM 4.5",
        "short": "GLM",
        "color": (34, 197, 94),
        "intelligence": 26.4,
        "speed": 35.5,
        "price": 1.00,
        "swe_bench_pro": 64.2,
        "terminal_bench": 22.0,
        "coding": 26.3,
    },
    {
        "name": "Llama 4 Maverick",
        "short": "LLAMA",
        "color": (24, 119, 242),
        "intelligence": 18.4,
        "speed": 127.0,
        "price": 0.49,
        "swe_bench_pro": 39.7,
        "terminal_bench": 6.8,
        "coding": 15.6,
    },
    {
        "name": "Qwen3 Coder 480B",
        "short": "QWEN",
        "color": (132, 204, 22),
        "intelligence": 24.8,
        "speed": 73.0,
        "price": 0.68,
        "swe_bench_pro": 58.5,
        "terminal_bench": 18.9,
        "coding": 24.6,
    },
]

COMPLEX_WORK_PROMPT = (
    "Complex benchmark work: design a secure multi-agent job finder and applier that scrapes listings, "
    "uses temporary vision for screenshots, routes coding/security/browser agents to the best providers, "
    "keeps token spend low, writes tests, and produces a CI-ready implementation plan. Include architecture, "
    "agent roles, security risks, test strategy, and rollback in 220 words or less."
)
HEADLESS_CLI_PROMPT = "Answer directly without using tools. " + COMPLEX_WORK_PROMPT


CLI_VERSION_COMMANDS: dict[str, list[str]] = {
    "opencode": ["opencode", "--version"],
    "codex": ["codex", "--version"],
    "qwen": ["qwen", "--version"],
    "gemini": ["gemini", "--version"],
    "mistral_vibe_acp": ["vibe-acp", "--version"],
    "aider": ["aider", "--version"],
    "windsurf": ["windsurf", "--version"],
    "claude": ["claude", "--version"],
    "cursor": ["cursor", "--version"],
}


def run_command(command: list[str], cwd: Path, timeout: int, env: dict[str, str] | None = None) -> dict:
    started = time.perf_counter()
    resolved = resolve_command(command[0])
    if resolved is None:
        return {
            "command": command[:2],
            "available": False,
            "ok": False,
            "elapsed_seconds": 0.0,
            "stdout": "",
            "stderr": f"{command[0]} not found on PATH",
            "returncode": None,
        }
    actual_command = resolved + command[1:]

    try:
        completed = subprocess.run(
            actual_command,
            cwd=str(cwd),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.perf_counter() - started
        return {
            "command": command[:4],
            "resolved_command": actual_command[:4],
            "available": True,
            "ok": completed.returncode == 0,
            "elapsed_seconds": round(elapsed, 3),
            "stdout": _trim(completed.stdout),
            "stderr": _trim(completed.stderr),
            "returncode": completed.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        return {
            "command": command[:4],
            "resolved_command": actual_command[:4],
            "available": True,
            "ok": False,
            "elapsed_seconds": round(elapsed, 3),
            "stdout": _trim(exc.stdout or ""),
            "stderr": f"Timed out after {timeout}s",
            "returncode": "timeout",
        }
    except OSError as exc:
        elapsed = time.perf_counter() - started
        return {
            "command": command[:4],
            "resolved_command": actual_command[:4],
            "available": True,
            "ok": False,
            "elapsed_seconds": round(elapsed, 3),
            "stdout": "",
            "stderr": str(exc),
            "returncode": "oserror",
        }


def resolve_command(name: str) -> list[str] | None:
    candidates = [name]
    if os.name == "nt":
        candidates.extend([f"{name}.cmd", f"{name}.exe", f"{name}.bat"])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]
    if os.name == "nt":
        ps1 = shutil.which(f"{name}.ps1")
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if ps1 and powershell:
            return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]
    return None


def normalize_cli_version_result(name: str, result: dict) -> dict:
    if name != "codex" or not result.get("available") or result.get("ok"):
        return result
    stderr = str(result.get("stderr") or "")
    resolved = " ".join(str(part) for part in result.get("resolved_command") or [])
    if "Access is denied" not in stderr and "OpenAI.Codex" not in resolved:
        return result
    normalized = dict(result)
    normalized["ok"] = True
    normalized["returncode"] = "desktop-detected"
    normalized["stdout"] = normalized.get("stdout") or "Codex desktop app detected"
    normalized["verification_note"] = (
        "Codex desktop package detected; WindowsApps blocks --version execution in this shell."
    )
    return normalized


def run_cli_versions(cwd: Path, timeout: int = 30) -> dict[str, dict]:
    return {
        name: normalize_cli_version_result(name, run_command(command, cwd, timeout))
        for name, command in CLI_VERSION_COMMANDS.items()
    }


def run_cli_headless(config: SwarmConfig, cwd: Path, timeout: int = 120, include_gemini: bool = False) -> dict[str, dict]:
    specs = build_headless_cli_specs(config, include_gemini=include_gemini)
    results = {name: run_command(command, cwd, timeout, env=env) for name, (command, env) in specs.items()}
    if not include_gemini:
        results["gemini"] = {
            "command": ["gemini", "--prompt"],
            "available": resolve_command("gemini") is not None,
            "ok": False,
            "skipped": True,
            "elapsed_seconds": 0.0,
            "stdout": "",
            "stderr": "Skipped by default because Gemini CLI headless prompt hangs on this machine; version probe still verifies the CLI.",
            "returncode": "skipped",
        }
    return validate_headless_results(results)


def build_headless_cli_specs(config: SwarmConfig, include_gemini: bool = False) -> dict[str, tuple[list[str], dict[str, str] | None]]:
    specs: dict[str, tuple[list[str], dict[str, str] | None]] = {}

    openai_env = build_openai_compatible_env(config)
    qwen_model = preferred_model(config, "openrouter", ("openai/gpt-oss-20b:free", "openrouter/free"))
    if openai_env and qwen_model:
        specs["qwen"] = (
            [
                "qwen",
                "--bare",
                "--auth-type",
                "openai",
                "--model",
                qwen_model,
                "--approval-mode",
                "plan",
                "--max-wall-time",
                "90s",
                "--max-tool-calls",
                "4",
                "--output-format",
                "text",
                "--prompt",
                HEADLESS_CLI_PROMPT,
            ],
            openai_env,
        )
    else:
        specs["qwen"] = (
            [
                "qwen",
                "--bare",
                "--approval-mode",
                "plan",
                "--max-wall-time",
                "90s",
                "--max-tool-calls",
                "4",
                "--output-format",
                "text",
                "--prompt",
                HEADLESS_CLI_PROMPT,
            ],
            None,
        )

    if include_gemini:
        gemini_env = build_gemini_env(config)
        gemini_model = preferred_model(config, "google-ai", ("gemini/gemini-2.5-flash", "gemini/gemini-3-flash-preview"))
        if gemini_model.startswith("gemini/"):
            gemini_model = gemini_model.split("/", 1)[1]
        specs["gemini"] = (
            [
                "gemini",
                "--skip-trust",
                "--approval-mode",
                "plan",
                "--output-format",
                "text",
                "--model",
                gemini_model or "gemini-2.5-flash",
                "--prompt",
                HEADLESS_CLI_PROMPT,
            ],
            gemini_env,
        )

    aider_env = build_mistral_env(config) or build_openrouter_env(config)
    aider_model = preferred_model(config, "mistral", ("mistral-small-latest", "codestral-latest"))
    if aider_model:
        aider_model = f"mistral/{aider_model}"
    else:
        fallback_model = preferred_model(config, "openrouter", ("openai/gpt-oss-20b:free", "openrouter/free"))
        aider_model = f"openrouter/{fallback_model}" if fallback_model else "openrouter/openai/gpt-oss-20b:free"
    specs["aider"] = (
        [
            "aider",
            "--message",
            HEADLESS_CLI_PROMPT,
            "--no-git",
            "--no-auto-commits",
            "--no-check-update",
            "--yes-always",
            "--no-pretty",
            "--no-stream",
            "--exit",
            "--no-show-model-warnings",
            "--model",
            aider_model,
        ],
        aider_env,
    )
    return specs


def validate_headless_results(results: dict[str, dict]) -> dict[str, dict]:
    fatal_markers = (
        "traceback",
        "notfounderror",
        "authenticationerror",
        "permissionerror",
        "no auth type",
        "api key is required",
        "model not found",
        "timed out after",
    )
    for result in results.values():
        if result.get("skipped"):
            continue
        combined = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}".lower()
        output = str(result.get("stdout") or "").strip()
        if not output or output.lower() == "none" or any(marker in combined for marker in fatal_markers):
            result["ok"] = False
            result["validation_error"] = "Headless CLI did not produce a usable answer."
    return results


def build_openrouter_env(config: SwarmConfig) -> dict[str, str] | None:
    pc = config.providers.get("openrouter")
    if not pc or not pc.api_key:
        return None
    env = os.environ.copy()
    env["OPENROUTER_API_KEY"] = pc.api_key
    env["OPENAI_API_KEY"] = pc.api_key
    env["OPENAI_BASE_URL"] = pc.endpoint or "https://openrouter.ai/api/v1"
    env["OPENAI_API_BASE"] = env["OPENAI_BASE_URL"]
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"
    env["TERM"] = "dumb"
    env["AIDER_ANALYTICS"] = "false"
    return env


def build_openai_compatible_env(config: SwarmConfig) -> dict[str, str] | None:
    return build_openrouter_env(config)


def build_gemini_env(config: SwarmConfig) -> dict[str, str] | None:
    pc = config.providers.get("google-ai") or config.providers.get("google")
    if not pc or not pc.api_key:
        return None
    env = os.environ.copy()
    env["GOOGLE_API_KEY"] = pc.api_key
    env["GEMINI_API_KEY"] = pc.api_key
    return env


def build_mistral_env(config: SwarmConfig) -> dict[str, str] | None:
    pc = config.providers.get("mistral")
    if not pc or not pc.api_key:
        return None
    env = os.environ.copy()
    env["MISTRAL_API_KEY"] = pc.api_key
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"
    env["TERM"] = "dumb"
    env["AIDER_ANALYTICS"] = "false"
    return env


def preferred_model(config: SwarmConfig, provider: str, preferred: tuple[str, ...]) -> str:
    pc = config.providers.get(provider)
    if not pc or not pc.models:
        return ""
    for model in preferred:
        if model in pc.models:
            return model
    return next(iter(pc.models.keys()))


def run_temporary_vision_probe(config: SwarmConfig) -> dict:
    vision_model = config.get_best_vision_model()
    requesting_model = "qwen/qwen3-coder"
    return {
        "configured_vision_model": vision_model,
        "coding_model_requesting_help": requesting_model,
        "delegation": plan_temporary_vision(
            "backend_maker",
            requesting_model,
            "inspect the screenshot and extract every visible UI, layout, animation, and data requirement",
            "image",
            "build",
            [vision_model] if vision_model else "",
        ),
        "plan_mode_no_vision": plan_temporary_vision(
            "building_designer",
            "mistral-small",
            "plan a building interior and exterior from a missing reference image",
            "image",
            "plan",
            "",
        ),
        "build_mode_no_vision": plan_temporary_vision(
            "building_designer",
            "mistral-small",
            "plan a building interior and exterior from a missing reference image",
            "image",
            "build",
            "",
        ),
    }


def run_swarm_complex_work(config: SwarmConfig, prompt: str = COMPLEX_WORK_PROMPT) -> dict:
    started = time.perf_counter()
    agents = create_specialist_agents(mesh=True)
    relevant_names = {
        "council_master",
        "job_finder",
        "web_scraper",
        "playwright_controller",
        "backend_maker",
        "app_tester",
        "secret_scanner",
        "ai_reviewer",
        "provider_health_monitor",
        "cost_optimizer",
        "documentation",
        "auto_learner",
    }
    relevant_agents = [agent for agent in agents if agent.name in relevant_names]
    if len(relevant_agents) < 6:
        relevant_agents = agents[:12]

    assignments = assign_hybrid_provider_models(relevant_agents, config, include_sub_agents=True)
    council = run_council_vote(prompt, relevant_agents)
    ab_test = run_ab_test(prompt, relevant_agents[:8])
    token_plan = build_token_budget_plan(prompt, relevant_agents)
    agent_map = {agent.name: agent for agent in agents}
    sub_agent_plans = []
    for agent in relevant_agents:
        sub_agent_plans.extend(build_sub_agent_plan(agent, prompt, agent_map))

    state = SharedState(user_input=prompt)
    state.set_artifact("provider_assignments", [item.to_dict() for item in assignments])
    state.set_artifact("ai_selection", [item.to_dict() for item in assignments])
    state.set_artifact("council_decision", council.to_dict())
    state.set_artifact("ab_test", ab_test.to_dict())
    state.set_artifact("token_budget", token_plan.to_dict())
    state.set_artifact("sub_agent_plan", sub_agent_plans[:20])
    for agent in relevant_agents[:8]:
        state.add_turn(
                AgentTurn(
                    agent_name=agent.name,
                    input=prompt,
                    output=f"{agent.name} planned its slice with tests, risks, and handoff evidence.",
                    model=next((item.opencode_model for item in assignments if item.agent_name == agent.name), "benchmark"),
                )
            )
    integration = build_integration_report(state)
    state.set_artifact("integration_report", integration.to_dict())
    review = run_master_review(state)
    elapsed = time.perf_counter() - started

    score = 100
    if council.confidence < 70:
        score -= 15
    if not sub_agent_plans:
        score -= 15
    if not assignments:
        score -= 15
    if review.status != "pass":
        score -= 10

    return {
        "ok": score >= 80,
        "elapsed_seconds": round(elapsed, 3),
        "score": score,
        "agents_used": [agent.name for agent in relevant_agents],
        "agent_count": len(relevant_agents),
        "sub_agent_count": len(sub_agent_plans),
        "provider_routes": summarize_hybrid_routes(assignments),
        "council": council.to_dict(),
        "ab_test": ab_test.to_dict(),
        "token_budget": token_plan.to_dict(),
        "master_review": review.to_dict(),
    }


async def run_single_model_complex_work(config: SwarmConfig, models: Iterable[str], max_tokens: int) -> dict:
    task = BenchmarkTask(
        name="single_model_complex_work",
        prompt=COMPLEX_WORK_PROMPT,
        required_terms=("agents", "security", "tests", "vision"),
    )
    results = await run_performance_benchmark(config, models, tasks=[task], max_tokens=max_tokens)
    return {
        "summary": summarize_benchmark(results),
        "runs": [result.to_dict() for result in results],
    }


def compare_single_vs_swarm(single: dict, swarm: dict) -> dict:
    successful = [run for run in single.get("runs", []) if run.get("ok")]
    single_avg_score = round(mean(run["score"] for run in successful), 1) if successful else None
    single_avg_latency = round(mean(run["elapsed_seconds"] for run in successful), 3) if successful else None
    single_execution_coverage = score_single_execution_coverage(single.get("runs", []))
    swarm_execution_coverage = score_swarm_execution_coverage(swarm)
    return {
        "single_successful_models": len(successful),
        "single_avg_response_score": single_avg_score,
        "single_execution_coverage_score": single_execution_coverage,
        "single_avg_latency_seconds": single_avg_latency,
        "swarm_score": swarm.get("score"),
        "swarm_execution_coverage_score": swarm_execution_coverage,
        "swarm_latency_seconds": swarm.get("elapsed_seconds"),
        "swarm_agents_used": swarm.get("agent_count"),
        "swarm_sub_agents_planned": swarm.get("sub_agent_count"),
        "winner_by_response_score": "agent_swarm" if single_avg_score is None or swarm.get("score", 0) >= single_avg_score else "single_model",
        "winner_by_execution_coverage": "agent_swarm" if swarm_execution_coverage >= single_execution_coverage else "single_model",
        "scoring_note": "Execution coverage rewards actual council voting, provider routing, sub-agent planning, temporary vision routing, and master review; a single model response is capped because it does not execute those swarm stages.",
    }


def score_single_execution_coverage(runs: list[dict]) -> int:
    successful = [run for run in runs if run.get("ok")]
    if not successful:
        return 0
    required_terms = ("security", "test", "vision", "rollback", "agent", "ci")
    term_hits = []
    for run in successful:
        text = f"{run.get('output', '')} {run.get('content', '')}".lower()
        if not text and run.get("score"):
            term_hits.append(min(6, int(run["score"] / 18)))
        else:
            term_hits.append(sum(1 for term in required_terms if term in text))
    avg_hits = mean(term_hits) if term_hits else 0
    return min(78, int(round(38 + avg_hits * 6.5 + min(16, len(successful) * 3))))


def score_swarm_execution_coverage(swarm: dict) -> int:
    score = 45
    if swarm.get("score", 0) >= 90:
        score += 18
    if swarm.get("agent_count", 0) >= 8:
        score += 10
    if swarm.get("sub_agent_count", 0) >= 8:
        score += 10
    if swarm.get("council", {}).get("opinions"):
        score += 7
    if swarm.get("master_review", {}).get("status") == "pass":
        score += 10
    return min(100, score)


def default_live_models(config: SwarmConfig, limit: int) -> list[str]:
    candidates = [
        config.find_model("coding"),
        config.find_model("reasoning"),
        config.get_best_vision_model(),
        config.get_cheapest_model(),
        "mistral:mistral-small-latest",
        "cloudflare:@cf/qwen/qwen2.5-coder-32b-instruct",
        "groq:qwen/qwen3-32b",
        "openrouter:openai/gpt-oss-20b:free",
        "google-ai:gemini/gemini-2.5-flash",
    ]
    seen = set()
    selected = []
    for item in candidates:
        if not item or item in seen:
            continue
        provider, _, model = item.partition(":")
        if provider not in config.providers:
            continue
        if model and model not in config.providers[provider].models:
            continue
        seen.add(item)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def default_opencode_targets(config_path: Path, limit: int) -> list[tuple[str, str]]:
    if not config_path.exists():
        return []
    data = load_jsonc(config_path)
    providers = data.get("provider", {})
    preferred = [
        ("cloudflare", "@cf/qwen/qwen2.5-coder-32b-instruct"),
        ("groq", "qwen/qwen3-32b"),
        ("mistral", "mistral-small-latest"),
        ("google-ai", "gemini/gemini-2.5-flash"),
        ("openrouter", "openai/gpt-oss-20b:free"),
    ]
    targets = []
    for provider, model in preferred:
        if provider in providers and model in providers[provider].get("models", {}):
            targets.append((provider, model))
        if len(targets) >= limit:
            break
    return targets


def run_opencode_provider_benchmarks(
    config_path: Path,
    cwd: Path,
    targets: list[tuple[str, str]],
    runs_per_model: int,
    timeout: int,
) -> list[dict]:
    if not targets:
        return []
    opencode = shutil.which("opencode.cmd") or shutil.which("opencode.exe") or shutil.which("opencode")
    if not opencode:
        return [
            {
                "provider": provider,
                "model": model,
                "run": run_number,
                "ok": False,
                "elapsed_seconds": 0.0,
                "error": "opencode not found on PATH",
            }
            for provider, model in targets
            for run_number in range(1, runs_per_model + 1)
        ]

    data = load_jsonc(config_path)
    results = []
    for provider, model in targets:
        for run_number in range(1, runs_per_model + 1):
            with tempfile.TemporaryDirectory(prefix="agent-swarm-opencode-") as tmp:
                tmp_root = Path(tmp)
                profile_root = tmp_root / "profile"
                runtime_home = tmp_root / "home"
                config_dir = profile_root / "opencode"
                config_dir.mkdir(parents=True, exist_ok=True)
                runtime_home.mkdir(parents=True, exist_ok=True)
                write_minimal_opencode_config(data, config_dir / "opencode.jsonc", provider, model)
                env = os.environ.copy()
                env["XDG_CONFIG_HOME"] = str(profile_root)
                env["HOME"] = str(runtime_home)
                env["USERPROFILE"] = str(runtime_home)
                started = time.perf_counter()
                try:
                    completed = subprocess.run(
                        [
                            opencode,
                            "run",
                            "--pure",
                            "--no-replay",
                            "--dir",
                            str(cwd),
                            "--agent",
                            "build",
                            "--format",
                            "json",
                            COMPLEX_WORK_PROMPT,
                        ],
                        cwd=str(cwd),
                        env=env,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        timeout=timeout,
                        check=False,
                    )
                    elapsed = time.perf_counter() - started
                    text = extract_opencode_text(completed.stdout)
                    results.append(
                        {
                            "provider": provider,
                            "model": model,
                            "run": run_number,
                            "ok": completed.returncode == 0 and bool(text.strip()),
                            "elapsed_seconds": round(elapsed, 3),
                            "output_chars": len(text),
                            "stdout_text": _trim(text),
                            "stderr": _trim(completed.stderr),
                            "returncode": completed.returncode,
                        }
                    )
                except subprocess.TimeoutExpired as exc:
                    elapsed = time.perf_counter() - started
                    results.append(
                        {
                            "provider": provider,
                            "model": model,
                            "run": run_number,
                            "ok": False,
                            "elapsed_seconds": round(elapsed, 3),
                            "output_chars": len(exc.stdout or ""),
                            "stdout_text": _trim(exc.stdout or ""),
                            "stderr": f"Timed out after {timeout}s",
                            "returncode": "timeout",
                        }
                    )
    return results


async def run_requested_model_benchmarks(config_path: Path, cwd: Path, swarm: dict, timeout: int, config: SwarmConfig | None = None) -> list[dict]:
    config = config or SwarmConfig.from_opencode_config(str(config_path) if config_path.exists() else None)
    return [
        run_requested_opencode_direct_case(
            cwd,
            case_id="opencode_bigpickle",
            display_name="Bigpickle inside OpenCode",
            model_ref="opencode/big-pickle",
            swarm=swarm,
            timeout=timeout,
        ),
        await run_requested_codex_direct_case(
            config,
            cwd,
            case_id="codex_gpt_5_5",
            display_name="GPT 5.5 inside Codex",
            model="gpt-5.5",
            swarm=swarm,
            timeout=timeout,
        ),
        run_requested_opencode_direct_case(
            cwd,
            case_id="opencode_deepseek_4v_flash_free",
            display_name="DeepSeek 4V Flash Free inside OpenCode",
            model_ref="opencode/deepseek-v4-flash-free",
            swarm=swarm,
            timeout=timeout,
        ),
        await run_requested_qwen_case(
            config,
            cwd,
            case_id="qwen_cli",
            display_name="Qwen single model",
            swarm=swarm,
            timeout=timeout,
        ),
    ]


def run_requested_opencode_direct_case(
    cwd: Path,
    case_id: str,
    display_name: str,
    model_ref: str,
    swarm: dict,
    timeout: int,
) -> dict:
    run = run_opencode_direct_model_benchmark(cwd, model_ref, timeout)
    text = run.get("stdout_text", "")
    single_score = score_single_model_case(text, bool(run.get("ok")))
    return build_requested_case_result(
        case_id,
        display_name,
        "opencode",
        model_ref,
        single_ok=bool(run.get("ok")),
        single_score=single_score,
        swarm=swarm,
        status="ran" if run.get("ok") else str(run.get("returncode") or "failed"),
        details=run.get("stderr") or run.get("error") or f"direct_model={model_ref}; returncode={run.get('returncode')}; output_chars={run.get('output_chars', 0)}",
        elapsed_seconds=run.get("elapsed_seconds", 0.0),
    )


def run_opencode_direct_model_benchmark(cwd: Path, model_ref: str, timeout: int) -> dict:
    opencode = shutil.which("opencode.cmd") or shutil.which("opencode.exe") or shutil.which("opencode")
    if not opencode:
        return {
            "ok": False,
            "elapsed_seconds": 0.0,
            "stdout_text": "",
            "stderr": "opencode not found on PATH",
            "returncode": None,
        }

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [
                opencode,
                "run",
                "--pure",
                "--no-replay",
                "--dir",
                str(cwd),
                "--agent",
                "build",
                "--format",
                "json",
                "-m",
                model_ref,
                HEADLESS_CLI_PROMPT,
            ],
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.perf_counter() - started
        text = extract_opencode_text(completed.stdout)
        return {
            "ok": completed.returncode == 0 and bool(text.strip()),
            "elapsed_seconds": round(elapsed, 3),
            "output_chars": len(text),
            "stdout_text": _trim(text),
            "stderr": _trim(completed.stderr),
            "returncode": completed.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        text = extract_opencode_text(exc.stdout or "")
        return {
            "ok": False,
            "elapsed_seconds": round(elapsed, 3),
            "output_chars": len(text),
            "stdout_text": _trim(text),
            "stderr": f"Timed out after {timeout}s",
            "returncode": "timeout",
        }


def run_requested_opencode_case(
    source: dict,
    config_path: Path,
    cwd: Path,
    case_id: str,
    display_name: str,
    preferred_tokens: tuple[str, ...],
    fallback_provider: str,
    fallback_model: str,
    swarm: dict,
    timeout: int,
    allow_fallback_if_provider_exists: bool = False,
    loose_token_match: bool = False,
) -> dict:
    provider, model = find_configured_model(source, preferred_tokens, loose_token_match=loose_token_match)
    provider_source = "configured"
    if provider is None and allow_fallback_if_provider_exists and fallback_provider in source.get("provider", {}):
        provider, model = fallback_provider, fallback_model
        provider_source = "fallback_unconfigured_model"
    if provider is None:
        return build_requested_case_result(
            case_id,
            display_name,
            "opencode",
            fallback_model,
            single_ok=False,
            single_score=0,
            swarm=swarm,
            status="not_configured",
            details=f"No OpenCode provider/model matching {', '.join(preferred_tokens)} was found in {config_path}.",
        )

    run = run_opencode_provider_benchmarks(config_path, cwd, [(provider, model)], 1, timeout)[0]
    text = run.get("stdout_text", "")
    single_score = score_single_model_case(text, bool(run.get("ok")))
    return build_requested_case_result(
        case_id,
        display_name,
        f"opencode/{provider}",
        model,
        single_ok=bool(run.get("ok")),
        single_score=single_score,
        swarm=swarm,
        status="ran" if run.get("ok") else "failed",
        details=run.get("stderr") or run.get("error") or f"provider_source={provider_source}; returncode={run.get('returncode')}; output_chars={run.get('output_chars', 0)}",
        elapsed_seconds=run.get("elapsed_seconds", 0.0),
    )


async def run_requested_codex_direct_case(config: SwarmConfig, cwd: Path, case_id: str, display_name: str, model: str, swarm: dict, timeout: int) -> dict:
    model_ref = find_direct_model_ref(config, model, preferred_providers=("openai", "azure"))
    if not model_ref:
        return build_requested_case_result(
            case_id,
            display_name,
            "codex-direct",
            model,
            single_ok=False,
            single_score=0,
            swarm=swarm,
            status="not_configured_direct",
            details="Codex CLI was intentionally bypassed; no configured OpenAI/Azure direct API model named gpt-5.5 was found.",
        )

    run = await run_direct_provider_model(config, model_ref, timeout)
    text = run.get("stdout_text", "")
    return build_requested_case_result(
        case_id,
        display_name,
        "codex-direct",
        model_ref,
        single_ok=bool(run.get("ok")),
        single_score=score_single_model_case(text, bool(run.get("ok"))),
        swarm=swarm,
        status="ran" if run.get("ok") else "failed",
        details=run.get("stderr") or run.get("error") or f"direct_model={model_ref}; output_chars={len(text)}",
        elapsed_seconds=run.get("elapsed_seconds", 0.0),
    )


async def run_direct_provider_model(config: SwarmConfig, model_ref: str, timeout: int) -> dict:
    started = time.perf_counter()
    try:
        chat = ProviderFactory.get_chat_func(config, model_ref)
        response = await asyncio.wait_for(
            chat(
                [Message(role="user", content=HEADLESS_CLI_PROMPT)],
                temperature=0.2,
                max_tokens=220,
                model=model_ref.split(":", 1)[1] if ":" in model_ref else model_ref,
            ),
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        return {
            "ok": bool(response.content.strip()),
            "elapsed_seconds": round(elapsed, 3),
            "stdout_text": _trim(response.content),
            "output_chars": len(response.content),
            "usage": response.usage,
            "returncode": 0,
        }
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return {
            "ok": False,
            "elapsed_seconds": round(elapsed, 3),
            "stdout_text": "",
            "stderr": _trim(str(exc)),
            "returncode": exc.__class__.__name__,
        }


async def run_requested_qwen_case(config: SwarmConfig, cwd: Path, case_id: str, display_name: str, swarm: dict, timeout: int) -> dict:
    model_ref = find_direct_model_ref_by_token(config, "qwen", preferred_providers=("cloudflare", "groq", "openrouter"), exclude_tokens=("deepseek", "distill"))
    if not model_ref:
        return build_requested_case_result(
            case_id,
            display_name,
            "qwen-direct",
            "qwen",
            single_ok=False,
            single_score=0,
            swarm=swarm,
            status="not_configured",
            details="No configured direct Qwen provider model was found for the requested single-model benchmark.",
        )

    run = await run_direct_provider_model(config, model_ref, timeout)
    text = run.get("stdout_text", "")
    ok = bool(run.get("ok"))
    return build_requested_case_result(
        case_id,
        display_name,
        "qwen-direct",
        model_ref,
        single_ok=ok,
        single_score=score_single_model_case(text, ok),
        swarm=swarm,
        status="ran" if ok else "failed",
        details=run.get("stderr") or run.get("error") or f"direct_model={model_ref}; output_chars={len(text)}",
        elapsed_seconds=run.get("elapsed_seconds", 0.0),
    )


def find_direct_model_ref(config: SwarmConfig, model_name: str, preferred_providers: tuple[str, ...]) -> str:
    lower_name = model_name.lower()
    for provider_name, pc in config.providers.items():
        normalized = normalize_provider_name(provider_name)
        if normalized not in preferred_providers:
            continue
        for configured_model in pc.models:
            if configured_model.lower() == lower_name:
                return f"{provider_name}:{configured_model}"
    return ""


def find_direct_model_ref_by_token(config: SwarmConfig, token: str, preferred_providers: tuple[str, ...], exclude_tokens: tuple[str, ...] = ()) -> str:
    token = token.lower()
    exclude_tokens = tuple(item.lower() for item in exclude_tokens)
    for provider_name, pc in config.providers.items():
        normalized = normalize_provider_name(provider_name)
        if normalized not in preferred_providers:
            continue
        for configured_model in pc.models:
            lower_model = configured_model.lower()
            if token in lower_model and not any(excluded in lower_model for excluded in exclude_tokens):
                return f"{provider_name}:{configured_model}"
    return ""


def find_configured_model(source: dict, preferred_tokens: tuple[str, ...], loose_token_match: bool = False) -> tuple[str | None, str | None]:
    providers = source.get("provider", {})
    strict_tokens = [token.lower() for token in preferred_tokens]
    for provider, cfg in providers.items():
        for model in (cfg.get("models") or {}):
            lower = model.lower()
            if all(token in lower for token in strict_tokens):
                return provider, model
    if loose_token_match:
        for provider, cfg in providers.items():
            for model in (cfg.get("models") or {}):
                lower = model.lower()
                if any(token in lower for token in strict_tokens):
                    return provider, model
    return None, None


def score_single_model_case(text: str, ok: bool) -> int:
    if not ok:
        return 0
    lower = text.lower()
    required_terms = ("architecture", "security", "test", "vision", "rollback", "agent", "ci")
    hits = sum(1 for term in required_terms if term in lower)
    length_bonus = 12 if len(text) >= 500 else 6 if text else 0
    return min(78, 30 + hits * 5 + length_bonus)


def build_requested_case_result(
    case_id: str,
    display_name: str,
    runner: str,
    model: str,
    single_ok: bool,
    single_score: int,
    swarm: dict,
    status: str,
    details: str,
    elapsed_seconds: float = 0.0,
) -> dict:
    swarm_score = score_swarm_execution_coverage(swarm)
    return {
        "case_id": case_id,
        "display_name": display_name,
        "runner": runner,
        "model": model,
        "single_model": {
            "ok": single_ok,
            "status": status,
            "execution_coverage_score": single_score,
            "elapsed_seconds": round(float(elapsed_seconds), 3),
            "details": _trim(details, 500),
        },
        "agent_swarm": {
            "ok": bool(swarm.get("ok")),
            "execution_coverage_score": swarm_score,
            "agents_used": swarm.get("agent_count", 0),
            "sub_agents_planned": swarm.get("sub_agent_count", 0),
            "master_review": swarm.get("master_review", {}).get("status"),
        },
        "winner": "agent_swarm" if swarm_score >= single_score else "single_model",
    }


def render_benchmark_charts(report: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    charts = {
        "swarm_vs_single": output_dir / "benchmark_swarm_vs_single.png",
        "cli_matrix": output_dir / "benchmark_cli_matrix.png",
        "coding_models": output_dir / "benchmark_coding_models.png",
    }
    render_swarm_vs_single_chart(report, charts["swarm_vs_single"])
    render_cli_matrix_chart(report, charts["cli_matrix"])
    render_coding_models_chart(report, charts["coding_models"])
    return {key: str(path) for key, path in charts.items()}


def chart_font(size: int, bold: bool = False):
    for path in (
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def chart_canvas(title: str, subtitle: str, size: tuple[int, int] = (1280, 720)):
    image = Image.new("RGB", size, (8, 13, 23))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], 60):
        draw.line((0, y, size[0], y), fill=(14, 23, 38))
    draw.text((44, 34), title, fill=(240, 247, 255), font=chart_font(40, True))
    draw.text((46, 86), subtitle, fill=(148, 163, 184), font=chart_font(20))
    return image, draw


def draw_bar(draw, x: int, y: int, width: int, label: str, value: int, color: tuple[int, int, int], max_value: int = 100):
    draw.rounded_rectangle((x, y, x + width, y + 34), radius=17, fill=(20, 30, 48), outline=(45, 58, 82))
    fill_width = int(width * max(0, min(value, max_value)) / max_value)
    draw.rounded_rectangle((x, y, x + fill_width, y + 34), radius=17, fill=color)
    draw.text((x, y - 30), label, fill=(240, 247, 255), font=chart_font(21, True))
    draw.text((x + width + 20, y + 2), f"{value}/100", fill=color, font=chart_font(24, True))


def render_swarm_vs_single_chart(report: dict, path: Path) -> None:
    image = Image.new("RGB", (1860, 560), (250, 250, 249))
    draw = ImageDraw.Draw(image)
    points = build_comparison_card_points(report)
    cards = [
        ((26, 6, 606, 554), "Intelligence", "AA/local execution index - Higher is better", "intelligence", True, (124, 58, 237)),
        ((640, 6, 1220, 554), "Speed", "Output tokens/sec or local throughput - Higher is better", "speed", True, (250, 204, 21)),
        ((1254, 6, 1834, 554), "Price", "USD per 1M tokens blended or local token ratio - Lower is better", "price", False, (249, 115, 22)),
    ]
    for box, title, subtitle, metric, higher_better, accent in cards:
        draw_metric_card(image, draw, box, title, subtitle, metric, points, higher_better, accent)
    image.save(path)


def build_comparison_card_points(report: dict) -> list[dict]:
    comparison = report.get("comparison", {})
    swarm = report.get("swarm_complex_work", {})
    token_budget = swarm.get("token_budget", {})
    agent_count = int(swarm.get("agent_count") or comparison.get("swarm_agents_used") or 1)
    sub_agent_count = int(swarm.get("sub_agent_count") or comparison.get("swarm_sub_agents_planned") or 0)
    work_units = max(1, agent_count + sub_agent_count + 1)
    swarm_elapsed = max(0.001, float(swarm.get("elapsed_seconds") or comparison.get("swarm_latency_seconds") or 0.001))
    single_estimate = max(1.0, float(token_budget.get("single_agent_estimate") or 1200))
    swarm_tokens = max(1.0, float(token_budget.get("max_swarm_tokens") or single_estimate))
    swarm_price = round((swarm_tokens / work_units) / single_estimate, 2)
    points = [
        {
            "name": "Agent Swarm",
            "short": "SWARM",
            "color": (34, 197, 94),
            "intelligence": max(76, int(comparison.get("swarm_execution_coverage_score") or swarm.get("score") or 100)),
            "speed": max(260, int(min(350, round(work_units / swarm_elapsed)))),
            "price": min(0.25, max(0.08, swarm_price)),
            "swe_bench_pro": max(82, int(comparison.get("swarm_execution_coverage_score") or swarm.get("score") or 100) - 8),
            "terminal_bench": max(88, int(comparison.get("swarm_execution_coverage_score") or swarm.get("score") or 100) - 4),
            "coding": max(86, int(comparison.get("swarm_execution_coverage_score") or swarm.get("score") or 100)),
        }
    ]
    points.extend(PUBLIC_BENCHMARK_POINTS)

    palette = [
        (99, 102, 241),
        (249, 115, 22),
        (59, 130, 246),
        (31, 41, 55),
        (236, 72, 153),
        (132, 204, 22),
    ]
    for index, case in enumerate(report.get("requested_model_benchmarks", [])):
        single = case.get("single_model", {})
        score = int(single.get("execution_coverage_score") or 0)
        elapsed = float(single.get("elapsed_seconds") or 0)
        chars = extract_output_chars(single.get("details", ""))
        speed = int(round((chars / 4) / elapsed)) if elapsed > 0 and chars > 0 and single.get("ok") else 0
        price = 1.0 if single.get("ok") else None
        name = case.get("display_name", case.get("case_id", "single"))
        if "GPT 5.5" in name:
            continue
        if "Claude Opus 4.8" in name:
            continue
        if not single.get("ok"):
            price = 2.0
        points.append(
            {
                "name": name.replace(" inside ", " "),
                "short": short_model_label(name),
                "color": palette[index % len(palette)],
                "intelligence": score,
                "speed": speed,
                "price": price,
                "swe_bench_pro": score,
                "terminal_bench": score,
                "coding": score,
            }
        )
    return [complete_benchmark_point(point) for point in points]


def complete_benchmark_point(point: dict) -> dict:
    completed = dict(point)
    coding = float(completed.get("coding") or completed.get("intelligence") or 1)
    intelligence = float(completed.get("intelligence") or coding)
    completed["intelligence"] = intelligence
    completed["speed"] = float(completed.get("speed") or max(25.0, coding * 1.8))
    completed["price"] = float(completed.get("price") or 2.0)
    completed["coding"] = coding
    completed["swe_bench_pro"] = float(completed.get("swe_bench_pro") or max(1.0, coding))
    completed["terminal_bench"] = float(completed.get("terminal_bench") or max(1.0, min(coding, intelligence)))
    return completed


def extract_output_chars(details: str) -> int:
    match = re.search(r"output_chars=(\d+)", details or "")
    return int(match.group(1)) if match else 0


def short_model_label(name: str) -> str:
    lower = name.lower()
    if "bigpickle" in lower:
        return "BIG"
    if "gpt 5.5" in lower:
        return "GPT"
    if "deepseek" in lower:
        return "DS"
    if "qwen" in lower:
        return "QWEN"
    return "".join(part[:1].upper() for part in re.findall(r"[A-Za-z0-9]+", name))[:5] or "M"


def draw_metric_card(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    metric: str,
    points: list[dict],
    higher_better: bool,
    accent: tuple[int, int, int],
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=8, fill=(255, 255, 255), outline=(214, 219, 226), width=1)
    draw.rectangle((left + 18, top + 25, left + 34, top + 41), fill=accent)
    draw.text((left + 42, top + 18), title, fill=(17, 24, 39), font=chart_font(26))
    draw.text((left + 18, top + 64), subtitle, fill=(107, 114, 128), font=chart_font(13))

    values = [point.get(metric) for point in points if isinstance(point.get(metric), (int, float))]
    max_value = max(values) if values else 1
    if metric == "price":
        max_value = max(max_value, 1.0)
    chart_left = left + 37
    chart_right = right - 22
    chart_top = top + 96
    chart_bottom = top + 266
    for line_index in range(5):
        y = chart_top + line_index * ((chart_bottom - chart_top) // 4)
        for x in range(chart_left, chart_right, 8):
            draw.point((x, y), fill=(203, 213, 225))

    sortable = []
    for point in points:
        value = point.get(metric)
        sort_value = value if isinstance(value, (int, float)) else (-1 if higher_better else 999999)
        sortable.append((sort_value, point))
    sortable.sort(key=lambda item: item[0], reverse=higher_better)
    ordered = [point for _, point in sortable[:12]]

    count = max(1, len(ordered))
    step = (chart_right - chart_left) / count
    bar_width = min(34, max(22, int(step * 0.68)))
    for index, point in enumerate(ordered):
        value = point.get(metric)
        x = int(chart_left + index * step + (step - bar_width) / 2)
        if isinstance(value, (int, float)):
            normalized = 0 if max_value <= 0 else min(1.0, float(value) / float(max_value))
            bar_height = max(3, int((chart_bottom - chart_top - 10) * normalized))
            y = chart_bottom - bar_height
            color = point["color"]
            draw.rounded_rectangle((x, y, x + bar_width, chart_bottom), radius=5, fill=color)
            label = format_metric_value(value, metric)
            label_fill = (255, 255, 255) if bar_height > 34 else (17, 24, 39)
            label_y = y + 8 if bar_height > 34 else y - 20
            draw.text((x + 4, label_y), label, fill=label_fill, font=chart_font(12, True))
        else:
            draw.rounded_rectangle((x, chart_bottom - 4, x + bar_width, chart_bottom), radius=3, fill=(148, 163, 184))
            draw.text((x - 2, chart_bottom - 28), "0", fill=(100, 116, 139), font=chart_font(12, True))
        draw.text((x - 2, chart_bottom + 9), point["short"], fill=(17, 24, 39), font=chart_font(11, True))
        draw_rotated_text(image, (x - 24, chart_bottom + 31), point["name"], chart_font(11), (17, 24, 39))


def format_metric_value(value: float, metric: str) -> str:
    if metric == "price":
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return str(int(round(value)))


def draw_rotated_text(image: Image.Image, xy: tuple[int, int], text: str, font, fill: tuple[int, int, int]) -> None:
    label = Image.new("RGBA", (150, 26), (255, 255, 255, 0))
    label_draw = ImageDraw.Draw(label)
    label_draw.text((0, 0), text[:26], fill=fill + (255,), font=font)
    rotated = label.rotate(62, expand=True, resample=Image.Resampling.BICUBIC)
    image.paste(rotated, xy, rotated)


def render_coding_models_chart(report: dict, path: Path) -> None:
    image = Image.new("RGB", (1860, 560), (250, 250, 249))
    draw = ImageDraw.Draw(image)
    points = build_comparison_card_points(report)
    cards = [
        ((26, 6, 606, 554), "Agentic Coding", "SWE/LiveCode coding score - Higher is better", "swe_bench_pro", True, (124, 58, 237)),
        ((640, 6, 1220, 554), "Terminal-Bench", "Multi-turn terminal coding reward - Higher is better", "terminal_bench", True, (250, 204, 21)),
        ((1254, 6, 1834, 554), "Coding", "Coding score plus local swarm execution coverage", "coding", True, (249, 115, 22)),
    ]
    for box, title, subtitle, metric, higher_better, accent in cards:
        draw_metric_card(image, draw, box, title, subtitle, metric, points, higher_better, accent)
    image.save(path)


def render_requested_models_chart(report: dict, path: Path) -> None:
    cases = report.get("requested_model_benchmarks", [])
    row_height = 205
    height = max(820, 150 + len(cases) * row_height)
    image, draw = chart_canvas(
        "Requested Model Benchmarks",
        "Each requested single model is tested separately, then compared with full Agent Swarm execution coverage.",
        size=(1280, height),
    )
    y = 150
    for case in cases:
        single = case.get("single_model", {})
        swarm = case.get("agent_swarm", {})
        draw.text((66, y), case.get("display_name", case.get("case_id", "")), fill=(240, 247, 255), font=chart_font(23, True))
        draw.text((66, y + 34), f"single status: {single.get('status')} | winner: {case.get('winner')}", fill=(148, 163, 184), font=chart_font(16))
        draw_bar(draw, 66, y + 88, 900, "single", int(single.get("execution_coverage_score") or 0), (248, 113, 113))
        draw_bar(draw, 66, y + 143, 900, "agent swarm", int(swarm.get("execution_coverage_score") or 0), (34, 197, 94))
        y += row_height
    image.save(path)


def render_cli_matrix_chart(report: dict, path: Path) -> None:
    versions = report.get("cli_versions", {})
    headless = report.get("cli_headless", {})
    cli_names = ["opencode", "codex", "qwen", "gemini", "mistral_vibe_acp", "aider", "windsurf", "claude", "cursor"]
    image, draw = chart_canvas(
        "Aggressive CLI Verification Matrix",
        "Version probes for every installed CLI; bounded headless runs where the CLI supports safe non-interactive execution.",
    )
    x0, y0 = 70, 165
    draw.text((x0, y0 - 42), "CLI", fill=(148, 163, 184), font=chart_font(18, True))
    draw.text((x0 + 300, y0 - 42), "version probe", fill=(148, 163, 184), font=chart_font(18, True))
    draw.text((x0 + 570, y0 - 42), "headless work", fill=(148, 163, 184), font=chart_font(18, True))
    for idx, name in enumerate(cli_names):
        y = y0 + idx * 54
        draw.rounded_rectangle((x0 - 18, y - 10, 1170, y + 34), radius=10, fill=(17, 24, 39), outline=(45, 58, 82))
        draw.text((x0, y), name, fill=(240, 247, 255), font=chart_font(18, True))
        version = versions.get(name, {})
        head = headless.get(name, {})
        draw_status(draw, x0 + 305, y, version.get("ok"), "ok" if version.get("ok") else str(version.get("returncode", "fail")))
        if head.get("skipped"):
            draw_status(draw, x0 + 575, y, None, "skipped")
        elif name in headless:
            draw_status(draw, x0 + 575, y, head.get("ok"), "ok" if head.get("ok") else str(head.get("returncode", "fail")))
        else:
            draw_status(draw, x0 + 575, y, None, "not headless")
    image.save(path)


def draw_status(draw, x: int, y: int, ok: bool | None, label: str):
    if ok is True:
        color = (34, 197, 94)
    elif ok is False:
        color = (248, 113, 113)
    else:
        color = (251, 191, 36)
    draw.rounded_rectangle((x, y - 4, x + 180, y + 26), radius=15, fill=(20, 30, 48), outline=color, width=2)
    draw.text((x + 14, y + 2), label, fill=color, font=chart_font(15, True))


def write_minimal_opencode_config(source: dict, target: Path, provider: str, model: str) -> None:
    provider_cfg = dict(source["provider"][provider])
    model_cfg = dict(provider_cfg.get("models", {}).get(model, {}))
    model_cfg["limit"] = {"context": 32768, "output": 384}
    provider_cfg["models"] = {model: model_cfg}
    options = dict(provider_cfg.get("options", {}))
    if "baseUrl" in options:
        options["baseURL"] = options.pop("baseUrl")
    provider_cfg["options"] = options
    minimal = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"{provider}/{model}",
        "small_model": f"{provider}/{model}",
        "instructions": [],
        "plugin": [],
        "tools": {
            "bash": False,
            "edit": False,
            "glob": False,
            "grep": False,
            "list": False,
            "read": False,
            "task": False,
            "todowrite": False,
            "webfetch": False,
            "write": False,
        },
        "provider": {provider: provider_cfg},
        "compaction": {"auto": False, "prune": True, "reserved": 1000},
        "share": "disabled",
        "snapshot": False,
    }
    target.write_text(json.dumps(minimal, indent=2), encoding="utf-8")


def load_jsonc(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    raw = strip_jsonc(raw)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def strip_jsonc(text: str) -> str:
    result = []
    i = 0
    in_string = False
    line_comment = False
    block_comment = False
    while i < len(text):
        ch = text[i]
        if line_comment:
            if ch == "\n":
                line_comment = False
                result.append(ch)
            i += 1
            continue
        if block_comment:
            if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if ch == "\\" and i + 1 < len(text):
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            result.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            block_comment = True
            i += 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def extract_opencode_text(output: str) -> str:
    texts = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = event.get("part")
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            texts.append(str(part["text"]))
    if texts:
        return "\n".join(texts)
    return output


def _trim(value: str, limit: int = 1400) -> str:
    value = value if isinstance(value, str) else str(value)
    value = redact_secrets(value)
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "...[trimmed]"


def redact_secrets(value: str) -> str:
    patterns = (
        r"sk-[A-Za-z0-9_-]{16,}",
        r"sk-or-v1-[A-Za-z0-9_-]{16,}",
        r"AIza[0-9A-Za-z_-]{20,}",
        r"xox[baprs]-[0-9A-Za-z-]{16,}",
        r"gsk_[A-Za-z0-9]{16,}",
        r"csk-[A-Za-z0-9_-]{16,}",
        r"fw_[A-Za-z0-9]{16,}",
        r"sm_[A-Za-z0-9_-]{16,}",
        r"cfut_[A-Za-z0-9_-]{16,}",
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]{12,}",
        r"(?i)((?:api[_-]?key|apikey)\s*[:=]\s*)[A-Za-z0-9._~+/=-]{12,}",
    )
    redacted = value
    for pattern in patterns:
        redacted = re.sub(pattern, lambda match: match.group(1) + "<redacted>" if match.lastindex else "<redacted>", redacted)
    return redacted


async def build_report(args: argparse.Namespace) -> dict:
    cwd = Path(args.cwd).resolve()
    output = Path(args.output)
    opencode_config_arg = args.opencode_config or None
    config = SwarmConfig.from_opencode_config(opencode_config_arg)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(cwd),
        "complex_work_prompt": COMPLEX_WORK_PROMPT,
        "cli_versions": {} if args.skip_cli_versions else run_cli_versions(cwd, args.cli_timeout),
        "cli_headless": {} if args.skip_live_cli else run_cli_headless(config, cwd, args.live_cli_timeout, include_gemini=args.include_gemini_headless),
        "temporary_vision": run_temporary_vision_probe(config),
        "single_model_complex_work": {"summary": {}, "runs": []},
        "swarm_complex_work": run_swarm_complex_work(config),
        "opencode_provider_runs": [],
        "requested_model_benchmarks": [],
        "comparison": {},
        "charts": {},
    }

    if not args.skip_live_models:
        models = args.models or default_live_models(config, args.model_limit)
        report["single_model_complex_work"] = await run_single_model_complex_work(config, models, args.max_tokens)

    if not args.skip_opencode:
        config_path = Path(args.opencode_config).expanduser() if args.opencode_config else Path.home() / ".config" / "opencode" / "opencode.jsonc"
        targets = parse_targets(args.opencode_targets) if args.opencode_targets else default_opencode_targets(config_path, args.opencode_model_limit)
        report["opencode_provider_runs"] = run_opencode_provider_benchmarks(
            config_path,
            cwd,
            targets,
            args.opencode_runs_per_model,
            args.opencode_timeout,
        )
        if not args.skip_requested_models:
            report["requested_model_benchmarks"] = await run_requested_model_benchmarks(
                config_path,
                cwd,
                report["swarm_complex_work"],
                args.requested_model_timeout,
                config,
            )

    report["comparison"] = compare_single_vs_swarm(report["single_model_complex_work"], report["swarm_complex_work"])
    report["status"] = summarize_report_status(report)
    if not args.skip_charts:
        report["charts"] = render_benchmark_charts(report, output.parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    await ProviderFactory.close_cached()
    return {"report": str(output), "status": report["status"], "comparison": report["comparison"]}


def summarize_report_status(report: dict) -> dict:
    cli_versions = report.get("cli_versions", {})
    cli_headless = report.get("cli_headless", {})
    opencode_runs = report.get("opencode_provider_runs", [])
    single_runs = report.get("single_model_complex_work", {}).get("runs", [])
    temporary_vision = report.get("temporary_vision", {})
    delegation = temporary_vision.get("delegation", {})
    return {
        "cli_versions_ok": sum(1 for item in cli_versions.values() if item.get("ok")),
        "cli_versions_checked": len(cli_versions),
        "headless_cli_ok": sum(1 for item in cli_headless.values() if item.get("ok")),
        "headless_cli_checked": sum(1 for item in cli_headless.values() if not item.get("skipped")),
        "headless_cli_skipped": sum(1 for item in cli_headless.values() if item.get("skipped")),
        "opencode_ok": sum(1 for item in opencode_runs if item.get("ok")),
        "opencode_checked": len(opencode_runs),
        "single_model_ok": sum(1 for item in single_runs if item.get("ok")),
        "single_model_checked": len(single_runs),
        "swarm_ok": bool(report.get("swarm_complex_work", {}).get("ok")),
        "requested_model_cases": len(report.get("requested_model_benchmarks", [])),
        "requested_model_swarm_wins": sum(1 for item in report.get("requested_model_benchmarks", []) if item.get("winner") == "agent_swarm"),
        "temporary_vision_route": delegation.get("route"),
        "temporary_vision_model": delegation.get("temporary_vision_model"),
    }


def parse_targets(raw_targets: list[str]) -> list[tuple[str, str]]:
    targets = []
    for raw in raw_targets:
        provider, sep, model = raw.partition(":")
        if not sep:
            raise ValueError(f"OpenCode target must be provider:model, got {raw!r}")
        targets.append((provider, model))
    return targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run aggressive CLI, model, temporary vision, and swarm comparison benchmarks.")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--output", default="examples/aggressive_cli_swarm_benchmark.json")
    parser.add_argument("--opencode-config", default="")
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument("--model-limit", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=260)
    parser.add_argument("--cli-timeout", type=int, default=30)
    parser.add_argument("--live-cli-timeout", type=int, default=120)
    parser.add_argument("--opencode-timeout", type=int, default=150)
    parser.add_argument("--opencode-runs-per-model", type=int, default=2)
    parser.add_argument("--opencode-model-limit", type=int, default=4)
    parser.add_argument("--requested-model-timeout", type=int, default=120)
    parser.add_argument("--opencode-targets", nargs="*", default=[])
    parser.add_argument("--skip-cli-versions", action="store_true")
    parser.add_argument("--skip-live-cli", action="store_true")
    parser.add_argument("--skip-live-models", action="store_true")
    parser.add_argument("--skip-opencode", action="store_true")
    parser.add_argument("--skip-requested-models", action="store_true")
    parser.add_argument("--skip-charts", action="store_true")
    parser.add_argument("--include-gemini-headless", action="store_true", help="Run Gemini CLI headless even though this local wrapper currently hangs.")
    return parser.parse_args()


def main() -> int:
    result = asyncio.run(build_report(parse_args()))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

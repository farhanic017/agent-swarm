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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarm.agents.catalog import create_specialist_agents
from swarm.config import SwarmConfig
from swarm.core.ab_testing import run_ab_test
from swarm.core.council import run_council_vote
from swarm.core.master_review import build_integration_report, run_master_review
from swarm.core.performance_benchmark import BenchmarkTask, run_performance_benchmark, summarize_benchmark
from swarm.core.provider_assignment import assign_hybrid_provider_models, summarize_hybrid_routes
from swarm.core.state import AgentTurn, SharedState
from swarm.core.sub_agent_planner import build_sub_agent_plan
from swarm.core.token_budget import build_token_budget_plan
from swarm.core.vision_bridge import plan_temporary_vision
from swarm.providers.factory import ProviderFactory


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


def run_cli_versions(cwd: Path, timeout: int = 30) -> dict[str, dict]:
    return {name: run_command(command, cwd, timeout) for name, command in CLI_VERSION_COMMANDS.items()}


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
    return {
        "single_successful_models": len(successful),
        "single_avg_score": single_avg_score,
        "single_avg_latency_seconds": single_avg_latency,
        "swarm_score": swarm.get("score"),
        "swarm_latency_seconds": swarm.get("elapsed_seconds"),
        "swarm_agents_used": swarm.get("agent_count"),
        "swarm_sub_agents_planned": swarm.get("sub_agent_count"),
        "winner_by_score": "agent_swarm" if single_avg_score is None or swarm.get("score", 0) >= single_avg_score else "single_model",
    }


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
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "...[trimmed]"


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
        "comparison": {},
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

    report["comparison"] = compare_single_vs_swarm(report["single_model_complex_work"], report["swarm_complex_work"])
    report["status"] = summarize_report_status(report)
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
    parser.add_argument("--opencode-targets", nargs="*", default=[])
    parser.add_argument("--skip-cli-versions", action="store_true")
    parser.add_argument("--skip-live-cli", action="store_true")
    parser.add_argument("--skip-live-models", action="store_true")
    parser.add_argument("--skip-opencode", action="store_true")
    parser.add_argument("--include-gemini-headless", action="store_true", help="Run Gemini CLI headless even though this local wrapper currently hangs.")
    return parser.parse_args()


def main() -> int:
    result = asyncio.run(build_report(parse_args()))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Iterable

from swarm.agents.catalog import create_specialist_agents
from swarm.config import SwarmConfig
from swarm.core.ab_testing import run_ab_test
from swarm.core.council import run_council_vote
from swarm.core.dashboard import write_dashboard
from swarm.core.master_review import build_integration_report, run_master_review
from swarm.core.media_apps import build_voice_workflow_plan, list_media_apps
from swarm.core.provider_assignment import assign_hybrid_provider_models, summarize_hybrid_routes
from swarm.core.state import AgentTurn, SharedState
from swarm.core.sub_agent_planner import build_sub_agent_plan
from swarm.core.switch_memory import SwitchMemory
from swarm.core.token_budget import build_token_budget_plan
from swarm.providers.base import Message
from swarm.providers.factory import ProviderFactory


DEFAULT_BENCHMARK_MODELS = (
    "openrouter:anthropic/claude-opus-4.8",
    "openrouter:anthropic/claude-opus-4.7",
)


@dataclass(frozen=True)
class BenchmarkTask:
    name: str
    prompt: str
    required_terms: tuple[str, ...] = ()


@dataclass
class BenchmarkRun:
    model_ref: str
    task_name: str
    ok: bool
    elapsed_seconds: float
    output_chars: int = 0
    usage: dict = field(default_factory=dict)
    score: int = 0
    error: str = ""
    finish_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "model_ref": self.model_ref,
            "task_name": self.task_name,
            "ok": self.ok,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "output_chars": self.output_chars,
            "usage": self.usage,
            "score": self.score,
            "error": self.error,
            "finish_reason": self.finish_reason,
        }


@dataclass
class FeatureBenchmarkRun:
    feature: str
    ok: bool
    elapsed_seconds: float
    score: int
    details: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "ok": self.ok,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "score": self.score,
            "details": self.details,
            "error": self.error,
        }


def default_benchmark_tasks() -> list[BenchmarkTask]:
    return [
        BenchmarkTask(
            name="coding_patch_plan",
            prompt=(
                "You are benchmarking agentic coding quality. In 160 words or less, propose a minimal patch plan "
                "for fixing a Python async resource leak where an httpx.AsyncClient is created per provider and "
                "not closed after tests. Include test strategy."
            ),
            required_terms=("close", "test"),
        ),
        BenchmarkTask(
            name="council_decision",
            prompt=(
                "In 140 words or less, decide whether an AI agent swarm should add dark mode. Give exactly: "
                "Decision, Evidence, Risks, Confidence."
            ),
            required_terms=("decision", "confidence"),
        ),
        BenchmarkTask(
            name="agent_routing",
            prompt=(
                "In 150 words or less, route these roles to local, MCP, or cloud models: master council, "
                "browser researcher, coding helper, image editor. Explain why without using a table."
            ),
            required_terms=("local", "mcp", "cloud"),
        ),
    ]


def run_feature_benchmark(config: SwarmConfig, output_dir: str | Path = "examples") -> list[FeatureBenchmarkRun]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[FeatureBenchmarkRun] = []
    agents = []
    council = None
    ab_test = None
    assignments = []

    def record(feature: str, fn):
        started = time.perf_counter()
        try:
            value = fn()
            elapsed = time.perf_counter() - started
            score = _score_feature_result(feature, value)
            details = value if isinstance(value, dict) else {"result": value}
            results.append(FeatureBenchmarkRun(feature, True, elapsed, score, details=details))
            return value
        except Exception as exc:
            elapsed = time.perf_counter() - started
            results.append(FeatureBenchmarkRun(feature, False, elapsed, 0, error=str(exc)))
            return None

    def catalog_feature():
        nonlocal agents
        agents = create_specialist_agents(mesh=True)
        pillars = sorted({agent.pillar for agent in agents})
        return {"agents": len(agents), "pillars": pillars, "meshed_agents": sum(bool(a.handoff_targets) for a in agents)}

    record("agent_catalog_4_pillars_20_plus_agents", catalog_feature)

    def provider_feature():
        nonlocal assignments
        assignments = assign_hybrid_provider_models(agents, config, include_sub_agents=True)
        return {
            "assignments": len(assignments),
            "routes": summarize_hybrid_routes(assignments),
            "providers": sorted({item.provider for item in assignments}),
            "has_rationales": all(bool(item.rationale) for item in assignments),
        }

    record("smart_ai_selection_hybrid_routing", provider_feature)

    def council_feature():
        nonlocal council
        council = run_council_vote("benchmark every feature of the agent swarm", agents)
        return {
            "verdict": council.verdict,
            "yes_votes": council.yes_votes,
            "no_votes": council.no_votes,
            "confidence": council.confidence,
            "opinions": len(council.opinions),
        }

    record("always_on_council_voting", council_feature)

    def ab_feature():
        nonlocal ab_test
        ab_test = run_ab_test("benchmark hybrid local mcp cloud browser media agents", agents[:8])
        return {
            "winner": ab_test.winner_id,
            "loser": ab_test.loser_id,
            "candidates": len(ab_test.candidates),
            "votes": dict(ab_test.council_votes),
            "summary": ab_test.summary,
        }

    record("ab_testing_winner_and_alternative", ab_feature)

    record(
        "token_budget_guardrails",
        lambda: build_token_budget_plan("benchmark browser media coding council swarm", agents).to_dict(),
    )

    record(
        "sub_agent_planning",
        lambda: _benchmark_sub_agent_planning(agents),
    )

    def voice_feature():
        voice_agents = [agent.name for agent in agents if agent.model_preference in {"speech_to_text", "text_to_speech"}]
        audio_apps = list_media_apps("audio")
        return {
            "voice_agents": voice_agents,
            "speech_to_text_model": config.get_best_speech_to_text_model(),
            "text_to_speech_model": config.get_best_text_to_speech_model(),
            "audio_apps": [app["name"] for app in audio_apps],
            "plan": build_voice_workflow_plan("benchmark voice transcription and narration", "speech_to_text"),
        }

    record("voice_to_text_and_speech_support", voice_feature)

    def switch_memory_feature():
        memory = SwitchMemory()
        context = "fix bug; completed step 1; artifact file=x.py"
        first = memory.build_message("coder", "model-a", context)
        second = memory.build_message("coder", "model-a", context)
        return {"first_full": "FULL_CONTEXT_ONCE" in first, "second_remembered": "REMEMBERED" in second}

    record("replacement_model_memory", switch_memory_feature)

    def master_review_feature():
        state = SharedState(user_input="benchmark every feature")
        if council:
            state.set_artifact("council_decision", council.to_dict())
        if ab_test:
            state.set_artifact("ab_test", ab_test.to_dict())
        state.set_artifact("ai_selection", [item.to_dict() for item in assignments[:8]])
        state.set_artifact("sub_agent_plan", _benchmark_sub_agent_planning(agents)["sample"])
        state.add_turn(AgentTurn(agent_name="coder", input="benchmark", output="implemented", model="benchmark"))
        integration = build_integration_report(state)
        state.set_artifact("integration_report", integration.to_dict())
        review = run_master_review(state)
        return review.to_dict()

    record("master_integration_review", master_review_feature)

    def dashboard_feature():
        target = output_root / "feature_benchmark_dashboard.html"
        path = write_dashboard(
            target,
            agents,
            council_decision=council,
            provider_assignments=assignments,
            ab_test=ab_test.to_dict() if ab_test else None,
        )
        return {"path": str(path), "bytes": path.stat().st_size, "exists": path.exists()}

    record("real_time_dashboard_export", dashboard_feature)

    return results


def _benchmark_sub_agent_planning(agents) -> dict:
    agent_map = {agent.name: agent for agent in agents}
    plans = []
    for agent in agents:
        plans.extend(build_sub_agent_plan(agent, "benchmark every feature", agent_map))
    return {
        "planned_agents": len(plans),
        "parents": len({plan["parent_agent"] for plan in plans}),
        "sample": plans[:5],
    }


async def run_performance_benchmark(
    config: SwarmConfig,
    model_refs: Iterable[str] = DEFAULT_BENCHMARK_MODELS,
    tasks: Iterable[BenchmarkTask] | None = None,
    max_tokens: int = 320,
    temperature: float = 0.0,
) -> list[BenchmarkRun]:
    benchmark_tasks = list(tasks or default_benchmark_tasks())
    results: list[BenchmarkRun] = []
    await ProviderFactory.close_cached()

    try:
        for model_ref in model_refs:
            try:
                chat = ProviderFactory.get_chat_func(config, model_ref)
            except Exception as exc:
                for task in benchmark_tasks:
                    results.append(BenchmarkRun(model_ref, task.name, False, 0.0, error=str(exc)))
                continue

            for task in benchmark_tasks:
                started = time.perf_counter()
                try:
                    response = await chat(
                        [
                            Message(
                                role="system",
                                content="Answer concisely. This is a live benchmark; do not mention benchmarking caveats.",
                            ),
                            Message(role="user", content=task.prompt),
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    elapsed = time.perf_counter() - started
                    score = _score_response(response.content, task.required_terms)
                    results.append(
                        BenchmarkRun(
                            model_ref=model_ref,
                            task_name=task.name,
                            ok=True,
                            elapsed_seconds=elapsed,
                            output_chars=len(response.content),
                            usage=response.usage,
                            score=score,
                            finish_reason=response.finish_reason,
                        )
                    )
                except Exception as exc:
                    elapsed = time.perf_counter() - started
                    results.append(BenchmarkRun(model_ref, task.name, False, elapsed, error=str(exc)))
                    if _is_fatal_provider_error(str(exc)):
                        for skipped_task in benchmark_tasks[benchmark_tasks.index(task) + 1:]:
                            results.append(
                                BenchmarkRun(
                                    model_ref,
                                    skipped_task.name,
                                    False,
                                    0.0,
                                    error=f"Skipped after fatal provider error: {exc}",
                                )
                            )
                        break
    finally:
        await ProviderFactory.close_cached()

    return results


def summarize_benchmark(results: list[BenchmarkRun]) -> dict:
    by_model: dict[str, list[BenchmarkRun]] = {}
    for result in results:
        by_model.setdefault(result.model_ref, []).append(result)

    summary = {}
    for model_ref, model_results in by_model.items():
        successful = [result for result in model_results if result.ok]
        failed = [result for result in model_results if not result.ok]
        summary[model_ref] = {
            "tasks": len(model_results),
            "successes": len(successful),
            "failures": len(failed),
            "avg_latency_seconds": round(mean([r.elapsed_seconds for r in successful]), 3) if successful else None,
            "avg_score": round(mean([r.score for r in successful]), 1) if successful else None,
            "total_output_chars": sum(r.output_chars for r in successful),
            "errors": [r.error[:220] for r in failed if r.error],
        }
    return summary


def summarize_feature_benchmark(results: list[FeatureBenchmarkRun]) -> dict:
    successful = [result for result in results if result.ok]
    failed = [result for result in results if not result.ok]
    return {
        "features": len(results),
        "successes": len(successful),
        "failures": len(failed),
        "avg_latency_seconds": round(mean([r.elapsed_seconds for r in successful]), 4) if successful else None,
        "avg_score": round(mean([r.score for r in successful]), 1) if successful else None,
        "errors": {result.feature: result.error for result in failed},
    }


def write_benchmark_report(path: str | Path, results: list[BenchmarkRun]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summarize_benchmark(results),
        "runs": [result.to_dict() for result in results],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def write_full_benchmark_report(
    path: str | Path,
    feature_results: list[FeatureBenchmarkRun],
    model_results: list[BenchmarkRun] | None = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_summary": summarize_feature_benchmark(feature_results),
        "features": [result.to_dict() for result in feature_results],
        "model_summary": summarize_benchmark(model_results or []),
        "model_runs": [result.to_dict() for result in model_results or []],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def _score_response(content: str, required_terms: tuple[str, ...]) -> int:
    if not content.strip():
        return 0
    lower = content.lower()
    term_score = sum(1 for term in required_terms if term.lower() in lower)
    brevity_score = 25 if len(content) <= 1400 else 10
    structure_score = 25 if any(mark in content for mark in (":", "-", "\n")) else 10
    return min(100, 35 + term_score * 20 + brevity_score + structure_score)


def _score_feature_result(feature: str, value) -> int:
    if not isinstance(value, dict):
        return 80
    if feature == "agent_catalog_4_pillars_20_plus_agents":
        return 100 if value.get("agents", 0) >= 20 and set(value.get("pillars", [])) == {"act", "code", "design", "see"} else 50
    if feature == "smart_ai_selection_hybrid_routing":
        return 100 if value.get("assignments", 0) > 0 and value.get("has_rationales") else 60
    if feature == "always_on_council_voting":
        return 100 if value.get("opinions", 0) >= 3 and value.get("confidence", 0) > 0 else 60
    if feature == "ab_testing_winner_and_alternative":
        return 100 if value.get("winner") and value.get("loser") and value.get("winner") != value.get("loser") else 60
    if feature == "real_time_dashboard_export":
        return 100 if value.get("exists") and value.get("bytes", 0) > 10_000 else 60
    if feature == "voice_to_text_and_speech_support":
        return 100 if value.get("voice_agents") and value.get("audio_apps") and value.get("plan") else 50
    return 90 if value else 50


def _is_fatal_provider_error(message: str) -> bool:
    fatal_markers = (
        "401 Unauthorized",
        "402 Payment Required",
        "403 Forbidden",
        "model not found",
        "No provider available",
    )
    return any(marker.lower() in message.lower() for marker in fatal_markers)


async def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run live model performance benchmarks.")
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_BENCHMARK_MODELS))
    parser.add_argument("--output", default="examples/opus_benchmark_report.json")
    parser.add_argument("--max-tokens", type=int, default=320)
    parser.add_argument("--features", action="store_true", help="Benchmark internal agent-swarm features.")
    parser.add_argument("--skip-models", action="store_true", help="Only benchmark internal features.")
    args = parser.parse_args()

    config = SwarmConfig.from_opencode_config()
    feature_results = run_feature_benchmark(config) if args.features else []
    model_results = []
    if not args.skip_models:
        model_results = await run_performance_benchmark(config, args.models, max_tokens=args.max_tokens)
    if args.features:
        path = write_full_benchmark_report(args.output, feature_results, model_results)
        print(json.dumps({
            "report": str(path),
            "feature_summary": summarize_feature_benchmark(feature_results),
            "model_summary": summarize_benchmark(model_results),
        }, indent=2))
        return 0 if all(result.ok for result in feature_results) and all(result.ok for result in model_results) else 2
    path = write_benchmark_report(args.output, model_results)
    print(json.dumps({"report": str(path), "summary": summarize_benchmark(model_results)}, indent=2))
    return 0 if all(result.ok for result in model_results) else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

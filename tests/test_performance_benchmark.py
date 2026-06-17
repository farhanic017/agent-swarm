import json

from swarm.core.performance_benchmark import (
    BenchmarkRun,
    _is_fatal_provider_error,
    run_feature_benchmark,
    summarize_feature_benchmark,
    summarize_benchmark,
    write_full_benchmark_report,
    write_benchmark_report,
)
from swarm.config import ProviderConfig, SwarmConfig


def test_summarize_benchmark_groups_successes_and_failures():
    results = [
        BenchmarkRun("m:a", "task1", True, 1.0, output_chars=100, score=80),
        BenchmarkRun("m:a", "task2", True, 3.0, output_chars=200, score=100),
        BenchmarkRun("m:b", "task1", False, 0.5, error="missing credentials"),
    ]

    summary = summarize_benchmark(results)

    assert summary["m:a"]["successes"] == 2
    assert summary["m:a"]["avg_latency_seconds"] == 2.0
    assert summary["m:a"]["avg_score"] == 90.0
    assert summary["m:a"]["total_output_chars"] == 300
    assert summary["m:b"]["failures"] == 1
    assert summary["m:b"]["errors"] == ["missing credentials"]


def test_write_benchmark_report(tmp_path):
    report = tmp_path / "bench.json"
    path = write_benchmark_report(report, [BenchmarkRun("m:a", "task", True, 1.2, score=75)])

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["m:a"]["successes"] == 1
    assert data["runs"][0]["elapsed_seconds"] == 1.2


def test_fatal_provider_error_detection():
    assert _is_fatal_provider_error("Client error '402 Payment Required'")
    assert _is_fatal_provider_error("No provider available for model")
    assert not _is_fatal_provider_error("temporary timeout")


def test_feature_benchmark_covers_swarm_capabilities(tmp_path):
    cfg = SwarmConfig(
        providers={
            "openclaw": ProviderConfig(api_key="", endpoint="http://localhost:7331/v1", models={"openclaw/director": {}}),
            "openrouter": ProviderConfig(api_key="x", models={"nous/hermes-3": {}, "qwen/qwen3-coder:free": {}}),
        }
    )

    results = run_feature_benchmark(cfg, output_dir=tmp_path)
    summary = summarize_feature_benchmark(results)

    assert summary["failures"] == 0
    assert summary["features"] >= 9
    assert {result.feature for result in results} >= {
        "agent_catalog_4_pillars_20_plus_agents",
        "smart_ai_selection_hybrid_routing",
        "always_on_council_voting",
        "ab_testing_winner_and_alternative",
        "hermes_self_evolution_skill_creation",
        "long_session_n8n_game_social_parallel_work",
        "advanced_capabilities_and_auto_learner",
        "temporary_vision_bridge_routes",
        "real_time_dashboard_export",
    }
    vision_result = next(result for result in results if result.feature == "temporary_vision_bridge_routes")
    assert vision_result.details["plan_mode_questions"] >= 7
    assert vision_result.details["build_mode_route_without_vision"] == "continue_without_annoying_user"

    report = write_full_benchmark_report(tmp_path / "full.json", results, [])
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["feature_summary"]["successes"] == summary["successes"]

import asyncio
import json
from pathlib import Path

import scripts.run_aggressive_cli_benchmark as benchmark_script
from scripts.run_aggressive_cli_benchmark import (
    PUBLIC_BENCHMARK_POINTS,
    build_comparison_card_points,
    compare_single_vs_swarm,
    default_opencode_targets,
    normalize_cli_version_result,
    order_metric_points,
    render_benchmark_charts,
    run_requested_model_benchmarks,
    run_swarm_complex_work,
    run_temporary_vision_probe,
    strip_jsonc,
)
from swarm.config import ProviderConfig, SwarmConfig


def test_temporary_vision_probe_uses_configured_vision_model():
    cfg = SwarmConfig(
        providers={
            "openai": ProviderConfig(
                api_key="x",
                models={
                    "gpt-4o": {"modalities": ["vision"]},
                    "gpt-4.1-mini": {},
                },
            )
        }
    )

    probe = run_temporary_vision_probe(cfg)

    assert probe["configured_vision_model"] == "openai:gpt-4o"
    assert probe["delegation"]["route"] == "delegate_to_temporary_vision_model"
    assert probe["delegation"]["temporary_vision_model"] == "openai:gpt-4o"
    assert probe["plan_mode_no_vision"]["questions"]
    assert probe["build_mode_no_vision"]["route"] == "continue_without_annoying_user"


def test_swarm_complex_work_returns_multi_agent_review():
    cfg = SwarmConfig(
        providers={
            "openrouter": ProviderConfig(api_key="x", models={"qwen/qwen3-coder:free": {}}),
            "mistral": ProviderConfig(api_key="x", models={"mistral-small-latest": {}}),
        }
    )

    result = run_swarm_complex_work(cfg)

    assert result["ok"]
    assert result["agent_count"] >= 6
    assert result["sub_agent_count"] >= 1
    assert result["council"]["opinions"]
    assert result["master_review"]["status"] == "pass"


def test_compare_single_vs_swarm_picks_swarm_when_score_is_higher():
    single = {
        "runs": [
            {"ok": True, "score": 70, "elapsed_seconds": 1.0},
            {"ok": True, "score": 80, "elapsed_seconds": 3.0},
        ]
    }
    swarm = {"score": 95, "elapsed_seconds": 0.2, "agent_count": 8, "sub_agent_count": 12}

    comparison = compare_single_vs_swarm(single, swarm)

    assert comparison["single_avg_response_score"] == 75.0
    assert comparison["single_execution_coverage_score"] < comparison["swarm_execution_coverage_score"]
    assert comparison["single_avg_latency_seconds"] == 2.0
    assert comparison["winner_by_execution_coverage"] == "agent_swarm"


def test_default_opencode_targets_parse_jsonc(tmp_path):
    config = tmp_path / "opencode.jsonc"
    config.write_text(
        """
        {
          // provider comments are allowed
          "provider": {
            "cloudflare": {"models": {"@cf/qwen/qwen2.5-coder-32b-instruct": {}}},
            "mistral": {"models": {"mistral-small-latest": {}}},
          },
        }
        """,
        encoding="utf-8",
    )

    assert json.loads(strip_jsonc('{"a": 1\n}'))["a"] == 1
    assert default_opencode_targets(config, 3) == [
        ("cloudflare", "@cf/qwen/qwen2.5-coder-32b-instruct"),
        ("mistral", "mistral-small-latest"),
    ]


def test_requested_model_benchmarks_record_blocked_models_without_crashing(tmp_path, monkeypatch):
    config = tmp_path / "opencode.jsonc"
    config.write_text('{"provider": {"openrouter": {"models": {}}}}', encoding="utf-8")
    swarm = {"ok": True, "score": 100, "agent_count": 12, "sub_agent_count": 20, "council": {"opinions": [1]}, "master_review": {"status": "pass"}}

    monkeypatch.setattr(benchmark_script, "run_command", lambda *args, **kwargs: {"ok": False, "stderr": "blocked", "returncode": "blocked"})
    monkeypatch.setattr(
        benchmark_script,
        "run_opencode_direct_model_benchmark",
        lambda *args, **kwargs: {"ok": False, "stderr": "model unavailable", "elapsed_seconds": 0, "stdout_text": ""},
    )
    results = asyncio.run(run_requested_model_benchmarks(config, tmp_path, swarm, timeout=1))

    assert len(results) == 4
    assert all(item["winner"] == "agent_swarm" for item in results)
    assert any(item["case_id"] == "codex_gpt_5_5" for item in results)
    assert any(item["case_id"] == "qwen_cli" for item in results)


def test_codex_desktop_probe_counts_as_ok_when_windowsapps_blocks_version():
    result = normalize_cli_version_result(
        "codex",
        {
            "command": ["codex", "--version"],
            "resolved_command": ["C:\\Program Files\\WindowsApps\\OpenAI.Codex\\codex.EXE", "--version"],
            "available": True,
            "ok": False,
            "stdout": "",
            "stderr": "[WinError 5] Access is denied",
            "returncode": "oserror",
        },
    )

    assert result["ok"] is True
    assert result["returncode"] == "desktop-detected"
    assert result["stdout"] == "Codex desktop app detected"


def test_benchmark_chart_renderer_writes_pngs(tmp_path):
    report = {
        "comparison": {
            "single_avg_response_score": 76,
            "single_execution_coverage_score": 58,
            "swarm_execution_coverage_score": 100,
            "winner_by_execution_coverage": "agent_swarm",
            "scoring_note": "test note",
        },
        "requested_model_benchmarks": [
            {
                "case_id": "case",
                "display_name": "Case",
                "winner": "agent_swarm",
                "single_model": {"status": "blocked", "execution_coverage_score": 0},
                "agent_swarm": {"execution_coverage_score": 100},
            }
        ],
        "cli_versions": {"opencode": {"ok": True}, "codex": {"ok": True, "returncode": "desktop-detected"}},
        "cli_headless": {"qwen": {"ok": True}, "gemini": {"skipped": True}},
    }

    charts = render_benchmark_charts(report, tmp_path)

    assert set(charts) == {"swarm_vs_single", "cli_matrix", "coding_models"}
    assert all(Path(path).exists() for path in charts.values())


def test_public_benchmark_points_cover_popular_models_without_missing_metrics():
    names = {point["name"] for point in PUBLIC_BENCHMARK_POINTS}
    assert {
        "Mistral Medium 3.1",
        "Llama 4 Maverick",
        "Gemini 2.5 Pro",
        "GLM 4.5",
        "MiMo V2.5 Pro",
        "MiniMax M2",
        "Kimi K2.6",
        "Grok 4.3",
        "Qwen3 Coder 480B",
    }.issubset(names)

    points = build_comparison_card_points({"comparison": {}, "swarm_complex_work": {"agent_count": 12, "sub_agent_count": 20}})
    for point in points:
        for metric in ("intelligence", "speed", "price", "swe_bench_pro", "terminal_bench", "coding"):
            assert isinstance(point.get(metric), (int, float)), (point["name"], metric)


def test_metric_cards_keep_kimi_visible_when_requested_models_are_added():
    points = build_comparison_card_points(
        {
            "comparison": {},
            "swarm_complex_work": {"agent_count": 12, "sub_agent_count": 20},
            "requested_model_benchmarks": [
                {
                    "display_name": f"Requested Model {index}",
                    "single_model": {"ok": True, "execution_coverage_score": 90 - index, "elapsed_seconds": 1, "details": "output_chars=1000"},
                }
                for index in range(8)
            ],
        }
    )

    for metric, higher_better in (("intelligence", True), ("speed", True), ("price", False), ("coding", True)):
        ordered = order_metric_points(points, metric, higher_better, limit=12)
        names = {point["name"] for point in ordered}
        assert "Agent Swarm" in names
        assert "Kimi K2.6" in names

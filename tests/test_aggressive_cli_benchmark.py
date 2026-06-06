import json

from scripts.run_aggressive_cli_benchmark import (
    compare_single_vs_swarm,
    default_opencode_targets,
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

    assert comparison["single_avg_score"] == 75.0
    assert comparison["single_avg_latency_seconds"] == 2.0
    assert comparison["winner_by_score"] == "agent_swarm"


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

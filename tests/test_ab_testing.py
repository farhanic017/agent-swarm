from swarm.agents.catalog import create_specialist_agents
from swarm.core.ab_testing import run_ab_test


def test_ab_test_returns_winner_and_alternative():
    result = run_ab_test("build hybrid browser media feature", create_specialist_agents()[:8])
    data = result.to_dict()
    assert data["winner_id"] in {"A", "B"}
    assert data["loser_id"] in {"A", "B"}
    assert data["winner_id"] != data["loser_id"]
    assert len(data["candidates"]) == 2
    assert data["summary"]


def test_ab_test_prefers_hybrid_for_complex_hybrid_prompt():
    result = run_ab_test(
        "test hybrid local cloud mcp browser image video media workflow",
        create_specialist_agents()[:8],
    )
    assert result.winner_id == "B"
    assert "Hybrid" in result.winner.name

import pytest

from swarm.agents.catalog import create_specialist_agents
from swarm.core.council import run_council_vote


def test_council_dark_mode_votes_proceed_with_reasoning():
    decision = run_council_vote("should we add dark mode?", create_specialist_agents(), quorum=6)
    assert decision.verdict == "proceed"
    assert decision.yes_votes == 6
    assert decision.no_votes == 0
    assert decision.confidence >= 80
    assert len(decision.opinions) == 6
    assert all(opinion.reasoning for opinion in decision.opinions)
    assert any(opinion.agent_name == "ux_research" for opinion in decision.opinions)


def test_council_crypto_selects_risk_specialists():
    decision = run_council_vote("analyze crypto market and suggest trading plan", create_specialist_agents(), quorum=6)
    names = {opinion.agent_name for opinion in decision.opinions}
    assert {"trading", "finance", "analytics", "legal"}.issubset(names)
    assert decision.yes_votes + decision.no_votes == 6
    assert 1 <= decision.confidence <= 99


def test_council_rejects_high_risk_request_by_majority_guardrails():
    decision = run_council_vote(
        "delete private credentials for unsafe trading with illegal risk",
        create_specialist_agents(),
        quorum=6,
    )
    assert decision.no_votes >= 3
    assert decision.conflicts or decision.verdict == "reject"
    assert any(opinion.risks for opinion in decision.opinions)


def test_council_validates_inputs():
    with pytest.raises(ValueError):
        run_council_vote("", create_specialist_agents())
    with pytest.raises(ValueError):
        run_council_vote("ship it", create_specialist_agents(), quorum=0)
    with pytest.raises(ValueError):
        run_council_vote("ship it", create_specialist_agents()[:2], quorum=6)

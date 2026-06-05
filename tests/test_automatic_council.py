import pytest

from swarm.agents.catalog import create_specialist_agents
from swarm.config import SwarmConfig
from swarm.core.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_always_records_council_before_agent_work():
    cfg = SwarmConfig()
    cfg.max_iterations = 0
    orch = Orchestrator(config=cfg)
    orch.register_agents(*create_specialist_agents())

    state = await orch.run("should we add dark mode?", verbose=False)

    assert "council_decision" in state.metadata
    assert state.metadata["council_decision"]["vote_line"] == "6/6 YES"
    assert state.get_artifact("council_decision")["verdict"] == "proceed"
    assert state.get_artifact("sub_agent_plan")
    assert state.get_artifact("ab_test")
    assert state.metadata["ab_test"]["winner_id"] in {"A", "B"}
    assert state.metadata["agent_communication_mesh"]["all_agents_can_message_each_other"]
    assert state.get_artifact("integration_report")
    assert state.get_artifact("master_review")
    assert state.metadata["master_review"]["checks"]["council_completed"]
    assert state.metadata["token_budget"]["max_swarm_tokens"] >= state.metadata["token_budget"]["single_agent_estimate"]
    assert state.metadata["learning_stats"]["total_lessons"] >= 1
    assert "ai_selection" in state.metadata
    assert "route_summary" in state.metadata["ai_selection"]


@pytest.mark.asyncio
async def test_automatic_council_uses_small_swarm_as_quorum():
    cfg = SwarmConfig()
    cfg.max_iterations = 0
    agents = create_specialist_agents()[:3]
    orch = Orchestrator(config=cfg)
    orch.register_agents(*agents)

    state = await orch.run("build a feature", verbose=False)

    assert state.metadata["council_decision"]["yes_votes"] == 3
    assert state.metadata["council_decision"]["vote_line"] == "3/3 YES"

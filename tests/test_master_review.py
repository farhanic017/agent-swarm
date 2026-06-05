from swarm.core.master_review import build_integration_report, run_master_review
from swarm.core.state import AgentTurn, SharedState


def test_master_review_passes_connected_successful_run():
    state = SharedState(user_input="build feature")
    state.set_artifact("council_decision", {"verdict": "proceed"})
    state.set_artifact("sub_agent_plan", [{"sub_agent": "testing"}])
    state.add_turn(AgentTurn(agent_name="coder", input="build", output="done", model="m"))

    integration = build_integration_report(state)
    state.set_artifact("integration_report", integration.to_dict())
    review = run_master_review(state)

    assert "agent_outputs" in integration.connected_parts
    assert review.status == "pass"
    assert review.confidence == 100


def test_master_review_flags_model_failures_and_missing_parts():
    state = SharedState(user_input="build feature")
    state.add_turn(
        AgentTurn(
            agent_name="coder",
            input="build",
            output="[ALL MODELS FAILED] out of credits",
            model="unknown",
        )
    )
    integration = build_integration_report(state)
    state.set_artifact("integration_report", integration.to_dict())
    review = run_master_review(state)

    assert review.status == "needs_attention"
    assert review.confidence < 100
    assert review.risks

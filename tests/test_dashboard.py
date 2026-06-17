from pathlib import Path

from swarm.agents.catalog import create_specialist_agents
from swarm.config import ProviderConfig, SwarmConfig
from swarm.core.ab_testing import run_ab_test
from swarm.core.council import run_council_vote
from swarm.core.dashboard import build_dashboard_payload, render_dashboard_html, write_dashboard
from swarm.core.provider_assignment import assign_distinct_provider_models


def test_dashboard_payload_contains_agents_and_council():
    agents = create_specialist_agents()
    decision = run_council_vote("should we add dark mode?", agents)
    assignments = assign_distinct_provider_models(
        agents,
        SwarmConfig(providers={"p1": ProviderConfig(api_key="x", models={"m1": {}})}),
    )
    ab_test = run_ab_test("should we add dark mode?", agents[:8]).to_dict()
    payload = build_dashboard_payload(agents, decision, assignments, ab_test)
    assert len(payload["agents"]) >= 20
    assert payload["council"]["verdict"] == "proceed"
    assert payload["council"]["confidence"] == decision.confidence
    assert payload["provider_assignments"]
    assert payload["ab_test"]["winner_id"] in {"A", "B"}
    assert {"name", "pillar", "category", "model", "model_preference", "provider", "route_type", "selection_rationale", "sub_agent_roles", "code"}.issubset(payload["agents"][0])


def test_dashboard_html_includes_realtime_features():
    agents = create_specialist_agents()
    decision = run_council_vote("build a feature", agents)
    html = render_dashboard_html(build_dashboard_payload(agents, decision))
    assert "Agent Swarm Real-Time Dashboard" in html
    assert "agentGraph" in html
    assert "focusGraphAgent" in html
    assert "advanceLiveDemo" in html
    assert "typeCode" in html
    assert "setInterval" in html
    assert "File Growth" in html
    assert "bytes written" in html
    assert "model type" in html
    assert "why this AI" in html
    assert "sub-agents" in html
    assert "Council Meeting" in html
    assert "A/B Selection" in html
    assert "renderABTest" in html


def test_write_dashboard_creates_html_file(tmp_path: Path):
    agents = create_specialist_agents()
    decision = run_council_vote("build dark mode", agents)
    output = write_dashboard(tmp_path / "dashboard.html", agents, decision)
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "dark mode" in text
    assert "coder" in text

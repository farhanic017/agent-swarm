from swarm.agents.catalog import create_specialist_agents
from swarm.core.token_budget import build_token_budget_plan, estimate_single_agent_tokens, should_stop_for_budget


def test_token_budget_is_bounded_against_single_agent_estimate():
    prompt = "Build a small landing page"
    estimate = estimate_single_agent_tokens(prompt)
    plan = build_token_budget_plan(prompt, create_specialist_agents())

    assert plan.single_agent_estimate == estimate
    assert plan.max_swarm_tokens <= int(estimate * 2.2)
    assert plan.max_iterations <= 8
    assert plan.max_parallel_agents <= 6


def test_token_budget_stop_condition():
    plan = build_token_budget_plan("short task", create_specialist_agents())
    assert not should_stop_for_budget(plan.max_swarm_tokens - 1, plan)
    assert should_stop_for_budget(plan.max_swarm_tokens, plan)

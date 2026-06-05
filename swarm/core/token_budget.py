from __future__ import annotations

from dataclasses import dataclass

from swarm.core.agent import Agent


@dataclass(frozen=True)
class TokenBudgetPlan:
    single_agent_estimate: int
    max_swarm_tokens: int
    max_iterations: int
    max_parallel_agents: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "single_agent_estimate": self.single_agent_estimate,
            "max_swarm_tokens": self.max_swarm_tokens,
            "max_iterations": self.max_iterations,
            "max_parallel_agents": self.max_parallel_agents,
            "reason": self.reason,
        }


def estimate_single_agent_tokens(prompt: str) -> int:
    # Conservative rough estimate: 4 chars/token input plus expected response.
    input_tokens = max(1, len(prompt) // 4)
    return max(1200, input_tokens + 900)


def build_token_budget_plan(
    prompt: str,
    agents: list[Agent],
    overhead_multiplier: float = 2.2,
    hard_cap: int = 12000,
) -> TokenBudgetPlan:
    estimate = estimate_single_agent_tokens(prompt)
    max_swarm_tokens = min(hard_cap, int(estimate * overhead_multiplier))
    max_parallel_agents = min(6, max(1, len(agents)))
    max_iterations = max(1, min(8, max_swarm_tokens // 1400))
    return TokenBudgetPlan(
        single_agent_estimate=estimate,
        max_swarm_tokens=max_swarm_tokens,
        max_iterations=max_iterations,
        max_parallel_agents=max_parallel_agents,
        reason=(
            "Bound swarm overhead so multi-agent work does not spend far more "
            "than a single-agent run unless explicitly configured higher."
        ),
    )


def should_stop_for_budget(total_tokens: int, plan: TokenBudgetPlan) -> bool:
    return total_tokens >= plan.max_swarm_tokens

"""SubAgentManager — delegates tasks to sub-agents with shared consciousness.

Sub-agents publish progress, artifacts, and completions to the parent
orchestrator's Consciousness hub. All running agents see live updates.
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING, Optional

from swarm.core.agent import Agent
from swarm.core.state import SharedState
from swarm.core.consciousness import Consciousness

if TYPE_CHECKING:
    from swarm.core.orchestrator import Orchestrator


class SubAgentResult:
    def __init__(self, agent_name: str, task: str, output: str, success: bool,
                 turns: int = 0, tokens: int = 0, duration_ms: int = 0):
        self.agent_name = agent_name
        self.task = task
        self.output = output
        self.success = success
        self.turns = turns
        self.tokens = tokens
        self.duration_ms = duration_ms

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "task": self.task,
            "output": self.output[:1000],
            "success": self.success,
            "turns": self.turns,
            "tokens": self.tokens,
            "duration_ms": self.duration_ms,
        }


class SubAgentManager:
    """Manages sub-agent delegation with shared consciousness.

    Sub-agents see a live view of the parent's Consciousness hub,
    broadcasting progress and receiving updates from other agents.
    """

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator
        self._results: dict[str, list[SubAgentResult]] = {}

    @property
    def consciousness(self) -> Consciousness:
        return self._orchestrator.consciousness

    async def spawn(self, agent_name: str, task: str, parent_state: SharedState,
                    max_iterations: int = 10, verbose: bool = False) -> SubAgentResult:
        if agent_name not in self._orchestrator.agents:
            return SubAgentResult(
                agent_name=agent_name,
                task=task,
                output=f"Agent '{agent_name}' not found",
                success=False,
            )

        start = time.monotonic()
        await self.consciousness.push_progress(
            agent_name, f"Sub-agent started", {"task": task[:100]}
        )

        try:
            child_state = SharedState(user_input=task)
            child_state.artifacts = dict(parent_state.artifacts)

            result_state = await self._orchestrator.run(
                user_input=task,
                entry_agent=agent_name,
                max_iterations=max_iterations,
                verbose=verbose,
                state=child_state,
            )

            final_text = ""
            for turn in result_state.agent_turns:
                if turn.output:
                    final_text = turn.output

            duration = int((time.monotonic() - start) * 1000)
            sub_result = SubAgentResult(
                agent_name=agent_name,
                task=task,
                output=final_text,
                success=True,
                turns=result_state.iteration,
                tokens=result_state.metadata.get("total_tokens", 0),
                duration_ms=duration,
            )

            relevant = result_state.get_artifact("relevant_info")
            if relevant:
                parent_state.set_artifact(f"sub_{agent_name}_{int(time.time())}", relevant)

            await self.consciousness.push_completion(
                agent_name, final_text,
                f"Completed in {duration}ms, {result_state.iteration} turns"
            )

            parent_state.artifacts.update(result_state.artifacts)

        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            sub_result = SubAgentResult(
                agent_name=agent_name,
                task=task,
                output=f"Sub-agent failed: {e}",
                success=False,
                duration_ms=duration,
            )
            await self.consciousness.push_error(agent_name, str(e))

        self._results.setdefault(agent_name, []).append(sub_result)
        return sub_result

    async def spawn_parallel(self, tasks: list[tuple[str, str]], parent_state: SharedState,
                             max_iterations: int = 10, verbose: bool = False) -> list[SubAgentResult]:
        """Spawn multiple sub-agents in parallel with shared consciousness.

        All spawned agents share the parent's Consciousness hub, so they
        see each other's progress in real-time.
        """
        await self.consciousness.push_progress(
            "sub_agent_manager", f"Spawning {len(tasks)} parallel sub-agents",
            {"agents": [t[0] for t in tasks]}
        )

        coros = [
            self.spawn(agent_name, task, parent_state, max_iterations, verbose)
            for agent_name, task in tasks
        ]
        results = await asyncio.gather(*coros)

        await self.consciousness.push_progress(
            "sub_agent_manager",
            f"All {len(tasks)} sub-agents completed",
            {"success": sum(1 for r in results if r.success)}
        )
        return results

    def get_results(self, agent_name: Optional[str] = None) -> list[SubAgentResult]:
        if agent_name:
            return self._results.get(agent_name, [])
        all_results = []
        for results in self._results.values():
            all_results.extend(results)
        return all_results

    def summary(self) -> str:
        lines = []
        for agent_name, results in self._results.items():
            successes = sum(1 for r in results if r.success)
            total = len(results)
            total_tokens = sum(r.tokens for r in results)
            lines.append(f"  {agent_name}: {successes}/{total} successful, {total_tokens} tokens")
        return "\n".join(lines) if lines else "  No sub-agents spawned"

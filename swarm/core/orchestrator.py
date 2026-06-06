"""Orchestrator — coordinates agents with shared consciousness, parallel execution,
model fallback with context preservation, and real-time state broadcasting."""

from __future__ import annotations
import asyncio
import json
import os
import time
from typing import Optional
from swarm.core.agent import Agent
from swarm.core.state import SharedState, AgentTurn
from swarm.core.handoff import build_handoff_tools, parse_handoff
from swarm.core.sub_agent import SubAgentManager
from swarm.core.consciousness import Consciousness
from swarm.core.messaging import MessageHub
from swarm.core.brainstorm import BrainstormEngine, estimate_complexity
from swarm.core.ab_testing import run_ab_test
from swarm.core.council import run_council_vote
from swarm.core.debug_collab import DebugCollaboration
from swarm.core.learning import LessonLearner
from swarm.core.master_review import build_integration_report, run_master_review
from swarm.core.preflight_review import review_agent_output
from swarm.core.provider_assignment import assign_hybrid_provider_models, summarize_hybrid_routes
from swarm.core.sub_agent_planner import build_sub_agent_plan
from swarm.core.switch_memory import SwitchMemory
from swarm.core.skill_runtime import create_temporary_skill_session, plan_required_skills
from swarm.core.token_budget import build_token_budget_plan, should_stop_for_budget
from swarm.core.environment_support import discover_environment_support
from swarm.tools.react_doctor_monitor import ReactDoctorMonitor
from swarm.config import SwarmConfig
from swarm.providers.base import Message
from swarm.providers.factory import ProviderFactory
from swarm.tools.registry import ToolRegistry
from swarm.safety.loop_detector import LoopDetector
from swarm.safety.timeout import TimeoutManager
from swarm.tools.base import Tool
from swarm.skills import SkillLoader
from swarm.switcher import SwitcherBridge
from swarm.core.agent import resolve_task_type


class Orchestrator:
    def __init__(
        self,
        config: Optional[SwarmConfig] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.config = config or SwarmConfig.auto_detect()
        self.tool_registry = tool_registry or ToolRegistry.create_default()
        self.agents: dict[str, Agent] = {}
        self.loop_detector = LoopDetector(
            threshold=self.config.loop_detection_threshold
        )
        timeout = getattr(self.config, 'agent_timeout_seconds', 60)
        if not isinstance(timeout, (int, float)):
            timeout = 60
        self.timeout_manager = TimeoutManager(default_timeout=timeout)
        self._sub_agent_manager: Optional[SubAgentManager] = None
        self._mcp_initialized = False
        self.skill_loader = SkillLoader()
        self._skill_discovered = False
        self.consciousness = Consciousness()
        self.message_hub = MessageHub(self.consciousness)
        self.switch_memory = SwitchMemory()
        self.brainstorm_engine = BrainstormEngine()
        self.debug_collab = DebugCollaboration()
        self.lesson_learner = LessonLearner()
        self.temp_skill_session = create_temporary_skill_session()
        self.switcher_bridge = SwitcherBridge(consciousness=self.consciousness)
        self.react_doctor = ReactDoctorMonitor(
            publish_fn=self.consciousness.push_diagnostic,
            interval=120,
        )
        self._react_doctor_task: Optional[asyncio.Task] = None

    def init_sub_agents(self):
        if self._sub_agent_manager is None:
            self._sub_agent_manager = SubAgentManager(self)
            mgr_ref = lambda: self._sub_agent_manager
            self.tool_registry.inject_sub_agent_tools(mgr_ref)
            self.tool_registry.inject_collaboration_refs(
                message_hub=self.message_hub,
                brainstorm_engine=self.brainstorm_engine,
                debug_collab=self.debug_collab,
                lesson_learner=self.lesson_learner,
            )

    @property
    def sub_agents(self) -> Optional[SubAgentManager]:
        return self._sub_agent_manager

    def register_agent(self, agent: Agent):
        self.agents[agent.name] = agent

    def register_agents(self, *agents: Agent):
        for agent in agents:
            self.register_agent(agent)

    async def _establish_agent_mesh(self, state: SharedState):
        roster = sorted(self.agents.keys())
        mesh = {
            "agents": roster,
            "mode": "direct+broadcast+shared_state+consciousness",
            "all_agents_can_message_each_other": True,
        }
        state.metadata["agent_communication_mesh"] = mesh
        self.message_hub.broadcast(
            "orchestrator",
            "Communication mesh online. All agents can use direct messages, broadcasts, shared artifacts, and consciousness updates.",
            msg_type="mesh_ready",
        )
        await self.consciousness.push_state(
            "agent_communication_mesh",
            mesh,
            "orchestrator",
        )

    def _resolve_model(self, agent: Agent, preference: str = "best") -> str:
        if agent.model:
            return agent.model
        if preference == "triage":
            return self.config.find_model("best")
        return self.config.find_model("cheap")

    def _get_model_chain(self, agent: Agent, preference: str) -> list[str]:
        task_type = resolve_task_type(agent)
        model_preference = getattr(agent, "model_preference", "auto")
        bridge_preference = (
            "best" if preference == "triage" else "cheap"
        )
        if model_preference in {"best", "cheap"}:
            bridge_preference = model_preference
        bridge_chain = self.switcher_bridge.get_model_chain_for_task(
            task_type,
            bridge_preference,
        )
        if bridge_chain:
            return bridge_chain[:12]

        bridge_chain = self.switcher_bridge.get_model_chain(
            bridge_preference
        )
        if bridge_chain:
            return bridge_chain[:12]

        chain = []

        if agent.model:
            chain.append(agent.model)

        if preference == "triage":
            chain.append(self.config.find_model("best"))
        else:
            chain.append(self.config.find_model("cheap"))

        cheap = self.config.find_model("cheap")
        best = self.config.find_model("best")
        for m in [cheap, best]:
            if m and m not in chain:
                chain.append(m)

        for cfg_name, pc in self.config._sorted_providers():
            if pc.models:
                for model_name in pc.models:
                    ref = f"{cfg_name}:{model_name}"
                    if ref not in chain:
                        chain.append(ref)

        return chain[:12]

    def _is_model_on_cooldown(self, model_ref: str) -> bool:
        return not self.switcher_bridge.is_healthy(model_ref)

    def _record_failure(self, model_ref: str, error: str = ""):
        self.switcher_bridge.record_failure(model_ref, error)

    def _prepare_messages(
        self,
        agent: Agent,
        user_input: str,
        state: SharedState,
    ) -> list[Message]:
        if not self._skill_discovered:
            self.skill_loader.discover()
            self._skill_discovered = True
        system_prompt = self.skill_loader.get_injected_prompt(agent, user_input)
        messages = [Message(role="system", content=system_prompt)]

        context = state.to_context_string()
        if context.strip():
            messages.append(Message(
                role="system",
                content=f"Shared Context:\n{context}",
            ))

        consciousness_summary = self.consciousness.to_context_string()
        if consciousness_summary.strip():
            messages.append(Message(
                role="system",
                content=f"Live Consciousness:\n{consciousness_summary}",
            ))

        messages_context = self.message_hub.get_conversation_summary(agent.name, limit=15)
        if messages_context.strip():
            messages.append(Message(
                role="system",
                content=messages_context,
            ))

        lessons = self.lesson_learner.get_lessons_for_prompt(agent.name, user_input)
        if lessons.strip():
            messages.append(Message(
                role="system",
                content=lessons,
            ))

        for turn in state.agent_turns[-10:]:
            messages.append(Message(
                role="user",
                content=turn.input,
            ))
            messages.append(Message(
                role="assistant",
                content=turn.output[:2000],
            ))

        messages.append(Message(role="user", content=user_input))
        return messages

    def _get_tools_for_agent(self, agent: Agent) -> list[Tool]:
        agent_tools = getattr(agent, "tools", [])
        return self.tool_registry.get_tools_for_agent(agent.name, agent_tools)

    async def _review_agent_turn(self, state: SharedState, agent: Agent, output: str):
        review = review_agent_output(agent.name, output, path=f"agents/{agent.name}.md")
        state.metadata.setdefault("preflight_reviews", []).append(review.to_dict())
        if review.comments:
            state.metadata.setdefault("pr_inline_comments", []).extend(
                [comment.to_dict() for comment in review.comments]
            )
            await self.consciousness.push_diagnostic(agent.name, review.summary, review.to_dict())
        return review

    async def _execute_tool_calls(
        self,
        tool_calls: list,
        agent: Agent,
    ) -> list[dict]:
        results = []
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args_raw = func.get("arguments", "{}")
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {}
            else:
                args = args_raw

            tool = self.tool_registry.get(name)
            if tool:
                result = await tool.execute(**args)
            else:
                result = f"Unknown tool: {name}"

            results.append({
                "tool_call_id": tc.get("id", ""),
                "output": str(result)[:3000],
            })
        return results

    async def _chat_with_fallback(
        self,
        messages: list,
        tools: Optional[list],
        temperature: float,
        max_tokens: int,
        model_chain: list[str],
        agent_name: str,
    ) -> tuple:
        errors = []
        for model_ref in model_chain:
            if self._is_model_on_cooldown(model_ref):
                continue

            if errors:
                messages_with_context = await self._inject_switch_context(
                    list(messages), model_ref, agent_name, errors[-1]
                )
            else:
                messages_with_context = messages

            chat_func = ProviderFactory.get_chat_func(self.config, model_ref)
            try:
                response = await self.timeout_manager.run_with_timeout(
                    chat_func(
                        messages=messages_with_context,
                        tools=tools if tools else None,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                )
                self.switcher_bridge.record_success(model_ref)
                await self.consciousness.push_progress(
                    agent_name, f"Switched to {model_ref}", {"status": "ok"}
                )
                return response, model_ref
            except Exception as e:
                estr = str(e)
                status = ""
                if "429" in estr or "rate_limit" in estr.lower():
                    status = "429"
                elif "404" in estr:
                    status = "404"
                elif "400" in estr:
                    status = "400"
                elif "401" in estr or "403" in estr:
                    status = "auth"
                self._record_failure(model_ref, estr)
                errors.append((model_ref, status, str(e)[:100]))

        auto_switched = self.switcher_bridge.switch_if_needed(
            model_chain[0] if model_chain else "",
            f"all models failed: {errors[0][2] if errors else 'unknown'}"
        )
        if auto_switched:
            refreshed = self.switcher_bridge.get_model_chain("best")
            if refreshed:
                return await self._chat_with_fallback(
                    messages, tools, temperature, max_tokens,
                    refreshed, agent_name,
                )

        raise RuntimeError(
            f"All models exhausted for {agent_name}. Errors: "
            + "; ".join(f"{m}[{s}]" for m, s, _ in errors)
        )

    async def _inject_switch_context(
        self,
        messages: list[Message],
        new_model_ref: str,
        agent_name: str,
        last_error: tuple,
    ) -> list[Message]:
        """Inject context summary into messages when switching models.

        This prevents the replacement model from hallucinating by telling it
        exactly what happened before and what it should continue working on.
        """
        original_task = ""
        for m in messages:
            if m.role == "user" and len(getattr(m, "content", "")) > 10:
                original_task = getattr(m, "content", "")

        context = self.consciousness.get_full_context_for_switch(original_task)
        switch_memory = self.switch_memory.build_message(agent_name, new_model_ref, context)

        prev_model, status, err_msg = last_error
        switch_notice = (
            f"[MODEL SWITCH] Previous model ({prev_model}) failed ({status}: {err_msg}).\n"
            f"Switched to {new_model_ref}. Read the switch memory below carefully.\n"
            f"Continue the task from where it left off — do NOT restart."
        )

        context_msg = Message(
            role="system",
            content=f"{switch_notice}\n\n{switch_memory}",
        )

        result = []
        inserted = False
        for m in messages:
            if m.role == "user" and not inserted:
                result.append(context_msg)
                inserted = True
            result.append(m)

        if not inserted:
            result.append(context_msg)

        return result

    async def run_parallel(
        self,
        tasks: list[tuple[str, str]],
        state: SharedState,
        max_iterations: int = 6,
        verbose: bool = True,
    ) -> list[tuple[str, str, bool]]:
        """Run multiple agents in parallel with shared consciousness.

        Each agent sees live updates from all others via the Consciousness hub.
        Supports hybrid API + local model routing per task type.

        Args:
            tasks: List of (agent_name, task_description) tuples.
            state: SharedState for context propagation.
            max_iterations: Max iterations per sub-agent.
            verbose: Log progress.

        Returns: List of (agent_name, final_output, success) tuples.
        """
        self.init_sub_agents()

        if verbose:
            await self.consciousness.push_progress(
                "orchestrator", f"Starting {len(tasks)} parallel agents",
                {"tasks": [t[0] for t in tasks]}
            )

        async def run_one(agent_name: str, task: str) -> tuple[str, str, bool]:
            agent = self.agents.get(agent_name)
            if not agent:
                await self.consciousness.push_error(agent_name, f"Agent not found")
                return agent_name, f"Agent '{agent_name}' not found", False

            await self.consciousness.push_progress(
                agent_name, f"Starting task", {"task": task[:100]}
            )

            task_type = resolve_task_type(agent)
            model_chain = self.switcher_bridge.get_model_chain_for_task(task_type, "best")
            if not model_chain:
                model_chain = self._get_model_chain(agent, "worker")

            messages = self._prepare_messages(agent, task, state)
            tools = self._get_tools_for_agent(agent)

            if verbose:
                self._log(f"[parallel] {agent_name} (task: {task_type}, chain: {len(model_chain)} models)")

            try:
                response, model_ref = await self._chat_with_fallback(
                    messages=messages,
                    tools=tools if tools else None,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    model_chain=model_chain,
                    agent_name=agent.name,
                )
                output = response.content or ""

                turn = AgentTurn(
                    agent_name=agent.name,
                    input=task,
                    output=output,
                    model=model_ref,
                    tokens_used=response.usage.get("total_tokens", 0),
                    duration_ms=0,
                )
                state.add_turn(turn)
                await self._review_agent_turn(state, agent, output)

                await self.consciousness.push_completion(
                    agent_name, output, f"Completed via {model_ref}"
                )
                if verbose:
                    self._log(f"  -> {agent_name} done via {model_ref}")
                return agent_name, output, True

            except RuntimeError as e:
                await self.consciousness.push_error(agent_name, str(e))
                if verbose:
                    self._log(f"  -> {agent_name} FAILED: {e}")
                return agent_name, f"[ALL MODELS FAILED] {e}", False

        task_map = {asyncio.ensure_future(run_one(agent_name, task)): agent_name
                    for agent_name, task in tasks}

        results = []
        pending = set(task_map.keys())
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for fut in done:
                agent_name = task_map[fut]
                if fut.exception():
                    results.append((agent_name, f"Unexpected error: {fut.exception()}", False))
                else:
                    result = fut.result()
                    results.append(result)
                    _, _, success = result
                    await self.consciousness.push_progress(
                        "orchestrator", f"{agent_name} completed",
                        {"success": success}
                    )

        return results

    async def run(
        self,
        user_input: str,
        entry_agent: Optional[str] = None,
        max_iterations: Optional[int] = None,
        verbose: bool = True,
        state: Optional[SharedState] = None,
        council: bool = True,
    ) -> SharedState:
        if not self.agents:
            raise ValueError("No agents registered. Call register_agent() first.")

        state = state or SharedState(user_input=user_input)
        if not state.user_input:
            state.user_input = user_input

        await self.consciousness.push_state("user_input", user_input, "orchestrator")
        await self._establish_agent_mesh(state)
        token_budget = build_token_budget_plan(user_input, list(self.agents.values()))
        state.metadata["token_budget"] = token_budget.to_dict()
        await self.consciousness.push_state(
            "token_budget",
            token_budget.to_dict(),
            "orchestrator",
        )
        ai_selection = assign_hybrid_provider_models(list(self.agents.values()), self.config, include_sub_agents=True)
        ai_selection_data = [assignment.to_dict() for assignment in ai_selection]
        state.metadata["ai_selection"] = {
            "assignments": ai_selection_data,
            "route_summary": summarize_hybrid_routes(ai_selection),
        }
        state.set_artifact("ai_selection", state.metadata["ai_selection"])
        await self.consciousness.push_state(
            "ai_selection",
            state.metadata["ai_selection"],
            "orchestrator",
        )
        state.metadata["environment_support"] = discover_environment_support()
        state.set_artifact("environment_support", state.metadata["environment_support"])
        skill_plan = plan_required_skills(user_input, existing_skills=[])
        state.metadata["skill_plan"] = skill_plan
        state.set_artifact("skill_plan", skill_plan)
        for skill_name in skill_plan["required"]:
            self.temp_skill_session.install_manifest(skill_name)
        await self.consciousness.push_state("skill_plan", skill_plan, "orchestrator")

        if council:
            council_agents = list(self.agents.values())
            decision = run_council_vote(
                user_input,
                council_agents,
                quorum=min(6, len(council_agents)),
            )
            decision_data = decision.to_dict()
            state.metadata["council_decision"] = decision_data
            state.set_artifact("council_decision", decision_data)
            await self.consciousness.push_progress(
                "council_master",
                decision.summary,
                {
                    "verdict": decision.verdict,
                    "confidence": decision.confidence,
                    "vote": decision.vote_line,
                },
            )
            if verbose:
                self._log(
                    f"Council complete | vote {decision.vote_line} | "
                    f"verdict {decision.verdict} | confidence {decision.confidence}%"
                )
            if decision.verdict == "reject":
                state.summary = decision.summary
                state.metadata["total_iterations"] = state.iteration
                state.metadata["total_tokens"] = 0
                state.metadata["total_duration_ms"] = 0
                state.metadata["temporary_skill_cleanup"] = self.temp_skill_session.cleanup()
                return state

        ab_agents = list(self.agents.values())[: min(8, len(self.agents))]
        ab_result = run_ab_test(user_input, ab_agents)
        state.metadata["ab_test"] = ab_result.to_dict()
        state.set_artifact("ab_test", ab_result.to_dict())
        await self.consciousness.push_progress(
            "council_master",
            ab_result.summary,
            ab_result.to_dict(),
        )

        complexity = estimate_complexity(user_input)
        if complexity >= self.brainstorm_engine.complexity_threshold:
            session = self.brainstorm_engine.create_session(user_input)
            await self.consciousness.push_progress(
                "orchestrator",
                f"Complexity detected (score={complexity}). Brainstorm session {session.id} created. "
                f"Agents can contribute via initiate_brainstorm/contribute_idea tools.",
                {"session_id": session.id, "complexity": complexity}
            )
            if verbose:
                self._log(f"COMPLEX TASK (score={complexity}) — brainstorm session {session.id} opened")

        max_iter = min(max_iterations or self.config.max_iterations, token_budget.max_iterations)
        current_agent_name = entry_agent or self._select_entry_agent(user_input)
        state.current_agent = current_agent_name
        entry_agent_obj = self.agents.get(current_agent_name)
        if entry_agent_obj:
            sub_plan = build_sub_agent_plan(entry_agent_obj, user_input, self.agents)
            state.metadata["sub_agent_plan"] = sub_plan
            state.set_artifact("sub_agent_plan", sub_plan)
            if sub_plan:
                await self.consciousness.push_progress(
                    current_agent_name,
                    f"Sub-agent helpers available: {', '.join(item['sub_agent'] for item in sub_plan)}",
                    {"sub_agent_plan": sub_plan},
                )

        if verbose:
            await self.consciousness.push_state("entry_agent", current_agent_name, "orchestrator")
            self._log(f"Swarm started | Input: {user_input[:100]}...")
            self._log(f"Entry agent: {current_agent_name}")
            self._log(f"Available agents: {list(self.agents.keys())}")

        self.init_sub_agents()

        if self._react_doctor_task is None or self._react_doctor_task.done():
            self.react_doctor.add_watch_dir(os.getcwd())
            self._react_doctor_task = asyncio.create_task(self.react_doctor.run())
            if verbose:
                self._log("React Doctor monitor started (background, 120s interval)")

        consecutive_failures = 0

        for iteration in range(max_iter):
            agent = self.agents.get(current_agent_name)
            if not agent:
                self._log(f"Agent '{current_agent_name}' not found, stopping.")
                break

            await self.consciousness.push_progress(
                current_agent_name, f"Iteration {iteration + 1}/{max_iter}",
                {"iteration": iteration}
            )

            model_chain = self._get_model_chain(
                agent,
                "triage" if iteration == 0 else "worker",
            )
            messages = self._prepare_messages(agent, user_input, state)
            tools = self._get_tools_for_agent(agent)
            handoff_tools = build_handoff_tools(self.agents, current_agent_name)
            all_tool_defs = tools + [
                t if isinstance(t, dict) else t.to_openai_format()
                for t in handoff_tools
            ]

            if verbose:
                self._log(f"[{iteration + 1}/{max_iter}] {agent.name}")

            start_time = time.monotonic()

            try:
                response, model_ref = await self._chat_with_fallback(
                    messages=messages,
                    tools=all_tool_defs if all_tool_defs else None,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    model_chain=model_chain,
                    agent_name=agent.name,
                )
                consecutive_failures = 0
            except RuntimeError as e:
                await self.consciousness.push_error(agent.name, str(e))
                self._log(f"ALL MODELS FAILED: {e}")
                turn = AgentTurn(
                    agent_name=agent.name,
                    input=user_input,
                    output=f"[ALL MODELS FAILED] {e}",
                    model="unknown",
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
                state.add_turn(turn)
                await self._review_agent_turn(state, agent, turn.output)
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    self._log("Two consecutive agent failures. Aborting.")
                    break
                continue

            duration = int((time.monotonic() - start_time) * 1000)
            tool_calls = response.tool_calls or []

            agent_output = response.content or "[No text response, processing tool calls...]"

            if verbose and model_ref:
                self._log(f"  model: {model_ref}")

            turn = AgentTurn(
                agent_name=agent.name,
                input=user_input,
                output=agent_output,
                model=model_ref,
                tokens_used=response.usage.get("total_tokens", 0),
                duration_ms=duration,
                tool_calls=tool_calls,
            )
            state.add_turn(turn)
            await self._review_agent_turn(state, agent, agent_output)
            running_tokens = sum(t.tokens_used for t in state.agent_turns)
            if should_stop_for_budget(running_tokens, token_budget):
                state.metadata["budget_stopped"] = True
                await self.consciousness.push_progress(
                    "orchestrator",
                    "Token budget reached; stopping additional agent turns.",
                    {"used": running_tokens, "budget": token_budget.max_swarm_tokens},
                )
                break

            if verbose and tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {}).get("name", "unknown")
                    self._log(f"  -> tool call: {fn}")

            await self.consciousness.push_state(
                f"agent:{agent.name}:last_output",
                agent_output[:200],
                agent.name
            )

            if not tool_calls:
                if verbose:
                    self._log(f"  -> {agent.name} finished")
                if current_agent_name == state.current_agent:
                    break
                continue

            if self.loop_detector.is_looping():
                self._log(f"LOOP DETECTED: {self.loop_detector.summary()}")
                state.metadata["loop_detected"] = True
                await self.consciousness.push_error(agent.name, f"Loop detected: {self.loop_detector.summary()}")
                break

            tool_results = await self._execute_tool_calls(tool_calls, agent)

            handoff = parse_handoff(tool_calls, self.agents)
            if handoff:
                next_agent, context = handoff
                if next_agent and next_agent in self.agents:
                    if verbose:
                        self._log(f"  -> handoff: {current_agent_name} -> {next_agent}")
                    self.loop_detector.record_handoff(current_agent_name, next_agent)
                    await self.consciousness.push_progress(
                        current_agent_name, f"Handoff to {next_agent}: {context[:100]}"
                    )
                    state.summary = context
                    current_agent_name = next_agent
                    state.current_agent = next_agent
                    user_input = context
                    continue

            for result in tool_results:
                messages.append(Message(
                    role="tool",
                    content=result["output"],
                    tool_call_id=result["tool_call_id"],
                ))

            model_chain_followup = self._get_model_chain(agent, "worker")
            try:
                followup, _ = await self._chat_with_fallback(
                    messages=messages,
                    tools=None,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    model_chain=model_chain_followup,
                    agent_name=agent.name,
                )
                if followup.content:
                    turn.output += f"\n{followup.content}"
            except RuntimeError:
                pass

        state.metadata["total_iterations"] = state.iteration
        state.metadata["total_tokens"] = sum(
            t.tokens_used for t in state.agent_turns
        )
        state.metadata["total_duration_ms"] = sum(
            t.duration_ms for t in state.agent_turns
        )
        state.metadata["switch_memory"] = self.switch_memory.to_dict()
        state.set_artifact("preflight_reviews", state.metadata.get("preflight_reviews", []))
        state.set_artifact("pr_inline_comments", state.metadata.get("pr_inline_comments", []))
        integration_report = build_integration_report(state)
        state.set_artifact("integration_report", integration_report.to_dict())
        await self.consciousness.push_artifact(
            "integration_report",
            integration_report.to_dict(),
            "master",
        )
        master_review = run_master_review(state)
        state.set_artifact("master_review", master_review.to_dict())
        state.metadata["master_review"] = master_review.to_dict()
        await self.consciousness.push_completion(
            "master",
            master_review.summary,
            master_review.summary,
        )
        self.lesson_learner.log_lesson(
            "*",
            user_input,
            master_review.status,
            (
                f"Run completed with {state.iteration} turns, "
                f"{state.metadata['total_tokens']} tokens, master status {master_review.status}."
            ),
            tags=["auto", "run-summary", master_review.status],
            success=master_review.status == "pass",
        )
        state.metadata["learning_stats"] = self.lesson_learner.get_stats()
        state.metadata["temporary_skill_cleanup"] = self.temp_skill_session.cleanup()

        if verbose:
            total_tokens = state.metadata["total_tokens"]
            total_time = state.metadata["total_duration_ms"]
            self._log(f"Swarm complete | {state.iteration} turns | {total_tokens} tokens | {total_time}ms")
            self._log(master_review.summary)
            self._log(f"Handoff trace: {self.loop_detector.summary()}")

        return state

    def _select_entry_agent(self, user_input: str) -> str:
        if "triage" in self.agents:
            return "triage"
        return list(self.agents.keys())[0]

    def _log(self, msg: str):
        print(f"[swarm] {msg}")

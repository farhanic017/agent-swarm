"""Context management — conversation compression, consciousness summaries,
and model-switch context injection for preventing hallucinations."""

import json
from typing import Optional
from swarm.core.state import SharedState
from swarm.core.consciousness import Consciousness


def compress_conversation(state: SharedState, max_turns: int = 10) -> str:
    recent = state.agent_turns[-max_turns:]
    lines = [f"Task: {state.user_input}"]
    if state.summary:
        lines.append(f"Progress: {state.summary}")
    if state.artifacts:
        lines.append(f"Artifacts: {json.dumps(state.artifacts, indent=2)}")
    for t in recent:
        lines.append(f"[{t.agent_name}] In: {t.input[:200]}")
        lines.append(f"[{t.agent_name}] Out: {t.output[:300]}")
    return "\n".join(lines)


def summarize_turn(turn) -> str:
    return f"{turn.agent_name} ({turn.duration_ms}ms, {turn.tokens_used}tok): {turn.output[:200]}"


def generate_switch_context(
    original_task: str,
    consciousness: Optional[Consciousness] = None,
    state: Optional[SharedState] = None,
    max_events: int = 50,
) -> str:
    """Generate a full context summary for injection on model switch.

    Combines data from Consciousness (events, live state, artifacts) and
    SharedState (turn history) to produce a complete picture that prevents
    the replacement model from hallucinating.

    The replacement model gets:
      1. Original task
      2. What's been done so far
      3. Artifacts produced
      4. Errors encountered
      5. Current state
      6. Clear instruction to continue, not restart
    """
    parts = [f"## Original Task\n{original_task}"]

    if state:
        if state.summary:
            parts.append(f"## Progress Summary\n{state.summary}")
        if state.agent_turns:
            turns = state.agent_turns[-10:]
            turn_lines = []
            for t in turns:
                turn_lines.append(f"[{t.agent_name}] (model: {t.model}, {t.tokens_used}tok) {t.output[:200]}")
            parts.append("## Recent Turns\n" + "\n".join(turn_lines))
        if state.artifacts:
            art_lines = []
            for k, v in list(state.artifacts.items())[:15]:
                if isinstance(v, str) and len(v) > 300:
                    v = v[:300] + "..."
                art_lines.append(f"  {k}: {v}")
            parts.append("## Artifacts\n" + "\n".join(art_lines))

    if consciousness:
        consciousness_context = consciousness.get_full_context_for_switch(original_task, max_events)
        parts.append(consciousness_context)

    parts.append("## Direction")
    parts.append("Continue where the previous model left off. Build on existing progress.")
    parts.append("Do NOT restart from scratch. Use the artifacts and state above.")

    return "\n\n".join(parts)


def build_agent_context_prompt(
    agent_name: str,
    task: str,
    state: SharedState,
    consciousness: Optional[Consciousness] = None,
) -> str:
    """Build a system-level context prompt for an agent.

    Includes shared context, consciousness state, and any relevant artifacts.
    """
    lines = [f"Task: {task}"]

    if state.summary:
        lines.append(f"Progress: {state.summary}")

    if state.artifacts:
        art = json.dumps(dict(list(state.artifacts.items())[:10]), indent=2)
        lines.append(f"Shared Artifacts:\n{art}")

    if consciousness:
        ctxt = consciousness.to_context_string()
        if ctxt:
            lines.append(f"Live State:\n{ctxt}")

    recent = state.agent_turns[-5:]
    if recent:
        turn_lines = []
        for t in recent:
            turn_lines.append(f"[{t.agent_name}] {t.output[:150]}")
        lines.append("Recent Activity:\n" + "\n".join(turn_lines))

    return "\n".join(lines)

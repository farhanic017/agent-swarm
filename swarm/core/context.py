"""Context management — conversation compression, consciousness summaries,
and model-switch context injection for preventing hallucinations."""

import json
import re
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


def build_compaction_summary(
    state: SharedState,
    project_tree: str = "",
    pending: list[str] | None = None,
    max_turns: int = 12,
) -> dict:
    """Build a /compact style summary that preserves current state over chat history."""
    recent = state.agent_turns[-max_turns:]
    completed = []
    decisions = []
    risks = []
    files = set()

    for turn in state.agent_turns:
        text = f"{turn.input}\n{turn.output}"
        for match in re.finditer(r"[\w./\\-]+\.(tsx|jsx|yaml|json|html|css|yml|py|js|ts|md)", text):
            files.add(match.group(0).replace("\\", "/"))
        lower = text.lower()
        if any(token in lower for token in ("done", "passed", "implemented", "fixed", "created")):
            completed.append(f"{turn.agent_name}: {turn.output[:180]}")
        if any(token in lower for token in ("decided", "use ", "selected", "approved", "verdict")):
            decisions.append(f"{turn.agent_name}: {turn.output[:180]}")
        if any(token in lower for token in ("risk", "blocked", "failed", "warning", "security")):
            risks.append(f"{turn.agent_name}: {turn.output[:180]}")

    artifacts = dict(list(state.artifacts.items())[:20])
    summary = {
        "command": "/compact",
        "purpose": "Preserve architecture, decisions, progress, pending work, and risks while dropping conversational noise.",
        "project": {
            "goal": state.user_input,
            "architecture": _summarize_project_tree(project_tree),
            "important_files": sorted(files)[:40],
        },
        "completed": completed[-12:],
        "pending": pending or _infer_pending_work(state),
        "important_decisions": decisions[-12:],
        "risks_and_debug_notes": risks[-12:],
        "artifacts": artifacts,
        "recent_turns": [summarize_turn(turn) for turn in recent],
        "next_agent_instruction": (
            "Do not reread the entire codebase unless the task requires it. Start from this summary, "
            "inspect only the touched or relevant files, then update the summary after verified work."
        ),
    }
    return summary


def format_compaction_summary(summary: dict) -> str:
    lines = [
        "# Compact Context Summary",
        "",
        f"Command: {summary.get('command', '/compact')}",
        f"Goal: {summary.get('project', {}).get('goal', '')}",
        "",
        "## Architecture",
        summary.get("project", {}).get("architecture", ""),
        "",
        "## Completed",
    ]
    lines.extend(f"- {item}" for item in summary.get("completed", []))
    lines.extend(["", "## Pending"])
    lines.extend(f"- {item}" for item in summary.get("pending", []))
    lines.extend(["", "## Important Decisions"])
    lines.extend(f"- {item}" for item in summary.get("important_decisions", []))
    lines.extend(["", "## Risks And Debug Notes"])
    lines.extend(f"- {item}" for item in summary.get("risks_and_debug_notes", []))
    lines.extend(["", "## Next Agent Instruction", summary.get("next_agent_instruction", "")])
    return "\n".join(lines)


def _summarize_project_tree(project_tree: str) -> str:
    if not project_tree.strip():
        return "Architecture summary not supplied yet; first agent should inspect top-level files once."
    lines = [line.strip() for line in project_tree.splitlines() if line.strip()]
    return "\n".join(lines[:80])


def _infer_pending_work(state: SharedState) -> list[str]:
    if state.metadata.get("pending"):
        return list(state.metadata["pending"])
    if state.artifacts.get("master_review"):
        review = state.artifacts["master_review"]
        if isinstance(review, dict) and review.get("risks"):
            return [f"Resolve master review risk: {risk}" for risk in review["risks"]]
    return ["Continue from the latest verified state and run focused tests for the next change."]


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

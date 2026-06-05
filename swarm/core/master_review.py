from __future__ import annotations

from dataclasses import dataclass, field

from swarm.core.state import SharedState


@dataclass(frozen=True)
class IntegrationReport:
    connected_parts: tuple[str, ...]
    missing_parts: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict:
        return {
            "connected_parts": list(self.connected_parts),
            "missing_parts": list(self.missing_parts),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class MasterReview:
    status: str
    confidence: int
    checks: dict = field(default_factory=dict)
    risks: tuple[str, ...] = ()
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "checks": self.checks,
            "risks": list(self.risks),
            "summary": self.summary,
        }


def build_integration_report(state: SharedState) -> IntegrationReport:
    parts = []
    if state.get_artifact("council_decision"):
        parts.append("council_decision")
    if state.get_artifact("sub_agent_plan"):
        parts.append("sub_agent_plan")
    if state.get_artifact("ab_test"):
        parts.append("ab_test")
    if state.get_artifact("ai_selection"):
        parts.append("ai_selection")
    if state.agent_turns:
        parts.append("agent_outputs")
    if state.artifacts:
        parts.append("shared_artifacts")

    missing = []
    if not state.get_artifact("council_decision"):
        missing.append("council_decision")
    if not state.agent_turns:
        missing.append("agent_outputs")

    summary = (
        "Connected project parts: " + ", ".join(parts)
        if parts
        else "No project parts were produced to connect."
    )
    return IntegrationReport(
        connected_parts=tuple(parts),
        missing_parts=tuple(missing),
        summary=summary,
    )


def run_master_review(state: SharedState) -> MasterReview:
    council = state.get_artifact("council_decision") or {}
    integration = state.get_artifact("integration_report") or {}
    errors = [
        turn.output
        for turn in state.agent_turns
        if isinstance(turn.output, str) and turn.output.startswith("[ALL MODELS FAILED]")
    ]
    checks = {
        "council_completed": bool(council),
        "council_proceeded": council.get("verdict") in (None, "proceed"),
        "parts_connected": bool(integration.get("connected_parts")),
        "no_model_failures": not errors,
        "loop_free": not state.metadata.get("loop_detected", False),
    }
    risks = []
    if errors:
        risks.append(f"{len(errors)} model failure turn(s) need attention")
    if integration.get("missing_parts"):
        risks.append("missing parts: " + ", ".join(integration["missing_parts"]))
    if state.metadata.get("loop_detected"):
        risks.append("handoff loop was detected")

    passed = sum(1 for ok in checks.values() if ok)
    confidence = int(round((passed / max(1, len(checks))) * 100))
    status = "pass" if all(checks.values()) else "needs_attention"
    summary = (
        f"Master review {status}. {passed}/{len(checks)} checks passed. "
        f"Confidence: {confidence}%."
    )
    return MasterReview(
        status=status,
        confidence=confidence,
        checks=checks,
        risks=tuple(risks),
        summary=summary,
    )

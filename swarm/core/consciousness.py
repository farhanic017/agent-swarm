"""Shared Consciousness — real-time state broadcasting across all agents.

Provides a pub/sub event hub where agents broadcast progress, state changes,
artifacts, and diagnostics. Every agent sees a live, unified view of what's
happening. Supports context summary generation for smooth model fallback.
"""

from __future__ import annotations
import asyncio
import inspect
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ConsciousnessEvent:
    """An event broadcast to all subscribing agents."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: str = ""  # state_change, progress, artifact, error, diagnostic, handoff, completion
    source: str = ""  # agent name
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class Consciousness:
    """Central pub/sub hub for real-time agent consciousness.

    Features:
      - Publish/subscribe event system
      - Live shared state visible to all agents
      - Event log for context summary generation
      - Async-safe broadcasting
    """

    def __init__(self):
        self._live_state: dict[str, Any] = {}
        self._artifacts: dict[str, Any] = {}
        self._event_log: list[ConsciousnessEvent] = []
        self._subscriptions: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()
        self._max_event_log: int = 5000

    # ── Pub/Sub ──────────────────────────────────────────────────────

    def subscribe(self, event_type: str, callback: Callable[[ConsciousnessEvent], None]) -> str:
        """Subscribe to events of a given type. Returns subscription ID.

        event_type can be:
          - A specific type: "state_change", "progress", "artifact", "error", "diagnostic"
          - "*" for all events
        """
        sid = uuid.uuid4().hex[:12]
        self._subscriptions.setdefault(event_type, []).append({"id": sid, "callback": callback})
        return sid

    def unsubscribe(self, subscription_id: str) -> bool:
        for event_type, subs in self._subscriptions.items():
            for i, sub in enumerate(subs):
                if sub["id"] == subscription_id:
                    subs.pop(i)
                    if not subs:
                        del self._subscriptions[event_type]
                    return True
        return False

    async def publish(self, event: ConsciousnessEvent) -> int:
        """Publish an event to all matching subscribers. Returns fan-out count."""
        async with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > self._max_event_log:
                self._event_log = self._event_log[-self._max_event_log:]

            if event.type == "state_change" and "key" in event.payload:
                self._live_state[event.payload["key"]] = event.payload.get("value")
            if event.type == "artifact" and "key" in event.payload:
                self._artifacts[event.payload["key"]] = event.payload.get("value")

            count = 0
            target_types = ["*", event.type]
            for tt in target_types:
                for sub in self._subscriptions.get(tt, []):
                    cb = sub["callback"]
                    try:
                        if inspect.iscoroutinefunction(cb):
                            asyncio.ensure_future(cb(event))
                        else:
                            cb(event)
                        count += 1
                    except Exception:
                        pass
            return count

    # ── Live State ───────────────────────────────────────────────────

    async def push_state(self, key: str, value: Any, source: str = "system") -> ConsciousnessEvent:
        """Update live state and broadcast the change."""
        event = ConsciousnessEvent(
            type="state_change",
            source=source,
            payload={"key": key, "value": value},
        )
        await self.publish(event)
        return event

    async def push_progress(self, source: str, message: str, detail: dict = None) -> ConsciousnessEvent:
        """Broadcast a progress update from an agent."""
        event = ConsciousnessEvent(
            type="progress",
            source=source,
            payload={"message": message, "detail": detail or {}},
        )
        await self.publish(event)
        return event

    async def push_artifact(self, key: str, value: Any, source: str = "system") -> ConsciousnessEvent:
        """Store and broadcast a new artifact."""
        event = ConsciousnessEvent(
            type="artifact",
            source=source,
            payload={"key": key, "value": value},
        )
        await self.publish(event)
        return event

    async def push_error(self, source: str, error: str, detail: dict = None) -> ConsciousnessEvent:
        """Broadcast an error from an agent or subsystem."""
        event = ConsciousnessEvent(
            type="error",
            source=source,
            payload={"error": error, "detail": detail or {}},
        )
        await self.publish(event)
        return event

    async def push_diagnostic(self, source: str, severity: str, message: str, detail: dict = None) -> ConsciousnessEvent:
        """Broadcast a diagnostic (e.g. from React Doctor)."""
        event = ConsciousnessEvent(
            type="diagnostic",
            source=source,
            payload={"severity": severity, "message": message, "detail": detail or {}},
        )
        await self.publish(event)
        return event

    async def push_completion(self, source: str, result: str, summary: str = "") -> ConsciousnessEvent:
        """Broadcast an agent's task completion."""
        event = ConsciousnessEvent(
            type="completion",
            source=source,
            payload={"result": result[:2000], "summary": summary},
        )
        await self.publish(event)
        return event

    def get_state(self, key: str, default=None) -> Any:
        return self._live_state.get(key, default)

    def get_all_state(self) -> dict:
        return dict(self._live_state)

    def get_artifact(self, key: str, default=None) -> Any:
        return self._artifacts.get(key, default)

    def get_all_artifacts(self) -> dict:
        return dict(self._artifacts)

    # ── Event Log ────────────────────────────────────────────────────

    def get_events(self, event_type: str = "", source: str = "", limit: int = 100) -> list[dict]:
        filtered = self._event_log
        if event_type:
            filtered = [e for e in filtered if e.type == event_type]
        if source:
            filtered = [e for e in filtered if e.source == source]
        return [e.to_dict() for e in filtered[-limit:]]

    def get_recent_summary(self, max_events: int = 20) -> str:
        """Generate a concise summary of recent events for context injection."""
        recent = self._event_log[-max_events:]
        if not recent:
            return ""

        lines = ["=== Shared Consciousness Context ==="]
        agents_seen = set()
        for e in recent:
            agents_seen.add(e.source)
            if e.type == "progress":
                lines.append(f"[{e.source}] Progress: {e.payload.get('message', '')}")
            elif e.type == "completion":
                lines.append(f"[{e.source}] Completed: {e.payload.get('summary', e.payload.get('result', '')[:200])}")
            elif e.type == "artifact":
                val = e.payload.get("value", "")
                if isinstance(val, str) and len(val) > 100:
                    val = val[:100] + "..."
                lines.append(f"[{e.source}] Artifact: {e.payload.get('key', '')} = {val}")
            elif e.type == "error":
                lines.append(f"[{e.source}] Error: {e.payload.get('error', '')[:200]}")
            elif e.type == "diagnostic":
                lines.append(f"[{e.source}] Diagnostic ({e.payload.get('severity', 'info')}): {e.payload.get('message', '')[:200]}")

        if self._live_state:
            lines.append("Live State:")
            for k, v in list(self._live_state.items())[:10]:
                lines.append(f"  {k}: {str(v)[:100]}")

        lines.append(f"Active agents: {', '.join(sorted(agents_seen))}")
        return "\n".join(lines)

    def get_full_context_for_switch(self, original_task: str, max_events: int = 50) -> str:
        """Generate a full context summary for injection on model switch.

        This is specifically designed for the fallback/switch path — it tells
        the replacement model everything that happened so it doesn't hallucinate.
        """
        recent = self._event_log[-max_events:]

        parts = [f"## Original Task\n{original_task}"]

        if self._artifacts:
            parts.append("## Artifacts Produced So Far")
            for k, v in list(self._artifacts.items())[:15]:
                if isinstance(v, str) and len(v) > 300:
                    v = v[:300] + "..."
                parts.append(f"  {k}: {v}")

        progress_events = [e for e in recent if e.type in ("progress", "completion")]
        if progress_events:
            parts.append("## Progress")
            for e in progress_events[-10:]:
                msg = e.payload.get("message") or e.payload.get("summary") or ""
                parts.append(f"  [{e.source}] {msg}")

        errors = [e for e in recent if e.type == "error"]
        if errors:
            parts.append("## Errors Encountered")
            for e in errors[-5:]:
                parts.append(f"  [{e.source}] {e.payload.get('error', '')[:200]}")

        state_events = [e for e in recent if e.type == "state_change"]
        if state_events:
            parts.append("## State Changes")
            for e in state_events[-5:]:
                parts.append(f"  [{e.source}] {e.payload.get('key', '')} = {str(e.payload.get('value', ''))[:100]}")

        if self._live_state:
            parts.append("## Current State")
            for k, v in list(self._live_state.items())[:10]:
                parts.append(f"  {k}: {str(v)[:100]}")

        parts.append("## Your Task")
        parts.append("Continue where the previous model left off. Use the artifacts and state above.")
        parts.append("Do NOT restart — build on existing progress.")

        return "\n\n".join(parts)

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "live_state": dict(self._live_state),
            "artifacts": dict(self._artifacts),
            "event_log": [e.to_dict() for e in self._event_log[-200:]],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Consciousness:
        c = cls()
        c._live_state = dict(data.get("live_state", {}))
        c._artifacts = dict(data.get("artifacts", {}))
        for e_data in data.get("event_log", []):
            c._event_log.append(ConsciousnessEvent(
                id=e_data.get("id", ""),
                type=e_data.get("type", ""),
                source=e_data.get("source", ""),
                payload=e_data.get("payload", {}),
                timestamp=e_data.get("timestamp", 0),
            ))
        return c

    def to_context_string(self) -> str:
        """Short context string for agent system prompts."""
        return self.get_recent_summary(max_events=15)

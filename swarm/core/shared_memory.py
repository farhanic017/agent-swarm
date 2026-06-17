"""
Shared Memory System for Agent Swarm.

Provides a persistent, thread-safe memory store that all agents can read/write.
Every agent has awareness of what other agents are doing, what has happened,
and what will happen next. Supports:
- Event logging (what happened)
- Task tracking (what's happening now)
- Prediction storage (what will happen)
- Knowledge base (shared facts and learnings)
- Agent state awareness (who is doing what)
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class MemoryType(str, Enum):
    EVENT = "event"
    TASK = "task"
    PREDICTION = "prediction"
    KNOWLEDGE = "knowledge"
    STATE = "state"
    LESSON = "lesson"


@dataclass
class MemoryEntry:
    id: str
    type: MemoryType
    agent: str
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    related_to: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "agent": self.agent,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "tags": self.tags,
            "related_to": self.related_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            id=data["id"],
            type=MemoryType(data["type"]),
            agent=data["agent"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            confidence=data.get("confidence", 1.0),
            tags=data.get("tags", []),
            related_to=data.get("related_to", []),
        )


class SharedMemory:
    """Thread-safe shared memory store for all agents."""

    def __init__(self, max_entries: int = 10000):
        self._entries: list[MemoryEntry] = []
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"mem_{self._counter}_{int(time.time() * 1000)}"

    def store(
        self,
        type: MemoryType,
        agent: str,
        content: str,
        metadata: dict | None = None,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        related_to: list[str] | None = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            id=self._next_id(),
            type=type,
            agent=agent,
            content=content,
            metadata=metadata or {},
            confidence=confidence,
            tags=tags or [],
            related_to=related_to or [],
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
        return entry

    def query(
        self,
        type: MemoryType | None = None,
        agent: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        since: float | None = None,
        search: str | None = None,
    ) -> list[MemoryEntry]:
        with self._lock:
            results = list(self._entries)

        if type:
            results = [e for e in results if e.type == type]
        if agent:
            results = [e for e in results if e.agent == agent]
        if tags:
            results = [e for e in results if any(t in e.tags for t in tags)]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if search:
            search_lower = search.lower()
            results = [e for e in results if search_lower in e.content.lower()]

        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        with self._lock:
            return list(self._entries[-limit:])

    def get_agent_state(self, agent: str) -> dict:
        with self._lock:
            agent_entries = [e for e in self._entries if e.agent == agent]
        if not agent_entries:
            return {"agent": agent, "status": "unknown", "last_activity": None}

        tasks = [e for e in agent_entries if e.type == MemoryType.TASK]
        events = [e for e in agent_entries if e.type == MemoryType.EVENT]

        current_task = tasks[-1] if tasks else None
        return {
            "agent": agent,
            "status": "active" if current_task else "idle",
            "current_task": current_task.content if current_task else None,
            "task_count": len(tasks),
            "event_count": len(events),
            "last_activity": agent_entries[-1].timestamp if agent_entries else None,
        }

    def get_all_agent_states(self) -> dict[str, dict]:
        with self._lock:
            agents = set(e.agent for e in self._entries)
        return {agent: self.get_agent_state(agent) for agent in agents}

    def get_summary(self) -> dict:
        with self._lock:
            entries = list(self._entries)

        type_counts = {}
        for entry in entries:
            type_counts[entry.type.value] = type_counts.get(entry.type.value, 0) + 1

        agents = set(e.agent for e in entries)
        return {
            "total_entries": len(entries),
            "type_counts": type_counts,
            "agents": list(agents),
            "oldest": entries[0].timestamp if entries else None,
            "newest": entries[-1].timestamp if entries else None,
        }

    def export_json(self) -> str:
        with self._lock:
            return json.dumps([e.to_dict() for e in self._entries], indent=2)

    def import_json(self, data: str) -> int:
        entries = json.loads(data)
        count = 0
        for entry_data in entries:
            entry = MemoryEntry.from_dict(entry_data)
            with self._lock:
                self._entries.append(entry)
            count += 1
        return count

    def clear(self):
        with self._lock:
            self._entries.clear()

    def get_predictions(self, agent: str | None = None) -> list[MemoryEntry]:
        return self.query(type=MemoryType.PREDICTION, agent=agent, limit=100)

    def get_knowledge(self, tags: list[str] | None = None) -> list[MemoryEntry]:
        return self.query(type=MemoryType.KNOWLEDGE, tags=tags, limit=100)

    def get_task_history(self, agent: str | None = None, limit: int = 50) -> list[MemoryEntry]:
        return self.query(type=MemoryType.TASK, agent=agent, limit=limit)


# Global shared memory instance
_shared_memory: SharedMemory | None = None
_memory_lock = threading.Lock()


def get_shared_memory() -> SharedMemory:
    global _shared_memory
    if _shared_memory is None:
        with _memory_lock:
            if _shared_memory is None:
                _shared_memory = SharedMemory()
    return _shared_memory


# ---------------------------------------------------------------------------
# Tool functions for registry
# ---------------------------------------------------------------------------

def memory_store_event(agent: str, content: str, tags: str = "") -> str:
    mem = get_shared_memory()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry = mem.store(MemoryType.EVENT, agent, content, tags=tag_list)
    return json.dumps(entry.to_dict(), indent=2)


def memory_store_task(agent: str, content: str, metadata: str = "{}") -> str:
    mem = get_shared_memory()
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}
    entry = mem.store(MemoryType.TASK, agent, content, metadata=meta)
    return json.dumps(entry.to_dict(), indent=2)


def memory_store_prediction(agent: str, content: str, confidence: float = 0.5, tags: str = "") -> str:
    mem = get_shared_memory()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry = mem.store(MemoryType.PREDICTION, agent, content, confidence=confidence, tags=tag_list)
    return json.dumps(entry.to_dict(), indent=2)


def memory_store_knowledge(agent: str, content: str, tags: str = "") -> str:
    mem = get_shared_memory()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry = mem.store(MemoryType.KNOWLEDGE, agent, content, tags=tag_list)
    return json.dumps(entry.to_dict(), indent=2)


def memory_store_lesson(agent: str, context: str, outcome: str, lesson: str, success: bool = True) -> str:
    mem = get_shared_memory()
    content = json.dumps({"context": context, "outcome": outcome, "lesson": lesson, "success": success})
    entry = mem.store(MemoryType.LESSON, agent, content, tags=[context[:50]])
    return json.dumps(entry.to_dict(), indent=2)


def memory_query(type_filter: str = "", agent: str = "", tags: str = "", search: str = "", limit: int = 20) -> str:
    mem = get_shared_memory()
    type_enum = MemoryType(type_filter) if type_filter else None
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    results = mem.query(type=type_enum, agent=agent or None, tags=tag_list, search=search or None, limit=limit)
    return json.dumps([e.to_dict() for e in results], indent=2)


def memory_get_agent_state(agent: str) -> str:
    mem = get_shared_memory()
    state = mem.get_agent_state(agent)
    return json.dumps(state, indent=2)


def memory_get_all_states() -> str:
    mem = get_shared_memory()
    states = mem.get_all_agent_states()
    return json.dumps(states, indent=2)


def memory_get_summary() -> str:
    mem = get_shared_memory()
    summary = mem.get_summary()
    return json.dumps(summary, indent=2)


def memory_get_recent(limit: int = 20) -> str:
    mem = get_shared_memory()
    entries = mem.get_recent(limit)
    return json.dumps([e.to_dict() for e in entries], indent=2)


def memory_get_predictions(agent: str = "") -> str:
    mem = get_shared_memory()
    entries = mem.get_predictions(agent=agent or None)
    return json.dumps([e.to_dict() for e in entries], indent=2)


def memory_clear() -> str:
    mem = get_shared_memory()
    mem.clear()
    return json.dumps({"status": "cleared"})


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

SHARED_MEMORY_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "memory_store_event",
        "description": "Store an event in shared memory. Other agents can see what happened. Use after completing actions, encountering errors, or observing important changes.",
        "func": memory_store_event,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Your agent name"},
                "content": {"type": "string", "description": "Event description"},
                "tags": {"type": "string", "description": "Comma-separated tags for filtering"},
            },
            "required": ["agent", "content"],
        },
    },
    {
        "name": "memory_store_task",
        "description": "Store current task status in shared memory. Other agents see what you're working on now.",
        "func": memory_store_task,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Your agent name"},
                "content": {"type": "string", "description": "Current task description"},
                "metadata": {"type": "string", "description": "JSON metadata (progress, priority, etc.)"},
            },
            "required": ["agent", "content"],
        },
    },
    {
        "name": "memory_store_prediction",
        "description": "Store a prediction about what will happen next. Other agents can see future plans and expected outcomes.",
        "func": memory_store_prediction,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Your agent name"},
                "content": {"type": "string", "description": "Prediction about what will happen"},
                "confidence": {"type": "number", "description": "Confidence score 0.0-1.0"},
                "tags": {"type": "string", "description": "Comma-separated tags"},
            },
            "required": ["agent", "content"],
        },
    },
    {
        "name": "memory_store_knowledge",
        "description": "Store a knowledge fact in shared memory. Other agents can learn from your discoveries.",
        "func": memory_store_knowledge,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Your agent name"},
                "content": {"type": "string", "description": "Knowledge fact or discovery"},
                "tags": {"type": "string", "description": "Comma-separated tags"},
            },
            "required": ["agent", "content"],
        },
    },
    {
        "name": "memory_store_lesson",
        "description": "Store a lesson learned from experience. Other agents avoid your mistakes and repeat your successes.",
        "func": memory_store_lesson,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Your agent name"},
                "context": {"type": "string", "description": "What you were working on"},
                "outcome": {"type": "string", "description": "What happened"},
                "lesson": {"type": "string", "description": "What you learned"},
                "success": {"type": "boolean", "description": "Was this a success or failure?"},
            },
            "required": ["agent", "context", "outcome", "lesson"],
        },
    },
    {
        "name": "memory_query",
        "description": "Query shared memory for events, tasks, predictions, knowledge, or lessons. Filter by type, agent, tags, or search text.",
        "func": memory_query,
        "parameters": {
            "type": "object",
            "properties": {
                "type_filter": {"type": "string", "enum": ["event", "task", "prediction", "knowledge", "lesson", ""], "description": "Filter by memory type"},
                "agent": {"type": "string", "description": "Filter by agent name"},
                "tags": {"type": "string", "description": "Comma-separated tags to match"},
                "search": {"type": "string", "description": "Text search in content"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "memory_get_agent_state",
        "description": "Get the current state of a specific agent - what they're doing, their task count, and last activity.",
        "func": memory_get_agent_state,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Agent name to check"},
            },
            "required": ["agent"],
        },
    },
    {
        "name": "memory_get_all_states",
        "description": "Get the current state of ALL agents in the swarm. See who is active, idle, or stuck.",
        "func": memory_get_all_states,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "memory_get_summary",
        "description": "Get a summary of all shared memory: total entries, type breakdown, active agents.",
        "func": memory_get_summary,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "memory_get_recent",
        "description": "Get the most recent entries from shared memory across all agents.",
        "func": memory_get_recent,
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent entries (default 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "memory_get_predictions",
        "description": "Get all predictions stored by agents about what will happen next.",
        "func": memory_get_predictions,
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Filter by agent (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "memory_clear",
        "description": "Clear all shared memory. Use with caution - this resets all agent knowledge.",
        "func": memory_clear,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

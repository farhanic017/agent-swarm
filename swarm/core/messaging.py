"""Agent-to-Agent Messaging — direct communication between agents.

Extends the Consciousness hub with peer-to-peer messaging so agents
can talk to each other independently, request help, share findings,
and coordinate without orchestration overhead.
"""

from __future__ import annotations
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from swarm.core.consciousness import Consciousness


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    sender: str = ""
    recipient: str = ""
    content: str = ""
    msg_type: str = "direct"
    thread_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content[:1000],
            "msg_type": self.msg_type,
            "thread_id": self.thread_id,
            "timestamp": self.timestamp,
        }


class MessageHub:
    """Peer-to-peer messaging layer built on top of Consciousness.

    Agents can send direct messages, broadcast to all agents, and
    maintain threaded conversations. Every message is also published
    as a consciousness event so the broader swarm stays aware.
    """

    def __init__(self, consciousness: Consciousness):
        self._consciousness = consciousness
        self._messages: list[AgentMessage] = []
        self._max_messages: int = 5000

    def send_message(self, sender: str, recipient: str, content: str,
                     msg_type: str = "direct", thread_id: str = "") -> AgentMessage:
        msg = AgentMessage(
            sender=sender,
            recipient=recipient,
            content=content,
            msg_type=msg_type,
            thread_id=thread_id or uuid.uuid4().hex[:12],
        )
        self._messages.append(msg)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    self._consciousness.push_progress(
                        sender,
                        f"Message to {recipient}: {content[:100]}",
                        {"msg_type": msg_type, "thread_id": msg.thread_id},
                    )
                )
        except RuntimeError:
            pass

        return msg

    def broadcast(self, sender: str, content: str, msg_type: str = "broadcast") -> AgentMessage:
        msg = AgentMessage(
            sender=sender,
            recipient="*",
            content=content,
            msg_type=msg_type,
            thread_id=uuid.uuid4().hex[:12],
        )
        self._messages.append(msg)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    self._consciousness.push_progress(
                        sender, f"Broadcast: {content[:100]}", {"msg_type": msg_type}
                    )
                )
        except RuntimeError:
            pass

        return msg

    def get_messages(self, agent_name: str, since: float = 0.0,
                     msg_type: str = "", limit: int = 50) -> list[dict]:
        filtered = []
        for m in self._messages:
            if m.timestamp < since:
                continue
            if m.recipient not in (agent_name, "*") and m.sender != agent_name:
                continue
            if msg_type and m.msg_type != msg_type:
                continue
            filtered.append(m.to_dict())
        return filtered[-limit:]

    def get_thread(self, thread_id: str) -> list[dict]:
        return [m.to_dict() for m in self._messages if m.thread_id == thread_id]

    def get_unread_count(self, agent_name: str) -> int:
        return sum(1 for m in self._messages
                   if m.recipient in (agent_name, "*"))

    def get_conversation_summary(self, agent_name: str, limit: int = 20) -> str:
        msgs = self.get_messages(agent_name, limit=limit)
        if not msgs:
            return ""
        lines = ["=== Agent Messages ==="]
        for m in msgs:
            direction = "->" if m["recipient"] == agent_name else "<-"
            lines.append(f"[{m['sender']}] {direction} {m['content'][:200]}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"messages": [m.to_dict() for m in self._messages[-200:]]}

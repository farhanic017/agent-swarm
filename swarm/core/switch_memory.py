from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class SwitchMemoryRecord:
    agent_name: str
    model_ref: str
    context_hash: str
    full_context: str
    injections: int = 0


@dataclass
class SwitchMemory:
    """Tracks replacement-model handoff memory.

    A replacement model receives the full handoff context once for a given
    agent/model/context combination. If the same replacement is used again, it
    receives a compact reminder that points back to the already supplied memory.
    """

    _records: dict[tuple[str, str, str], SwitchMemoryRecord] = field(default_factory=dict)

    def build_message(self, agent_name: str, model_ref: str, context: str) -> str:
        context_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()[:16]
        key = (agent_name, model_ref, context_hash)
        record = self._records.get(key)
        if record is None:
            record = SwitchMemoryRecord(
                agent_name=agent_name,
                model_ref=model_ref,
                context_hash=context_hash,
                full_context=context,
            )
            self._records[key] = record
            record.injections += 1
            return (
                f"[SWITCH MEMORY: FULL_CONTEXT_ONCE id={context_hash}]\n"
                f"This is the complete handoff memory for {agent_name} on {model_ref}. "
                "Store it mentally and continue from it.\n\n"
                f"{context}"
            )

        record.injections += 1
        return (
            f"[SWITCH MEMORY: REMEMBERED id={context_hash}]\n"
            f"You already received the complete handoff memory for {agent_name} on {model_ref}. "
            "Do not restart. Continue from that remembered context and the latest user/tool messages."
        )

    def to_dict(self) -> dict:
        return {
            "records": [
                {
                    "agent_name": record.agent_name,
                    "model_ref": record.model_ref,
                    "context_hash": record.context_hash,
                    "injections": record.injections,
                }
                for record in self._records.values()
            ]
        }

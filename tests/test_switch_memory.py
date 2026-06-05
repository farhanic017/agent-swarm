from swarm.core.switch_memory import SwitchMemory


def test_switch_memory_sends_full_context_once_then_reminder():
    memory = SwitchMemory()
    context = "Original task plus artifacts and progress"

    first = memory.build_message("coder", "provider:model-a", context)
    second = memory.build_message("coder", "provider:model-a", context)

    assert "FULL_CONTEXT_ONCE" in first
    assert context in first
    assert "REMEMBERED" in second
    assert context not in second
    records = memory.to_dict()["records"]
    assert records[0]["injections"] == 2


def test_switch_memory_full_context_for_different_replacement_model():
    memory = SwitchMemory()
    context = "handoff context"
    first = memory.build_message("coder", "provider:model-a", context)
    second_model = memory.build_message("coder", "provider:model-b", context)

    assert "FULL_CONTEXT_ONCE" in first
    assert "FULL_CONTEXT_ONCE" in second_model
    assert len(memory.to_dict()["records"]) == 2

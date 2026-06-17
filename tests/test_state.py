import tempfile
from pathlib import Path
from swarm.core.state import SharedState, AgentTurn


def test_state_creation():
    state = SharedState(user_input="test task")
    assert state.user_input == "test task"
    assert state.iteration == 0
    assert state.agent_turns == []


def test_add_turn():
    state = SharedState()
    turn = AgentTurn(
        agent_name="researcher",
        input="research X",
        output="found Y",
        model="gpt-4",
        tokens_used=100,
        duration_ms=500,
    )
    state.add_turn(turn)
    assert state.iteration == 1
    assert len(state.agent_turns) == 1
    assert state.agent_turns[0].agent_name == "researcher"


def test_artifacts():
    state = SharedState()
    state.set_artifact("report", "content here")
    assert state.get_artifact("report") == "content here"
    assert state.get_artifact("missing", "default") == "default"


def test_context_string():
    state = SharedState(user_input="build a web app")
    state.summary = "Designed the architecture"
    context = state.to_context_string()
    assert "build a web app" in context
    assert "Designed the architecture" in context


def test_save_and_load():
    state = SharedState(user_input="test save")
    state.add_turn(AgentTurn(
        agent_name="test",
        input="input",
        output="output",
        model="m",
    ))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        state.save(str(path))

        loaded = SharedState.load(str(path))
        assert loaded.user_input == "test save"
        assert len(loaded.agent_turns) == 1
        assert loaded.agent_turns[0].agent_name == "test"

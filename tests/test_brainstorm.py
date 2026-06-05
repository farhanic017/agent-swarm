import pytest
from swarm.core.brainstorm import BrainstormEngine, estimate_complexity


@pytest.fixture
def engine():
    return BrainstormEngine()


def test_estimate_complexity_simple():
    assert estimate_complexity("hello world") < 3


def test_estimate_complexity_complex():
    score = estimate_complexity("Design a complex full stack architecture with multiple components")
    assert score >= 3


def test_create_session(engine):
    session = engine.create_session("Design a new feature", "Need to add user auth")
    assert session.problem == "Design a new feature"
    assert session.context == "Need to add user auth"
    assert session.status == "open"
    assert session.id


def test_add_idea(engine):
    session = engine.create_session("Fix performance issue")
    idea = engine.add_idea(session.id, "coder", "backend", "Use caching", 0.8)
    assert idea is not None
    assert idea.agent_name == "coder"
    assert idea.perspective == "backend"

    session2 = engine.get_session(session.id)
    assert len(session2.ideas) == 1


def test_add_idea_closed_session(engine):
    session = engine.create_session("test")
    engine.finalize(session.id, "Done")
    idea = engine.add_idea(session.id, "coder", "test", "idea")
    assert idea is None


def test_finalize_session(engine):
    session = engine.create_session("Build API")
    ok = engine.finalize(session.id, "Step 1: Design, Step 2: Implement", ["Design API", "Implement API"])
    assert ok

    session2 = engine.get_session(session.id)
    assert session2.status == "planned"
    assert "Step 1" in session2.plan
    assert len(session2.work_packages) == 2


def test_get_session_summary(engine):
    session = engine.create_session("Refactor database layer")
    engine.add_idea(session.id, "coder", "performance", "Use connection pooling", 0.9)
    engine.finalize(session.id, "Plan: optimize queries")
    summary = engine.get_session_summary(session.id)
    assert "Refactor database" in summary
    assert "connection pooling" in summary
    assert "Plan:" in summary


def test_should_brainstorm(engine):
    assert not engine.should_brainstorm("simple task")
    assert engine.should_brainstorm("complex architecture redesign with multiple services")


def test_get_active_session(engine):
    s1 = engine.create_session("First")
    assert engine.get_active_session() is not None
    assert engine.get_active_session().id == s1.id

    engine.finalize(s1.id, "done")
    assert engine.get_active_session() is None

    s2 = engine.create_session("Second")
    assert engine.get_active_session().id == s2.id


def test_complexity_threshold_configurable(engine):
    assert engine.complexity_threshold == 3
    engine.complexity_threshold = 5
    assert engine.complexity_threshold == 5
    assert not engine.should_brainstorm("complex full stack multi-step")
    engine.complexity_threshold = 1
    assert engine.should_brainstorm("complex task")


def test_multiple_ideas(engine):
    session = engine.create_session("Build feature")
    engine.add_idea(session.id, "coder", "code", "Write backend")
    engine.add_idea(session.id, "writer", "docs", "Write docs")
    engine.add_idea(session.id, "researcher", "research", "Research APIs")
    assert len(session.ideas) == 3


def test_to_dict(engine):
    engine.create_session("Test")
    d = engine.to_dict()
    assert d["active_sessions"] >= 1

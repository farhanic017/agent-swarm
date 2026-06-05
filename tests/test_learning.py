import os
import pytest
import tempfile
from pathlib import Path
from swarm.core.learning import LessonLearner


@pytest.fixture
def learner():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "lessons.json"
        yield LessonLearner(storage_path=str(path))


def test_log_lesson(learner):
    lsn = learner.log_lesson("coder", "Working on auth", "Added JWT", "Always validate tokens", ["auth", "security"], True)
    assert lsn.agent_name == "coder"
    assert lsn.lesson == "Always validate tokens"
    assert lsn.tags == ["auth", "security"]
    assert lsn.success is True


def test_log_failure_lesson(learner):
    lsn = learner.log_lesson("coder", "Database migration", "Failed", "Always backup first", ["db"], False)
    assert lsn.success is False


def test_get_relevant_lessons_by_context(learner):
    learner.log_lesson("coder", "Working on authentication", "Success", "Use OAuth2", ["auth", "security"], True)
    learner.log_lesson("coder", "Building UI", "Success", "Use Tailwind", ["ui", "frontend"], True)

    lessons = learner.get_relevant_lessons("coder", "Building authentication system", max_results=5)
    assert len(lessons) >= 1
    assert any("OAuth2" in l.lesson for l in lessons)


def test_get_relevant_lessons_respects_max(learner):
    for i in range(10):
        learner.log_lesson("coder", f"Context {i}", "Success", f"Lesson {i}", ["test"], True)

    lessons = learner.get_relevant_lessons("coder", "Context", max_results=3)
    assert len(lessons) <= 3


def test_agent_filtering(learner):
    learner.log_lesson("coder", "Auth", "Success", "Coder lesson", ["auth"], True)
    learner.log_lesson("writer", "Auth", "Success", "Writer lesson", ["auth"], True)

    coder_lessons = learner.get_relevant_lessons("coder", "Auth", max_results=10)
    writer_lessons = learner.get_relevant_lessons("writer", "Auth", max_results=10)

    assert any("Coder lesson" in l.lesson for l in coder_lessons)
    assert any("Writer lesson" in l.lesson for l in writer_lessons)


def test_get_relevant_no_matches(learner):
    learner.log_lesson("coder", "Python code", "Success", "Use type hints", ["python"], True)
    lessons = learner.get_relevant_lessons("coder", "cooking pasta", max_results=5)
    assert len(lessons) == 0


def test_lessons_for_prompt_format(learner):
    learner.log_lesson("coder", "Debugging", "Found bug", "Use try/except", ["errors"], True)
    prompt = learner.get_lessons_for_prompt("coder", "Debugging issue in production")
    assert "=== Lessons Learned" in prompt
    assert "try/except" in prompt


def test_lessons_for_prompt_empty(learner):
    prompt = learner.get_lessons_for_prompt("coder", "something")
    assert prompt == ""


def test_get_stats(learner):
    learner.log_lesson("coder", "A", "Success", "L1", [], True)
    learner.log_lesson("coder", "B", "Success", "L2", [], True)
    learner.log_lesson("writer", "C", "Failed", "L3", [], False)

    stats = learner.get_stats()
    assert stats["total_lessons"] == 3
    assert stats["by_agent"]["coder"] == 2
    assert stats["by_agent"]["writer"] == 1
    assert stats["total_applies"] >= 0


def test_prune_low_value(learner):
    learner.log_lesson("coder", "Test", "Success", "Keep me", [], True)
    learner.log_lesson("coder", "Test", "Success", "Keep me too", [], True)
    for lsn in learner._lessons:
        lsn.score = 1
    pruned = learner.prune_low_value(min_score=3)
    assert pruned >= 2


def test_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "lessons.json"
        l1 = LessonLearner(storage_path=str(path))
        l1.log_lesson("coder", "Auth", "Done", "Use JWT", ["auth"], True)

        l2 = LessonLearner(storage_path=str(path))
        assert len(l2._lessons) == 1
        assert l2._lessons[0].lesson == "Use JWT"


def test_wildcard_agent_matches_all(learner):
    learner.log_lesson("*", "Any task", "Success", "Universal lesson", ["general"], True)
    lessons = learner.get_relevant_lessons("coder", "Any task", max_results=5)
    assert len(lessons) >= 1
    assert "Universal lesson" in lessons[0].lesson

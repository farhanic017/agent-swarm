"""Tests for the Shared Consciousness module."""

from __future__ import annotations
import pytest
import asyncio
from swarm.core.consciousness import Consciousness, ConsciousnessEvent


@pytest.fixture
def consciousness():
    return Consciousness()


class TestConsciousnessEvent:
    def test_create_event(self):
        event = ConsciousnessEvent(type="progress", source="coder", payload={"message": "working"})
        assert event.type == "progress"
        assert event.source == "coder"
        assert event.payload["message"] == "working"
        assert event.id is not None
        assert event.timestamp > 0

    def test_event_to_dict(self):
        event = ConsciousnessEvent(type="test", source="system", payload={"key": "val"})
        d = event.to_dict()
        assert d["type"] == "test"
        assert d["source"] == "system"
        assert d["payload"]["key"] == "val"


class TestPubSub:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, consciousness):
        received = []
        sid = consciousness.subscribe("progress", lambda e: received.append(e))
        await consciousness.push_progress("coder", "working on it")
        assert len(received) == 1
        assert received[0].type == "progress"
        assert received[0].source == "coder"

    @pytest.mark.asyncio
    async def test_subscribe_wildcard(self, consciousness):
        received = []
        consciousness.subscribe("*", lambda e: received.append(e))
        await consciousness.push_progress("coder", "test")
        await consciousness.push_error("researcher", "err")
        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self, consciousness):
        received = []
        sid = consciousness.subscribe("progress", lambda e: received.append(e))
        consciousness.unsubscribe(sid)
        await consciousness.push_progress("coder", "test")
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_async_callback(self, consciousness):
        results = []

        async def async_cb(event):
            results.append(event.type)

        consciousness.subscribe("progress", async_cb)
        await consciousness.push_progress("coder", "test")
        await asyncio.sleep(0.01)
        assert "progress" in results


class TestLiveState:
    @pytest.mark.asyncio
    async def test_push_state(self, consciousness):
        await consciousness.push_state("current_agent", "coder", "orchestrator")
        assert consciousness.get_state("current_agent") == "coder"

    @pytest.mark.asyncio
    async def test_push_state_updates_live_state(self, consciousness):
        await consciousness.push_state("count", 1, "system")
        assert consciousness.get_state("count") == 1
        await consciousness.push_state("count", 2, "system")
        assert consciousness.get_state("count") == 2

    @pytest.mark.asyncio
    async def test_get_all_state(self, consciousness):
        await consciousness.push_state("a", 1, "sys")
        await consciousness.push_state("b", 2, "sys")
        all_state = consciousness.get_all_state()
        assert all_state == {"a": 1, "b": 2}


class TestArtifacts:
    @pytest.mark.asyncio
    async def test_push_and_get_artifact(self, consciousness):
        await consciousness.push_artifact("summary", "done", "coder")
        assert consciousness.get_artifact("summary") == "done"

    @pytest.mark.asyncio
    async def test_get_all_artifacts(self, consciousness):
        await consciousness.push_artifact("file1", "content1", "coder")
        await consciousness.push_artifact("file2", "content2", "writer")
        arts = consciousness.get_all_artifacts()
        assert arts == {"file1": "content1", "file2": "content2"}


class TestContextSummary:
    @pytest.mark.asyncio
    async def test_empty_summary(self, consciousness):
        summary = consciousness.get_recent_summary()
        assert summary == ""

    @pytest.mark.asyncio
    async def test_summary_includes_progress(self, consciousness):
        await consciousness.push_progress("coder", "analyzing data")
        summary = consciousness.get_recent_summary()
        assert "[coder]" in summary
        assert "analyzing data" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_completion(self, consciousness):
        await consciousness.push_completion("coder", "result data", "task done")
        summary = consciousness.get_recent_summary()
        assert "Completed" in summary or "completed" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_errors(self, consciousness):
        await consciousness.push_error("researcher", "API timeout")
        summary = consciousness.get_recent_summary()
        assert "Error" in summary
        assert "API timeout" in summary

    @pytest.mark.asyncio
    async def test_full_context_for_switch(self, consciousness):
        await consciousness.push_progress("coder", "wrote the main function")
        await consciousness.push_artifact("output.txt", "hello world", "coder")
        ctx = consciousness.get_full_context_for_switch("Write a Python script")
        assert "## Original Task" in ctx
        assert "Write a Python script" in ctx
        assert "output.txt" in ctx or "Artifacts" in ctx
        assert "Your Task" in ctx
        assert "Do NOT restart" in ctx or "build on" in ctx.lower()

    @pytest.mark.asyncio
    async def test_full_context_with_errors(self, consciousness):
        await consciousness.push_error("researcher", "model failed")
        ctx = consciousness.get_full_context_for_switch("Research task")
        assert "Errors" in ctx
        assert "model failed" in ctx


class TestSerialization:
    @pytest.mark.asyncio
    async def test_to_dict(self, consciousness):
        await consciousness.push_state("agent", "coder", "sys")
        await consciousness.push_progress("coder", "working")
        d = consciousness.to_dict()
        assert "live_state" in d
        assert "artifacts" in d
        assert "event_log" in d

    @pytest.mark.asyncio
    async def test_from_dict(self, consciousness):
        await consciousness.push_state("key", "val", "sys")
        d = consciousness.to_dict()
        c2 = Consciousness.from_dict(d)
        assert c2.get_state("key") == "val"

    def test_from_dict_empty(self):
        c = Consciousness.from_dict({})
        assert c.get_all_state() == {}
        assert c.get_all_artifacts() == {}


class TestEventLog:
    @pytest.mark.asyncio
    async def test_get_events_by_type(self, consciousness):
        await consciousness.push_progress("coder", "test")
        await consciousness.push_error("researcher", "test")
        events = consciousness.get_events(event_type="error")
        assert len(events) == 1
        assert events[0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_get_events_by_source(self, consciousness):
        await consciousness.push_progress("coder", "work")
        await consciousness.push_progress("writer", "write")
        events = consciousness.get_events(source="writer")
        assert len(events) == 1
        assert events[0]["source"] == "writer"

    @pytest.mark.asyncio
    async def test_get_events_limit(self, consciousness):
        for i in range(10):
            await consciousness.push_progress("coder", f"step {i}")
        events = consciousness.get_events(limit=3)
        assert len(events) == 3


class TestEventTypes:
    @pytest.mark.asyncio
    async def test_push_diagnostic(self, consciousness):
        await consciousness.push_diagnostic("react_doctor", "warning", "unused import")
        events = consciousness.get_events(event_type="diagnostic")
        assert len(events) == 1
        assert events[0]["payload"]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_push_completion(self, consciousness):
        await consciousness.push_completion("coder", "done", "task complete")
        events = consciousness.get_events(event_type="completion")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_push_state_event(self, consciousness):
        consciousness._live_state = {}
        await consciousness.push_state("agent", "coder", "sys")
        assert consciousness.get_state("agent") == "coder"

    @pytest.mark.asyncio
    async def test_to_context_string(self, consciousness):
        s = consciousness.to_context_string()
        assert isinstance(s, str)


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_concurrent_publish(self, consciousness):
        """Multiple concurrent publishes should not deadlock."""
        async def publisher(n):
            for i in range(20):
                await consciousness.push_progress("coder", f"step {i}")
        tasks = [publisher(i) for i in range(5)]
        await asyncio.gather(*tasks)
        assert len(consciousness._event_log) >= 100

    def test_empty_state_get(self, consciousness):
        """Getting a state that was never set returns None."""
        assert consciousness.get_state("nonexistent") is None

    def test_unsubscribe_nonexistent(self, consciousness):
        """Unsubscribing a non-existent sid should not crash."""
        consciousness.unsubscribe(99999)

    @pytest.mark.asyncio
    async def test_push_without_callbacks(self, consciousness):
        """Pushing when no subscribers are registered works."""
        await consciousness.push_progress("coder", "test")
        assert len(consciousness._event_log) == 1

    @pytest.mark.asyncio
    async def test_event_log_overflow(self, consciousness):
        """Event log should not exceed max_events (5000)."""
        for i in range(5010):
            await consciousness.push_progress("sys", f"test {i}")
        assert len(consciousness._event_log) <= 5000

    def test_serialize_large_state(self, consciousness):
        """Large values in live state should serialize cleanly."""
        consciousness._live_state["big"] = "x" * 10000
        consciousness._live_state["list_val"] = [1, 2, 3]
        d = consciousness.to_dict()
        assert d["live_state"]["big"] == "x" * 10000
        assert d["live_state"]["list_val"] == [1, 2, 3]

    def test_get_recent_summary_with_no_events(self, consciousness):
        """get_recent_summary should return empty string when no events."""
        summary = consciousness.get_recent_summary()
        assert summary == ""

    @pytest.mark.asyncio
    async def test_get_events_no_filter(self, consciousness):
        """get_events with no filters returns all events."""
        await consciousness.push_progress("a", "msg1")
        await consciousness.push_error("b", "err1")
        events = consciousness.get_events()
        assert len(events) == 2

    def test_event_to_dict_includes_id_and_timestamp(self):
        event = ConsciousnessEvent(type="test", source="sys", payload={})
        d = event.to_dict()
        assert "id" in d
        assert "timestamp" in d
        assert isinstance(d["id"], str)
        assert isinstance(d["timestamp"], (int, float))

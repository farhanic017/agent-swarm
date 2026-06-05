import pytest
import time
from swarm.core.consciousness import Consciousness
from swarm.core.messaging import MessageHub


@pytest.fixture
def hub():
    return MessageHub(Consciousness())


def test_send_message(hub):
    msg = hub.send_message("coder", "researcher", "Can you find the API docs?")
    assert msg.sender == "coder"
    assert msg.recipient == "researcher"
    assert msg.content == "Can you find the API docs?"
    assert msg.msg_type == "direct"
    assert msg.thread_id


def test_get_messages_for_recipient(hub):
    hub.send_message("coder", "researcher", "Message 1")
    hub.send_message("writer", "researcher", "Message 2")
    hub.send_message("researcher", "coder", "Reply")

    msgs = hub.get_messages("researcher")
    assert len(msgs) >= 2
    recipients = [m["recipient"] for m in msgs]
    assert "researcher" in recipients


def test_get_messages_since(hub):
    hub.send_message("coder", "researcher", "Old")
    t = time.time() + 0.001
    time.sleep(0.01)
    hub.send_message("writer", "researcher", "New")

    msgs = hub.get_messages("researcher", since=t)
    assert all(m["timestamp"] >= t for m in msgs)
    assert any("New" in m["content"] for m in msgs)


def test_broadcast(hub):
    msg = hub.broadcast("coder", "Everyone look at this")
    assert msg.recipient == "*"
    assert msg.msg_type == "broadcast"

    msgs = hub.get_messages("researcher")
    contents = [m["content"] for m in msgs]
    assert any("Everyone" in c for c in contents)

    msgs2 = hub.get_messages("writer")
    contents2 = [m["content"] for m in msgs2]
    assert any("Everyone" in c for c in contents2)


def test_thread_conversation(hub):
    msg1 = hub.send_message("coder", "researcher", "First", thread_id="thread_1")
    msg2 = hub.send_message("researcher", "coder", "Second", thread_id="thread_1")
    msg3 = hub.send_message("coder", "researcher", "Third", thread_id="thread_1")

    thread = hub.get_thread("thread_1")
    assert len(thread) == 3
    assert thread[0]["content"] == "First"
    assert thread[1]["content"] == "Second"
    assert thread[2]["content"] == "Third"


def test_get_messages_filtered_by_type(hub):
    hub.send_message("coder", "researcher", "Normal")
    hub.send_message("coder", "researcher", "Help!", msg_type="request_help")

    msgs = hub.get_messages("researcher", msg_type="request_help")
    assert len(msgs) == 1
    assert msgs[0]["msg_type"] == "request_help"


def test_get_unread_count(hub):
    hub.send_message("coder", "researcher", "Hello")
    hub.send_message("writer", "researcher", "Hi")
    assert hub.get_unread_count("researcher") >= 2


def test_conversation_summary(hub):
    hub.send_message("coder", "researcher", "Message content here")
    summary = hub.get_conversation_summary("researcher")
    assert "=== Agent Messages ===" in summary
    assert "coder" in summary
    assert "Message content" in summary


def test_sender_sees_own_messages(hub):
    hub.send_message("coder", "researcher", "Sent by coder")
    msgs = hub.get_messages("coder")
    assert any("Sent by coder" in m["content"] for m in msgs)


def test_to_dict(hub):
    hub.send_message("a", "b", "test")
    d = hub.to_dict()
    assert "messages" in d
    assert len(d["messages"]) >= 1


def test_all_agents_can_exchange_direct_and_broadcast_messages(hub):
    agents = ["coder", "researcher", "testing", "security"]
    for sender in agents:
        for recipient in agents:
            if sender != recipient:
                hub.send_message(sender, recipient, f"{sender} to {recipient}")

    hub.broadcast("master", "final integration review")

    for agent in agents:
        visible = hub.get_messages(agent, limit=100)
        contents = " ".join(msg["content"] for msg in visible)
        assert "final integration review" in contents
        for other in agents:
            if other != agent:
                assert f"{other} to {agent}" in contents or f"{agent} to {other}" in contents

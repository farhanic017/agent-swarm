#  Auto Model Switcher  ───  Test Suite (26 tests)
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

"""Auto Model Switcher v2 — Tests"""

import json, sys, os, tempfile, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "model": "opencode/big-pickle",
    "provider": {
        "google-ai": {
            "options": {"apiKey": "test-google-key"},
            "models": {"gemini/gemini-2.0-flash-001": {}},
        },
        "openrouter": {
            "options": {"apiKey": "sk-or-test-key"},
            "models": {
                "deepseek/deepseek-v4-flash:free": {},
                "qwen/qwen3-coder:free": {},
            },
        },
        "azure-openai": {
            "options": {"apiKey": "test-azure-key", "endpoint": "https://test.openai.azure.com"},
            "models": {"gpt-4o": {}, "o4-mini": {}},
        },
    },
}

# ─── Config Parsing ──────────────────────────────────────────────────────────

def test_parse_opencode_config():
    from switcher import parse_opencode_config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonc", delete=False) as f:
        f.write(json.dumps(SAMPLE_CONFIG, indent=2))
        tmp = f.name
    try:
        cfg = parse_opencode_config(Path(tmp))
        assert cfg["model"] == "opencode/big-pickle"
        assert "google-ai" in cfg["provider"]
    finally:
        os.unlink(tmp)


def test_parse_with_comments():
    from switcher import parse_opencode_config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonc", delete=False) as f:
        f.write("""{
  // comment
  "model": "m1",
  "provider": {
    "p": {
      "options": {"apiKey": "k"},
      "models": {"m1": {}}
    }
  }
}""")
        tmp = f.name
    try:
        cfg = parse_opencode_config(Path(tmp))
        assert cfg["model"] == "m1"
    finally:
        os.unlink(tmp)

# ─── State ───────────────────────────────────────────────────────────────────

def test_state_lifecycle():
    from switcher import (is_depleted, mark_depleted, mark_recovered,
                          load_state, save_state, get_active, set_active)
    state = load_state()
    key = "test:depleted-model"
    assert not is_depleted(key)
    mark_depleted(key, "test reason", cooldown_minutes=1)
    assert is_depleted(key)
    mark_recovered(key)
    assert not is_depleted(key)
    set_active("opencode", "test:active")
    assert get_active("opencode") == "test:active"
    state = load_state()
    state["depleted"].pop(key, None)
    save_state(state)


def test_context():
    from switcher import save_context, load_context
    save_context("model:a", "model:b", "test switch", "summary text")
    ctx = load_context()
    assert ctx["previous_model"] == "model:a"
    assert ctx["new_model"] == "model:b"
    assert ctx["switch_reason"] == "test switch"
    os.remove(Path.home() / ".auto-model-switcher" / "context.json")


def test_recovery_eta():
    from switcher import get_recovery_eta, mark_depleted, load_state, save_state
    eta = get_recovery_eta()
    assert not eta["all_depleted"]
    mark_depleted("test:model1", "out of credits", cooldown_minutes=60)
    eta = get_recovery_eta()
    assert eta["all_depleted"] is False  # active model isn't in depleted
    state = load_state()
    state["active"]["opencode"] = "test:model1"
    save_state(state)
    eta = get_recovery_eta()
    assert eta["all_depleted"] is True
    state = load_state()
    state["depleted"].pop("test:model1", None)
    save_state(state)

# ─── Model Scoring ───────────────────────────────────────────────────────────

def test_score_free_beat_paid():
    from switcher import score_model
    free_healthy = (True, "healthy")
    paid_healthy = (True, "healthy")
    free_score = score_model({"key": "f", "model_id": "m", "is_free": True, "provider": "test"}, free_healthy)
    paid_score = score_model({"key": "p", "model_id": "m", "is_free": False, "provider": "test"}, paid_healthy)
    assert free_score > paid_score, f"Free {free_score} should beat paid {paid_score}"


def test_score_zero_on_unhealthy():
    from switcher import score_model
    assert score_model({"key": "x", "model_id": "m", "is_free": False, "provider": "t"}, (False, "fail")) == 0


def test_score_reasoning_boost():
    from switcher import score_model
    h = (True, "healthy")
    base = score_model({"key": "x", "model_id": "gpt-4o", "is_free": False, "provider": "t"}, h)
    reasoning = score_model({"key": "x", "model_id": "o4-mini", "is_free": False, "provider": "t"}, h)
    assert reasoning > base

# ─── Health Checks ───────────────────────────────────────────────────────────

def test_check_openrouter_healthy():
    from unittest.mock import patch, MagicMock
    from switcher import check_openrouter, _get_session
    with patch("switcher._get_session") as mock_sess:
        mock_sess.return_value = MagicMock()
        mock_sess.return_value.get.return_value.status_code = 200
        mock_sess.return_value.get.return_value.json.return_value = {"data": {"credits": 50.0, "limit": 200.0}}
        h, m = check_openrouter({"api_key": "k"})
        assert h


def test_check_openrouter_zero_credits():
    from unittest.mock import patch, MagicMock
    from switcher import check_openrouter
    with patch("switcher._get_session") as mock_sess:
        mock_sess.return_value = MagicMock()
        mock_sess.return_value.get.return_value.status_code = 200
        mock_sess.return_value.get.return_value.json.return_value = {"data": {"credits": 0.0, "limit": 200.0}}
        h, m = check_openrouter({"api_key": "k"})
        assert not h
        assert "0 credits" in m


def test_check_openrouter_402():
    from unittest.mock import patch, MagicMock
    from switcher import check_openrouter
    with patch("switcher._get_session") as mock_sess:
        mock_sess.return_value = MagicMock()
        mock_sess.return_value.get.return_value.status_code = 402
        h, m = check_openrouter({"api_key": "k"})
        assert not h
        assert "0 credits" in m


def test_check_openrouter_402():
    from unittest.mock import patch, MagicMock
    from switcher import check_openrouter
    mock_session = MagicMock()
    mock_session.get.return_value.status_code = 402
    with patch("switcher._get_session", return_value=mock_session):
        h, m = check_openrouter({"api_key": "k"})
        assert not h

# ─── Free-Tier Gate Detection ────────────────────────────────────────────────

def test_detect_free_tier_gate():
    from switcher import detect_free_tier_gate
    provider = {"is_free": True}
    assert detect_free_tier_gate(provider, "buy 10 tokens get 1000 free")
    assert detect_free_tier_gate(provider, "insufficient credits, add funds")
    assert detect_free_tier_gate(provider, "purchase credits to continue using free tier")
    assert not detect_free_tier_gate(provider, "healthy, 100 credits remaining")


def test_detect_gate_only_for_free():
    from switcher import detect_free_tier_gate
    assert not detect_free_tier_gate({"is_free": False}, "buy tokens free")

# ─── Parallel Checking ───────────────────────────────────────────────────────

def test_check_all_parallel():
    from unittest.mock import patch
    from switcher import check_all_parallel
    chain = [{"key": "a:m1", "provider": "test", "model_id": "m1", "is_free": True}]
    with patch("switcher._checked_model_with_session") as mock:
        mock.return_value = (True, "mock ok")
        results = check_all_parallel(chain)
        assert "a:m1" in results
        assert results["a:m1"][0] is True


def test_build_chain():
    from switcher import build_chain
    c = build_chain([
        {"key": "p", "is_free": False},
        {"key": "f", "is_free": True},
    ])
    assert c[0]["key"] == "f"
    assert c[1]["key"] == "p"


def test_discover_from_env():
    from switcher import discover_from_env
    os.environ["OPENAI_API_KEY"] = "test-key"
    providers = []
    discover_from_env(providers)
    assert any(p["provider"] == "openai" for p in providers)
    del os.environ["OPENAI_API_KEY"]

# ─── MCP State Preservation ───────────────────────────────────────────────────

def test_mcp_tool_call_record():
    from switcher import save_mcp_tool_call, _load_mcp_state, clear_mcp_state
    clear_mcp_state()
    save_mcp_tool_call("read_file", {"path": "/foo/bar.py"}, "hash123")
    state = _load_mcp_state()
    assert len(state["tools_executed"]) == 1
    assert state["tools_executed"][0]["name"] == "read_file"
    clear_mcp_state()


def test_mcp_file_write_record():
    from switcher import save_mcp_file_write, _load_mcp_state, clear_mcp_state
    clear_mcp_state()
    save_mcp_file_write("/foo/bar.py", "write")
    state = _load_mcp_state()
    assert len(state["file_writes"]) == 1
    assert state["file_writes"][0]["action"] == "write"
    clear_mcp_state()


def test_mcp_handoff_has_executed_tools():
    from switcher import (save_mcp_tool_call, build_mcp_handoff, clear_mcp_state)
    clear_mcp_state()
    save_mcp_tool_call("bash", {"command": "npm test"}, "abc")
    handoff = build_mcp_handoff("model:a", "model:b")
    assert handoff["previous_model"] == "model:a"
    assert handoff["new_model"] == "model:b"
    assert len(handoff["already_executed_tools"]) == 1
    assert handoff["already_executed_tools"][0]["name"] == "bash"
    clear_mcp_state()


def test_mcp_handoff_clears_after_save_context():
    from switcher import (save_mcp_tool_call, save_context, load_context,
                          _load_mcp_state, clear_mcp_state)
    from pathlib import Path
    clear_mcp_state()
    save_mcp_tool_call("read_file", {"path": "/x.py"}, "h1")
    save_context("model:a", "model:b", "test", "summary")
    ctx = load_context()
    assert "mcp" in ctx
    assert len(ctx["mcp"]["already_executed_tools"]) == 1
    # MCP state should be cleared after building handoff
    mcp = _load_mcp_state()
    assert len(mcp["tools_executed"]) == 0
    # Clean up
    Path.home().joinpath(".auto-model-switcher", "context.json").unlink(missing_ok=True)
    Path.home().joinpath(".auto-model-switcher", "mcp_state.json").unlink(missing_ok=True)


# ─── Local Model Cold Starts ─────────────────────────────────────────────────

def test_check_ollama_cold_start_detected():
    from unittest.mock import patch, MagicMock
    from switcher import check_ollama
    provider = {"model_id": "llama3", "provider": "ollama"}
    with patch("switcher._get_session") as mock_sess:
        mock_sess.return_value = MagicMock()
        mock_sess.return_value.get.return_value.status_code = 200
        mock_sess.return_value.get.return_value.json.return_value = {"models": [{"name": "llama2"}]}
        mock_sess.return_value.post.side_effect = __import__("requests").Timeout("model loading")
        h, m = check_ollama(provider)
        assert h is True
        assert "cold start" in m.lower() or "loading" in m.lower()


def test_check_ollama_ready():
    from unittest.mock import patch, MagicMock
    from switcher import check_ollama
    provider = {"model_id": "llama3", "provider": "ollama"}
    with patch("switcher._get_session") as mock_sess:
        mock_sess.return_value = MagicMock()
        mock_sess.return_value.get.return_value.status_code = 200
        mock_sess.return_value.get.return_value.json.return_value = {"models": [{"name": "llama3"}]}
        mock_sess.return_value.post.return_value.status_code = 200
        mock_sess.return_value.post.return_value.json.return_value = {"response": "ok"}
        h, m = check_ollama(provider)
        assert h is True
        assert "ready" in m.lower()


# ─── Rate Limit Header Parsing ────────────────────────────────────────────────

def test_parse_retry_after_header():
    from unittest.mock import MagicMock
    from switcher import _parse_retry_after, _build_rate_limit_msg
    r = MagicMock()
    r.headers = {"Retry-After": "120"}
    assert _parse_retry_after(r) == 120


def test_parse_ratelimit_reset_header():
    from unittest.mock import MagicMock
    from switcher import _parse_retry_after
    import time
    r = MagicMock()
    reset_ts = int(time.time()) + 300
    r.headers = {"x-ratelimit-reset": str(reset_ts)}
    retry = _parse_retry_after(r)
    assert retry is not None
    assert 295 <= retry <= 305


def test_build_rate_limit_msg():
    from unittest.mock import MagicMock
    from switcher import _build_rate_limit_msg
    r = MagicMock()
    r.headers = {"Retry-After": "45"}
    msg = _build_rate_limit_msg(429, r)
    assert "rate limited (429)" in msg
    assert "retry in 45s" in msg


def test_mark_depleted_uses_retry_seconds():
    from switcher import mark_depleted, load_state, save_state
    # Mark depleted with a retry-after style reason
    mark_depleted("test:rate-limited-model", "rate limited (429), retry in 120s")
    state = load_state()
    entry = state["depleted"].get("test:rate-limited-model")
    assert entry is not None
    assert entry.get("retry_seconds") == 120
    assert "cooldown_until" in entry
    state["depleted"].pop("test:rate-limited-model", None)
    save_state(state)


# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [obj for name, obj in globals().items()
             if name.startswith("test_") and isinstance(obj, types.FunctionType)]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  [OK] {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1
    print(f"\n  {passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)

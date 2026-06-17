"""Tests for the model hiding feature."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from swarm.switcher.switcher import (
    hide_model,
    unhide_model,
    get_hidden_models,
    is_hidden,
    build_chain,
    load_state,
    save_state,
)


# ── Helper ──────────────────────────────────────────────────────────────────

def _reset_state():
    """Reset state to clean defaults for each test."""
    save_state({"active": {}, "depleted": {}, "history": [], "last_switch": None, "hidden": []})


# ── CRUD operations ─────────────────────────────────────────────────────────

class TestHideModel:
    def setup_method(self):
        _reset_state()

    def test_hide_model_adds_to_list(self):
        hide_model("openrouter:gpt-4o")
        assert "openrouter:gpt-4o" in get_hidden_models()

    def test_hide_model_idempotent(self):
        hide_model("openrouter:gpt-4o")
        hide_model("openrouter:gpt-4o")
        assert get_hidden_models().count("openrouter:gpt-4o") == 1

    def test_hide_model_records_history(self):
        hide_model("openrouter:gpt-4o", reason="too expensive")
        state = load_state()
        history = state.get("history", [])
        assert any(h["model"] == "openrouter:gpt-4o" and h["action"] == "hidden" for h in history)

    def test_hide_multiple_models(self):
        hide_model("openrouter:gpt-4o")
        hide_model("azure:gpt-4o")
        hide_model("openai:gpt-4o-mini")
        hidden = get_hidden_models()
        assert len(hidden) == 3
        assert "openrouter:gpt-4o" in hidden
        assert "azure:gpt-4o" in hidden
        assert "openai:gpt-4o-mini" in hidden


class TestUnhideModel:
    def setup_method(self):
        _reset_state()

    def test_unhide_model_removes_from_list(self):
        hide_model("openrouter:gpt-4o")
        assert unhide_model("openrouter:gpt-4o") is True
        assert "openrouter:gpt-4o" not in get_hidden_models()

    def test_unhide_nonexistent_returns_false(self):
        assert unhide_model("nonexistent:model") is False

    def test_unhide_records_history(self):
        hide_model("openrouter:gpt-4o")
        unhide_model("openrouter:gpt-4o")
        state = load_state()
        history = state.get("history", [])
        assert any(h["model"] == "openrouter:gpt-4o" and h["action"] == "unhidden" for h in history)


class TestIsHidden:
    def setup_method(self):
        _reset_state()

    def test_is_hidden_true(self):
        hide_model("openrouter:gpt-4o")
        assert is_hidden("openrouter:gpt-4o") is True

    def test_is_hidden_false(self):
        assert is_hidden("openrouter:gpt-4o") is False

    def test_is_hidden_after_unhide(self):
        hide_model("openrouter:gpt-4o")
        unhide_model("openrouter:gpt-4o")
        assert is_hidden("openrouter:gpt-4o") is False


class TestGetHiddenModels:
    def setup_method(self):
        _reset_state()

    def test_empty_by_default(self):
        assert get_hidden_models() == []

    def test_returns_copy(self):
        hide_model("openrouter:gpt-4o")
        hidden = get_hidden_models()
        hidden.append("fake:model")
        assert "fake:model" not in get_hidden_models()


# ── Chain filtering ─────────────────────────────────────────────────────────

class TestBuildChainFiltering:
    def setup_method(self):
        _reset_state()

    def test_hidden_models_excluded_from_chain(self):
        providers = [
            {"key": "openrouter:gpt-4o", "provider": "openrouter", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
            {"key": "google:gemini-flash", "provider": "google", "model_id": "gemini-flash",
             "is_free": True, "api_key": "test", "endpoint": None,
             "deployment": "gemini-flash", "source": "test", "is_active": False},
        ]

        hide_model("openrouter:gpt-4o")
        chain = build_chain(providers)

        keys = [p["key"] for p in chain]
        assert "openrouter:gpt-4o" not in keys
        assert "openai:gpt-4o" in keys
        assert "google:gemini-flash" in keys

    def test_no_hidden_models_chain_unchanged(self):
        providers = [
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
        ]
        chain = build_chain(providers)
        assert len(chain) == 1
        assert chain[0]["key"] == "openai:gpt-4o"

    def test_all_models_hidden_empty_chain(self):
        providers = [
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
        ]
        hide_model("openai:gpt-4o")
        chain = build_chain(providers)
        assert len(chain) == 0

    def test_hidden_preserves_free_first_ordering(self):
        providers = [
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
            {"key": "google:gemini-flash", "provider": "google", "model_id": "gemini-flash",
             "is_free": True, "api_key": "test", "endpoint": None,
             "deployment": "gemini-flash", "source": "test", "is_active": False},
            {"key": "openrouter:free", "provider": "openrouter", "model_id": "free",
             "is_free": True, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "free", "source": "test", "is_active": False},
        ]
        hide_model("openrouter:free")
        chain = build_chain(providers)
        assert chain[0]["is_free"] is True  # google:gemini-flash still first
        assert chain[0]["key"] == "google:gemini-flash"
        assert chain[1]["key"] == "openai:gpt-4o"


# ── Bridge integration ──────────────────────────────────────────────────────

class TestBridgeHiddenModels:
    def setup_method(self):
        _reset_state()

    def test_bridge_get_working_models_excludes_hidden(self):
        from swarm.switcher.bridge import SwitcherBridge
        bridge = SwitcherBridge()
        bridge._initialized = True
        bridge._chain = [
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
            {"key": "openrouter:free", "provider": "openrouter", "model_id": "free",
             "is_free": True, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "free", "source": "test", "is_active": False},
        ]

        hide_model("openai:gpt-4o")

        with patch("swarm.switcher.bridge.is_hidden", side_effect=lambda k: k == "openai:gpt-4o"), \
             patch("swarm.switcher.bridge.is_depleted", return_value=False), \
             patch("swarm.switcher.bridge.detect_task", return_value="general"), \
             patch("swarm.switcher.bridge._load_health_cache", return_value={}), \
             patch("swarm.switcher.bridge._save_health_cache"):
            # Mock _get_health to return healthy for both
            bridge._health_cache = {
                "openai:gpt-4o": (True, "healthy"),
                "openrouter:free": (True, "healthy"),
            }
            bridge._last_health_check = 9999999999  # force cache hit
            working = bridge.get_working_models()

        keys = [m[0] for m in working]
        assert "openai:gpt-4o" not in keys
        assert "openrouter:free" in keys

    def test_bridge_get_model_chain_excludes_hidden(self):
        from swarm.switcher.bridge import SwitcherBridge
        bridge = SwitcherBridge()
        bridge._initialized = True
        bridge._chain = [
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
            {"key": "openrouter:free", "provider": "openrouter", "model_id": "free",
             "is_free": True, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "free", "source": "test", "is_active": False},
        ]

        hide_model("openai:gpt-4o")

        with patch("swarm.switcher.bridge.is_hidden", side_effect=lambda k: k == "openai:gpt-4o"), \
             patch("swarm.switcher.bridge.is_depleted", return_value=False), \
             patch("swarm.switcher.bridge.detect_task", return_value="general"):
            bridge._health_cache = {
                "openai:gpt-4o": (True, "healthy"),
                "openrouter:free": (True, "healthy"),
            }
            bridge._last_health_check = 9999999999
            chain = bridge.get_model_chain("best")

        assert "openai:gpt-4o" not in chain
        assert "openrouter:free" in chain


# ── State persistence ───────────────────────────────────────────────────────

class TestHiddenPersistence:
    def setup_method(self):
        _reset_state()

    def test_hidden_survives_state_reload(self):
        hide_model("openrouter:gpt-4o")
        # Simulate reload
        hidden = get_hidden_models()
        assert "openrouter:gpt-4o" in hidden

    def test_hidden_independent_of_depleted(self):
        from swarm.switcher.switcher import mark_depleted, is_depleted
        hide_model("openrouter:gpt-4o")
        mark_depleted("openrouter:gpt-4o", "test", cooldown_minutes=5)
        assert is_hidden("openrouter:gpt-4o") is True
        assert is_depleted("openrouter:gpt-4o") is True
        # Unhide doesn't affect depleted
        unhide_model("openrouter:gpt-4o")
        assert is_hidden("openrouter:gpt-4o") is False
        assert is_depleted("openrouter:gpt-4o") is True

    def test_default_state_has_hidden_key(self):
        state = load_state()
        assert "hidden" in state
        assert isinstance(state["hidden"], list)

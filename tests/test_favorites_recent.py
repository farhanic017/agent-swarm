"""Tests for favorites, recent, and model selector features."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from swarm.switcher.switcher import (
    toggle_favorite,
    set_favorite,
    unset_favorite,
    get_favorites,
    is_favorite,
    track_recent,
    get_recent,
    load_state,
    save_state,
    discover_providers,
    build_chain,
    check_all_parallel,
    _load_health_cache,
    _save_health_cache,
    is_depleted,
    score_model,
    get_model_specialty,
    detect_task,
)
from swarm.core.model_selector_html import render_model_selector


# ── Helpers ──────────────────────────────────────────────────────────────────

def _reset_state():
    save_state({"active": {}, "depleted": {}, "history": [], "last_switch": None, "hidden": [], "favorites": [], "recent": []})


# ── Favorites CRUD ──────────────────────────────────────────────────────────

class TestToggleFavorite:
    def setup_method(self):
        _reset_state()

    def test_toggle_adds_fav(self):
        result = toggle_favorite("openrouter:gpt-4o")
        assert result is True
        assert "openrouter:gpt-4o" in get_favorites()

    def test_toggle_removes_fav(self):
        set_favorite("openrouter:gpt-4o")
        result = toggle_favorite("openrouter:gpt-4o")
        assert result is False
        assert "openrouter:gpt-4o" not in get_favorites()

    def test_toggle_idempotent_cycle(self):
        toggle_favorite("openrouter:gpt-4o")
        toggle_favorite("openrouter:gpt-4o")
        assert get_favorites() == []

    def test_toggle_records_history(self):
        toggle_favorite("openrouter:gpt-4o")
        toggle_favorite("openrouter:gpt-4o")
        state = load_state()
        history = state.get("history", [])
        assert any(h["model"] == "openrouter:gpt-4o" and h["action"] == "favorited" for h in history)
        assert any(h["model"] == "openrouter:gpt-4o" and h["action"] == "unfavorited" for h in history)


class TestSetUnsetFavorite:
    def setup_method(self):
        _reset_state()

    def test_set_favorite(self):
        set_favorite("openai:gpt-4o")
        assert is_favorite("openai:gpt-4o")

    def test_set_favorite_idempotent(self):
        set_favorite("openai:gpt-4o")
        set_favorite("openai:gpt-4o")
        assert get_favorites().count("openai:gpt-4o") == 1

    def test_unset_favorite(self):
        set_favorite("openai:gpt-4o")
        unset_favorite("openai:gpt-4o")
        assert not is_favorite("openai:gpt-4o")

    def test_unset_nonexistent_no_error(self):
        unset_favorite("nonexistent:model")  # should not raise

    def test_multiple_favorites(self):
        set_favorite("openrouter:gpt-4o")
        set_favorite("azure:gpt-4o")
        set_favorite("openai:gpt-4o-mini")
        favs = get_favorites()
        assert len(favs) == 3

    def test_get_favorites_returns_copy(self):
        set_favorite("openrouter:gpt-4o")
        favs = get_favorites()
        favs.append("fake:model")
        assert "fake:model" not in get_favorites()


class TestIsFavorite:
    def setup_method(self):
        _reset_state()

    def test_is_favorite_true(self):
        set_favorite("openrouter:gpt-4o")
        assert is_favorite("openrouter:gpt-4o") is True

    def test_is_favorite_false(self):
        assert is_favorite("openrouter:gpt-4o") is False

    def test_default_empty(self):
        assert get_favorites() == []


# ── Recent Models ────────────────────────────────────────────────────────────

class TestTrackRecent:
    def setup_method(self):
        _reset_state()

    def test_track_recent_adds_model(self):
        track_recent("openrouter:gpt-4o")
        recent = get_recent()
        assert "openrouter:gpt-4o" in recent

    def test_track_recent_most_recent_first(self):
        track_recent("openrouter:gpt-4o")
        track_recent("azure:gpt-4o")
        track_recent("openai:gpt-4o-mini")
        recent = get_recent()
        assert recent[0] == "openai:gpt-4o-mini"
        assert recent[-1] == "openrouter:gpt-4o"

    def test_track_recent_moves_to_front(self):
        track_recent("openrouter:gpt-4o")
        track_recent("azure:gpt-4o")
        track_recent("openrouter:gpt-4o")  # re-track
        recent = get_recent()
        assert recent[0] == "openrouter:gpt-4o"
        assert recent.count("openrouter:gpt-4o") == 1  # no duplicates

    def test_track_recent_max_10(self):
        for i in range(15):
            track_recent(f"provider:model-{i}")
        recent = get_recent()
        assert len(recent) == 10
        assert recent[0] == "provider:model-14"  # most recent

    def test_track_recent_records_history(self):
        track_recent("openrouter:gpt-4o")
        state = load_state()
        history = state.get("history", [])
        assert any(h["model"] == "openrouter:gpt-4o" and h["action"] == "recent" for h in history)

    def test_default_empty(self):
        assert get_recent() == []


# ── Model Selector HTML ─────────────────────────────────────────────────────

class TestModelSelectorHTML:
    def test_renders_valid_html(self, tmp_path):
        output = tmp_path / "selector.html"
        payload = {
            "models": [
                {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
                 "is_free": False, "is_active": True, "is_fav": False, "is_hidden": False,
                 "is_depleted": False, "healthy": True, "health_msg": "healthy",
                 "specialty": "coding", "score": 155},
            ],
            "favorites": [], "recent": [], "hidden": [],
            "active": "openai:gpt-4o", "task": "coding",
            "total": 1, "healthy": 1,
        }
        render_model_selector(str(output), payload)
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "Model Selector" in html
        assert "openai:gpt-4o" in html
        assert "All Models" in html
        assert "Favorites" in html
        assert "Recent" in html
        assert "Free" in html
        assert "Hidden" in html
        assert '__PAYLOAD__' not in html  # placeholder replaced

    def test_empty_models(self, tmp_path):
        output = tmp_path / "selector.html"
        payload = {
            "models": [], "favorites": [], "recent": [], "hidden": [],
            "active": None, "task": "general", "total": 0, "healthy": 0,
        }
        render_model_selector(str(output), payload)
        html = output.read_text(encoding="utf-8")
        assert "Model Selector" in html
        assert '"models": []' in html

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "sub" / "dir" / "selector.html"
        payload = {
            "models": [], "favorites": [], "recent": [], "hidden": [],
            "active": None, "task": "general", "total": 0, "healthy": 0,
        }
        render_model_selector(str(output), payload)
        assert output.exists()


# ── Favorites + Hidden interaction ──────────────────────────────────────────

class TestFavoritesHiddenInteraction:
    def setup_method(self):
        _reset_state()

    def test_can_fav_and_hide_same_model(self):
        set_favorite("openrouter:gpt-4o")
        from swarm.switcher.switcher import hide_model
        hide_model("openrouter:gpt-4o")
        assert is_favorite("openrouter:gpt-4o")
        from swarm.switcher.switcher import is_hidden
        assert is_hidden("openrouter:gpt-4o")

    def test_unhide_preserves_fav(self):
        from swarm.switcher.switcher import hide_model, unhide_model
        set_favorite("openrouter:gpt-4o")
        hide_model("openrouter:gpt-4o")
        unhide_model("openrouter:gpt-4o")
        assert is_favorite("openrouter:gpt-4o")
        from swarm.switcher.switcher import is_hidden
        assert not is_hidden("openrouter:gpt-4o")

    def test_unfav_preserves_hidden(self):
        from swarm.switcher.switcher import hide_model
        set_favorite("openrouter:gpt-4o")
        hide_model("openrouter:gpt-4o")
        unset_favorite("openrouter:gpt-4o")
        assert not is_favorite("openrouter:gpt-4o")
        from swarm.switcher.switcher import is_hidden
        assert is_hidden("openrouter:gpt-4o")


# ── State persistence ───────────────────────────────────────────────────────

class TestStatePersistence:
    def setup_method(self):
        _reset_state()

    def test_favorites_survive_reload(self):
        set_favorite("openrouter:gpt-4o")
        favs = get_favorites()
        assert "openrouter:gpt-4o" in favs

    def test_recent_survive_reload(self):
        track_recent("openrouter:gpt-4o")
        recent = get_recent()
        assert "openrouter:gpt-4o" in recent

    def test_default_state_has_all_keys(self):
        state = load_state()
        assert "favorites" in state
        assert "recent" in state
        assert "hidden" in state
        assert isinstance(state["favorites"], list)
        assert isinstance(state["recent"], list)
        assert isinstance(state["hidden"], list)


# ── Favorites in chain (should NOT filter — favorites are a UI feature only) ──

class TestFavoritesDoNotFilterChain:
    def setup_method(self):
        _reset_state()

    def test_favorites_not_excluded_from_chain(self):
        providers = [
            {"key": "openai:gpt-4o", "provider": "openai", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://api.openai.com/v1",
             "deployment": "gpt-4o", "source": "test", "is_active": False},
        ]
        set_favorite("openai:gpt-4o")
        chain = build_chain(providers)
        assert len(chain) == 1
        assert chain[0]["key"] == "openai:gpt-4o"

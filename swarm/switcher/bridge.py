"""SwitcherBridge — connects auto-model-switcher health/rotation with the swarm.

The bridge:
  1. Discovers all models from configs + env via the auto-model-switcher
  2. Health-checks all models in parallel (<2s)
  3. Scores by task (coding/chat/reasoning/general)
  4. Builds a sorted fallback chain for the orchestrator
  5. Manages cooldowns with Retry-After support (persistent across sessions)
  6. Auto-recovers depleted models when their cooldown expires
  7. (NEW) Context-aware switching — injects consciousness summary into
     the switch context so replacement models know what happened before
"""

from __future__ import annotations
import time
import json
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from swarm.core.consciousness import Consciousness

from swarm.switcher.switcher import (
    discover_providers,
    discover_local_models,
    build_chain as _build_chain,
    check_all_parallel,
    score_model,
    detect_task,
    get_model_specialty,
    set_active,
    get_active,
    mark_depleted,
    mark_recovered,
    is_depleted,
    is_hidden,
    get_hidden_models,
    hide_model,
    unhide_model,
    toggle_favorite,
    set_favorite,
    unset_favorite,
    get_favorites,
    is_favorite,
    track_recent,
    get_recent,
    load_state,
    save_state,
    save_context,
    get_recovery_eta,
    _load_health_cache,
    _save_health_cache,
    log,
    STATE_DIR,
)

STATE_DIR.mkdir(parents=True, exist_ok=True)
_CHAIN_CACHE_FILE = STATE_DIR / "bridge_chain.json"


class SwitcherBridge:
    """Zero-config model health & rotation for the swarm orchestrator."""

    def __init__(self, consciousness: Optional["Consciousness"] = None):
        self._initialized = False
        self._consciousness = consciousness
        self._chain: list[dict] = []
        self._health_cache: dict = {}
        self._last_health_check: float = 0
        self._health_ttl: float = 30.0  # re-check every 30s (faster than switcher's 120s)
        self._task_cache: str = "general"
        self._last_switch_time: float = 0
        self._switch_cooldown: float = 10.0  # don't re-switch more than once per 10s
        self._switch_history: list[dict] = []  # in-memory switch trace for this session

    # ── Initialization ───────────────────────────────────────────────────

    def _ensure_discovered(self):
        if not self._initialized:
            self._discover()
            self._initialized = True

    def _discover(self):
        providers = discover_providers()
        if not providers:
            from swarm.switcher.switcher import discover_from_env
            discover_from_env(providers)
        self._chain = _build_chain(providers)
        log(f"Bridge: discovered {len(self._chain)} models")

    def re_discover(self):
        """Force re-discovery of all models (e.g. config changed)."""
        self._initialized = False
        self._chain = []
        self._health_cache = {}
        self._ensure_discovered()

    # ── Health Checks ────────────────────────────────────────────────────

    def _get_health(self) -> dict:
        now = time.time()
        if now - self._last_health_check < self._health_ttl and self._health_cache:
            return self._health_cache

        cached = _load_health_cache()
        fresh = check_all_parallel(self._chain, cached_health=cached)
        _save_health_cache(fresh)

        self._health_cache = fresh
        self._last_health_check = now
        return fresh

    def get_working_models(self, include_depleted: bool = False) -> list[tuple[str, int, str]]:
        """Return (model_ref, score, status_msg) for all healthy models, scored by task.

        When include_depleted=True, depleted models are included with reduced scores
        so the fallback chain always has candidates available.
        Hidden models are always excluded.
        """
        self._ensure_discovered()
        health = self._get_health()
        self._task_cache = detect_task()
        task = self._task_cache

        scored = []
        for p in self._chain:
            key = p["key"]
            if is_hidden(key):
                continue
            depleted = is_depleted(key)
            if depleted and not include_depleted:
                continue
            h = health.get(key)
            if not h or not h[0]:
                if not depleted or not include_depleted:
                    continue
                # Depleted model with no health data — give it a minimal score
                # so it can still serve as a last-resort fallback
                scored.append((1, key, "depleted-no-health"))
                continue
            s = score_model(p, h, task)
            if depleted:
                s = max(1, s // 4)  # penalize but don't eliminate
            if s > 0:
                scored.append((s, key, h[1]))

        scored.sort(key=lambda x: -x[0])
        return [(k, s, m) for s, k, m in scored]

    def get_model_chain(self, preference: str = "best") -> list[str]:
        """Return a priority-sorted list of model refs for fallback."""
        working = self.get_working_models()
        if not working:
            # Last resort: include depleted models so the chain is never empty
            working = self.get_working_models(include_depleted=True)
        if not working:
            return []

        if preference == "best":
            return [m[0] for m in working]
        elif preference == "cheap":
            cheap = [m for m in working if m[0] >= 100]  # free models score 150+
            if cheap:
                return [m[0] for m in cheap]
            return [m[0] for m in working]
        return [m[0] for m in working]

    def get_working_models_for_task(self, task_type: str, include_depleted: bool = False) -> list[tuple[str, int, str]]:
        """Return (model_ref, score, status_msg) for healthy models, scored for a specific task.
        Hidden models are always excluded.
        """
        self._ensure_discovered()
        health = self._get_health()
        self._task_cache = task_type

        scored = []
        for p in self._chain:
            key = p["key"]
            if is_hidden(key):
                continue
            depleted = is_depleted(key)
            if depleted and not include_depleted:
                continue
            h = health.get(key)
            if not h or not h[0]:
                if not depleted or not include_depleted:
                    continue
                scored.append((1, key, "depleted-no-health"))
                continue
            s = score_model(p, h, task_type)
            if depleted:
                s = max(1, s // 4)
            if s > 0:
                scored.append((s, key, h[1]))

        scored.sort(key=lambda x: -x[0])
        return [(k, s, m) for s, k, m in scored]

    def get_model_chain_for_task(self, task_type: str, preference: str = "best") -> list[str]:
        """Return a model chain scored specifically for the given task type.

        Task types: coding, chat, reasoning, general.
        Each agent gets a chain where models strong at that task rank highest.
        """
        working = self.get_working_models_for_task(task_type)
        if not working:
            # Last resort: include depleted models so the chain is never empty
            working = self.get_working_models_for_task(task_type, include_depleted=True)
        if not working:
            return self.get_model_chain(preference)

        if preference == "best":
            return [m[0] for m in working]
        elif preference == "cheap":
            cheap = [m for m in working if m[0] >= 100]
            if cheap:
                return [m[0] for m in cheap]
            return [m[0] for m in working]
        return [m[0] for m in working]

    def record_success(self, model_ref: str):
        """Mark a model as healthy/recovered after a successful call."""
        if model_ref:
            mark_recovered(model_ref)

    def record_failure(self, model_ref: str, error: str):
        """Mark a model as failed and notify the switcher state.

        Parses Retry-After headers from error messages.
        """
        status_code = ""
        retry_seconds = None

        if "429" in error:
            status_code = "429"
        elif "402" in error:
            status_code = "402"
        elif "401" in error or "403" in error:
            status_code = "auth"
        elif "400" in error:
            status_code = "400"

        m = __import__("re").search(r"retry in (\d+)s", error)
        if not m:
            m = __import__("re").search(r"retry[_ -]?after[:\s]+(\d+)", error, __import__("re").IGNORECASE)
        if m:
            retry_seconds = int(m.group(1))

        cooldown = 30
        if retry_seconds:
            cooldown = max(1, retry_seconds // 60)
        elif status_code == "429":
            cooldown = 5
        elif status_code == "402":
            cooldown = 60
        elif status_code == "400":
            cooldown = 2  # short cooldown — may be a transient format issue
        elif status_code == "auth":
            cooldown = 60  # auth errors need longer cooldown

        mark_depleted(model_ref, error[:200], cooldown_minutes=cooldown)

        if status_code:
            log(f"Bridge: {model_ref} failed ({status_code}), cooldown {cooldown}min")
            return
        if cooldown > 1:
            log(f"Bridge: {model_ref} failed ({error[:60]}), cooldown {cooldown}min")

    def is_healthy(self, model_ref: str) -> bool:
        """Check if a model is healthy (not depleted, passed health check)."""
        if is_depleted(model_ref):
            return False
        health = self._get_health()
        h = health.get(model_ref)
        if h and h[0]:
            return True
        return False

    def get_best_model(self, preference: str = "best") -> Optional[str]:
        """Get the single best model ref for the detected task."""
        chain = self.get_model_chain(preference)
        return chain[0] if chain else None

    def get_task(self) -> str:
        self._ensure_discovered()
        self._task_cache = detect_task()
        return self._task_cache

    def get_active_model(self) -> Optional[str]:
        return get_active("opencode")

    def set_active_model(self, model_ref: str):
        set_active("opencode", model_ref)
        track_recent(model_ref)
        self._last_switch_time = time.time()

    def set_consciousness(self, consciousness: Consciousness):
        """Set the consciousness reference for context-aware switching."""
        self._consciousness = consciousness

    def switch_if_needed(self, current_model: str, error: str,
                         original_task: str = "", force: bool = False) -> Optional[str]:
        """Auto-rotate if current model failed. Returns new model or None.

        If a Consciousness hub is attached, generates a rich context summary
        so the replacement model knows what happened before and continues
        seamlessly without hallucinating.

        When force=True, bypasses the switch cooldown — used when the entire
        model chain is exhausted and we must find an alternative immediately.
        """
        now = time.time()
        if not force and now - self._last_switch_time < self._switch_cooldown:
            return None

        if is_depleted(current_model):
            pass
        else:
            self.record_failure(current_model, error)

        best = self.get_best_model()
        if not best or best == current_model:
            # Try with depleted models included as last resort
            all_models = self.get_working_models(include_depleted=True)
            best = next((m[0] for m in all_models if m[0] != current_model), None)
        if best and best != current_model:
            prev = current_model
            self.set_active_model(best)

            # Record switch in session history
            self._switch_history.append({
                "from": prev,
                "to": best,
                "reason": error[:200],
                "forced": force,
                "time": datetime.now().isoformat(),
            })

            summary = f"Switched from {prev} to {best}"
            if self._consciousness:
                try:
                    context = self._consciousness.get_full_context_for_switch(
                        original_task or error, max_events=50
                    )
                    summary = context
                except Exception:
                    summary = f"Switched from {prev} to {best}"

            save_context(prev, best, f"auto-rotate: {error[:80]}", summary)
            log(f"Bridge: auto-rotated {prev} -> {best} (consciousness context injected)")
            return best
        return None

    def get_all_models(self) -> list[dict]:
        self._ensure_discovered()
        return list(self._chain)

    def get_switch_history(self) -> list[dict]:
        """Return the in-memory switch history for this session."""
        return list(self._switch_history)

    def get_stats(self) -> dict:
        self._ensure_discovered()
        health = self._get_health()
        working = sum(1 for k, p in [(p["key"], p) for p in self._chain]
                      if health.get(k) and health[k][0] and not is_depleted(k))
        depleted = sum(1 for p in self._chain if is_depleted(p["key"]))
        return {
            "total": len(self._chain),
            "working": working,
            "depleted": depleted,
            "task": self._task_cache,
            "active": get_active("opencode"),
        }


def resolve_provider_and_model(model_ref: str, config) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse a model ref like 'azure:gpt-4o' or 'openrouter:openrouter/free'
    into (normalized_provider_name, model_id, api_key).

    Returns (None, None, None) if the ref cannot be resolved.
    """
    if ":" not in model_ref:
        return None, None, None

    prov_cfg, model_id = model_ref.split(":", 1)
    from swarm.config import normalize_provider_name
    norm = normalize_provider_name(prov_cfg)

    for cfg_name, pc in config.providers.items():
        if normalize_provider_name(cfg_name) == norm:
            return norm, model_id, pc.api_key

    return norm, model_id, None

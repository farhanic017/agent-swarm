"""Watchdog — background health monitor and automatic model rotation.

Inspired by the standalone auto-model-switcher's watch daemon. Periodically
checks all discovered models, marks unhealthy ones as depleted, auto-rotates
when the active model runs out of credits/tokens, and recovers models when
their cooldown expires.

Integrates with the swarm via SwitcherBridge and Consciousness for
context-aware switching.
"""

from __future__ import annotations

import asyncio
import time
import re
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from swarm.switcher.switcher import (
    discover_providers,
    build_chain,
    check_all_parallel,
    score_model,
    detect_task,
    mark_depleted,
    mark_recovered,
    is_depleted,
    get_active,
    set_active,
    load_state,
    save_context,
    detect_free_tier_gate,
    check_model,
    log,
)

if TYPE_CHECKING:
    from swarm.switcher.bridge import SwitcherBridge
    from swarm.core.consciousness import Consciousness


# Token exhaustion patterns — matched against provider error messages
TOKEN_EXHAUSTION_PATTERNS = [
    r"insufficient.?quota",
    r"quota.?exceeded",
    r"credit.?limit",
    r"0.?credits?.?remaining",
    r"out.?of.?credits",
    r"out.?of.?tokens",
    r"token.?limit.?exceeded",
    r"billing.?limit",
    r"payment.?required",
    r"buy.*token",
    r"purchase.*credit",
    r"add.*funds",
    r"free.?tier.?limit",
    r"rate.?limit.?exceeded",
]


def is_token_exhaustion(error_msg: str) -> bool:
    """Detect if an error indicates token/credit exhaustion (not transient rate-limit)."""
    msg = error_msg.lower()
    return any(re.search(p, msg) for p in TOKEN_EXHAUSTION_PATTERNS)


class Watchdog:
    """Background health monitor that auto-rotates models on failure.

    Usage:
        watchdog = Watchdog(bridge, consciousness)
        await watchdog.start(interval=120)  # check every 2 min
        # ... later ...
        await watchdog.stop()

    The watchdog:
    - Checks all models every `interval` seconds
    - Marks unhealthy models as depleted
    - Auto-rotates when the active model fails
    - Recovers depleted models when cooldown expires
    - Detects token/credit exhaustion patterns
    - Pushes events to Consciousness for orchestrator awareness
    """

    def __init__(
        self,
        bridge: "SwitcherBridge",
        consciousness: Optional["Consciousness"] = None,
        interval: int = 120,
    ):
        self.bridge = bridge
        self.consciousness = consciousness
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_check: float = 0
        self._check_count: int = 0
        self._rotation_count: int = 0
        self._recovery_count: int = 0

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    async def start(self, interval: Optional[int] = None):
        """Start the background watchdog loop."""
        if self.is_running:
            log("Watchdog: already running")
            return

        if interval is not None:
            self.interval = interval

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log(f"Watchdog: started (interval={self.interval}s)")

        if self.consciousness:
            await self.consciousness.push_progress(
                "watchdog",
                f"Health monitor started (every {self.interval}s)",
                {"interval": self.interval},
            )

    async def stop(self):
        """Stop the watchdog gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        log("Watchdog: stopped")

        if self.consciousness:
            await self.consciousness.push_progress(
                "watchdog",
                "Health monitor stopped",
                {
                    "checks": self._check_count,
                    "rotations": self._rotation_count,
                    "recoveries": self._recovery_count,
                },
            )

    async def check_now(self) -> dict:
        """Run a single health check cycle immediately. Returns status dict."""
        return await self._check_cycle()

    async def report_token_exhaustion(self, model_ref: str, error: str):
        """Called by the orchestrator when a provider reports token/credit exhaustion.

        This triggers immediate rotation instead of waiting for the next check cycle.
        """
        if not is_token_exhaustion(error):
            return None

        log(f"Watchdog: token exhaustion detected for {model_ref}: {error[:80]}")
        mark_depleted(model_ref, f"token_exhaustion: {error[:150]}", cooldown_minutes=60)

        if self.consciousness:
            await self.consciousness.push_error(
                "watchdog",
                f"Token/credit exhaustion on {model_ref}",
                {"model": model_ref, "error": error[:200]},
            )

        # Trigger immediate rotation
        return await self._rotate(model_ref, error)

    async def _run_loop(self):
        """Main watchdog loop — runs until stopped."""
        while self._running:
            try:
                await self._check_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log(f"Watchdog: check cycle error: {e}")
                if self.consciousness:
                    await self.consciousness.push_error("watchdog", f"Check cycle error: {e}")

            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

    async def _check_cycle(self) -> dict:
        """Run one full health check cycle."""
        self._check_count += 1
        self._last_check = time.time()

        # Force re-discovery to pick up new models
        self.bridge.re_discover()
        chain = self.bridge.get_all_models()

        if not chain:
            log("Watchdog: no models discovered")
            return {"status": "no_models", "checked": 0}

        # Parallel health check
        cached = {}
        try:
            from swarm.switcher.switcher import _load_health_cache
            cached = _load_health_cache()
        except Exception:
            pass

        health_results = check_all_parallel(chain, cached_health=cached)

        try:
            from swarm.switcher.switcher import _save_health_cache
            _save_health_cache(health_results)
        except Exception:
            pass

        task = detect_task()
        active_key = get_active("opencode")
        checked = 0
        new_depletions = []
        new_recoveries = []
        rotated = False

        for p in chain:
            key = p["key"]
            health = health_results.get(key)
            if not health:
                continue

            checked += 1
            healthy, msg = health

            # Detect free-tier gate
            if healthy and detect_free_tier_gate(p, msg):
                log(f"Watchdog: {key} free-tier gate detected ({msg})")
                mark_depleted(key, f"free-tier gate: {msg}", cooldown_minutes=60)
                new_depletions.append(key)
                if key == active_key:
                    rotated = True
                    await self._rotate(key, f"free-tier gate: {msg}")
                continue

            if not healthy:
                if not is_depleted(key):
                    cooldown = 30
                    if "429" in msg:
                        cooldown = 5
                    elif "402" in msg or "payment" in msg.lower():
                        cooldown = 60
                    elif is_token_exhaustion(msg):
                        cooldown = 60

                    mark_depleted(key, msg, cooldown_minutes=cooldown)
                    new_depletions.append(key)
                    log(f"Watchdog: {key} marked depleted ({msg[:60]})")

                    if key == active_key:
                        rotated = True
                        await self._rotate(key, msg)
            else:
                # Model is healthy — recover if previously depleted
                if is_depleted(key):
                    mark_recovered(key)
                    new_recoveries.append(key)
                    self._recovery_count += 1
                    log(f"Watchdog: {key} recovered ({msg[:60]})")

        result = {
            "status": "ok",
            "checked": checked,
            "depleted": len(new_depletions),
            "recovered": len(new_recoveries),
            "rotated": rotated,
            "active": active_key,
            "task": task,
            "timestamp": datetime.now().isoformat(),
        }

        if self.consciousness and (new_depletions or new_recoveries):
            await self.consciousness.push_state(
                "watchdog",
                result,
                "watchdog",
            )

        return result

    async def _rotate(self, failed_model: str, error: str) -> Optional[str]:
        """Find and switch to the best available model."""
        self._rotation_count += 1

        new_model = self.bridge.switch_if_needed(
            failed_model, error, force=True
        )

        if new_model:
            log(f"Watchdog: rotated {failed_model} -> {new_model}")

            # Update CLI config
            from swarm.switcher.switcher import update_opencode_config
            update_opencode_config(new_model)

            if self.consciousness:
                await self.consciousness.push_progress(
                    "watchdog",
                    f"Auto-rotated: {failed_model} -> {new_model}",
                    {
                        "previous": failed_model,
                        "new": new_model,
                        "reason": error[:100],
                    },
                )
        else:
            log(f"Watchdog: no alternative model found for {failed_model}")
            if self.consciousness:
                recovery = self._get_recovery_info()
                await self.consciousness.push_error(
                    "watchdog",
                    f"No alternative model for {failed_model}. All models may be depleted.",
                    {"recovery": recovery},
                )

        return new_model

    def _get_recovery_info(self) -> dict:
        """Get recovery ETA for depleted models."""
        from swarm.switcher.switcher import get_recovery_eta
        try:
            return get_recovery_eta()
        except Exception:
            return {}

    def get_status(self) -> dict:
        """Get current watchdog status."""
        return {
            "running": self.is_running,
            "interval": self.interval,
            "checks": self._check_count,
            "rotations": self._rotation_count,
            "recoveries": self._recovery_count,
            "last_check": self._last_check,
            "bridge_stats": self.bridge.get_stats(),
        }

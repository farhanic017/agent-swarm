"""Tests for the Watchdog health monitor and token exhaustion detection."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from swarm.switcher.watchdog import Watchdog, is_token_exhaustion
from swarm.providers.base import ProviderError


# ── Token exhaustion pattern detection ──────────────────────────────────────

class TestIsTokenExhaustion:
    def test_insufficient_quota(self):
        assert is_token_exhaustion("Error: insufficient quota for this request")

    def test_quota_exceeded(self):
        assert is_token_exhaustion("429: quota_exceeded - you have exceeded your quota")

    def test_payment_required(self):
        assert is_token_exhaustion("402 Payment Required")

    def test_buy_tokens(self):
        assert is_token_exhaustion("Please buy 10 tokens to continue")

    def test_purchase_credits(self):
        assert is_token_exhaustion("purchase more credits at openrouter.ai")

    def test_out_of_credits(self):
        assert is_token_exhaustion("Account has 0 credits remaining")

    def test_free_tier_limit(self):
        assert is_token_exhaustion("free tier limit reached for this model")

    def test_add_funds(self):
        assert is_token_exhaustion("add funds to your account to continue")

    def test_normal_error_not_exhaustion(self):
        assert not is_token_exhaustion("Connection refused")
        assert not is_token_exhaustion("Model not found (404)")
        assert not is_token_exhaustion("Internal server error (500)")
        assert not is_token_exhaustion("rate limited (429), retry in 30s")

    def test_empty_string(self):
        assert not is_token_exhaustion("")

    def test_case_insensitive(self):
        assert is_token_exhaustion("INSUFFICIENT QUOTA")
        assert is_token_exhaustion("Payment Required")
        assert is_token_exhaustion("BUY MORE TOKENS")


# ── ProviderError ───────────────────────────────────────────────────────────

class TestProviderError:
    def test_basic_error(self):
        err = ProviderError("test error", status_code=402, provider="openrouter", model="gpt-4o")
        assert str(err) == "test error"
        assert err.status_code == 402
        assert err.provider == "openrouter"
        assert err.model == "gpt-4o"
        assert err.is_exhaustion is False

    def test_exhaustion_error(self):
        err = ProviderError(
            "insufficient quota",
            status_code=402,
            provider="openrouter",
            model="gpt-4o",
            is_exhaustion=True,
            retry_after=60,
        )
        assert err.is_exhaustion is True
        assert err.retry_after == 60

    def test_defaults(self):
        err = ProviderError("something")
        assert err.status_code == 0
        assert err.provider == ""
        assert err.model == ""
        assert err.is_exhaustion is False
        assert err.retry_after is None

    def test_is_exception(self):
        err = ProviderError("test")
        assert isinstance(err, Exception)
        with pytest.raises(ProviderError):
            raise err


# ── Watchdog lifecycle ──────────────────────────────────────────────────────

class TestWatchdogLifecycle:
    def _make_bridge(self):
        bridge = MagicMock()
        bridge.re_discover = MagicMock()
        bridge.get_all_models = MagicMock(return_value=[])
        bridge.get_stats = MagicMock(return_value={
            "total": 0, "working": 0, "depleted": 0,
            "task": "general", "active": None,
        })
        bridge.switch_if_needed = MagicMock(return_value=None)
        bridge.is_healthy = MagicMock(return_value=True)
        return bridge

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=10)

        assert not w.is_running
        await w.start()
        assert w.is_running
        await w.stop()
        assert not w.is_running

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=10)

        await w.start()
        await w.start()  # should not error
        assert w.is_running
        await w.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=10)
        await w.stop()  # should not error

    @pytest.mark.asyncio
    async def test_status(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=60)

        status = w.get_status()
        assert status["running"] is False
        assert status["interval"] == 60
        assert status["checks"] == 0
        assert status["rotations"] == 0
        assert status["recoveries"] == 0

    @pytest.mark.asyncio
    async def test_check_now_empty(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=60)

        result = await w.check_now()
        assert result["status"] == "no_models"
        assert result["checked"] == 0


# ── Watchdog token exhaustion reporting ─────────────────────────────────────

class TestWatchdogTokenExhaustion:
    def _make_bridge(self):
        bridge = MagicMock()
        bridge.re_discover = MagicMock()
        bridge.get_all_models = MagicMock(return_value=[])
        bridge.get_stats = MagicMock(return_value={
            "total": 0, "working": 0, "depleted": 0,
            "task": "general", "active": None,
        })
        bridge.switch_if_needed = MagicMock(return_value="openai:gpt-4o")
        bridge.is_healthy = MagicMock(return_value=True)
        return bridge

    @pytest.mark.asyncio
    async def test_report_token_exhaustion_triggers_rotation(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=60)

        result = await w.report_token_exhaustion(
            "openrouter:gpt-4o", "402 Payment Required: insufficient quota"
        )
        assert result == "openai:gpt-4o"
        assert w._rotation_count == 1
        bridge.switch_if_needed.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_non_exhaustion_ignored(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=60)

        result = await w.report_token_exhaustion(
            "openrouter:gpt-4o", "Connection refused"
        )
        assert result is None
        assert w._rotation_count == 0
        bridge.switch_if_needed.assert_not_called()

    @pytest.mark.asyncio
    async def test_report_exhaustion_marks_depleted(self):
        bridge = self._make_bridge()
        w = Watchdog(bridge=bridge, interval=60)

        with patch("swarm.switcher.watchdog.mark_depleted") as mock_deplete:
            await w.report_token_exhaustion(
                "openrouter:gpt-4o", "402: 0 credits remaining"
            )
            mock_deplete.assert_called_once()
            args = mock_deplete.call_args
            assert args[0][0] == "openrouter:gpt-4o"
            assert args[1]["cooldown_minutes"] == 60

    @pytest.mark.asyncio
    async def test_report_exhaustion_with_consciousness(self):
        bridge = self._make_bridge()
        consciousness = AsyncMock()
        w = Watchdog(bridge=bridge, consciousness=consciousness, interval=60)

        await w.report_token_exhaustion(
            "openrouter:gpt-4o", "402: out of credits"
        )
        consciousness.push_error.assert_called_once()
        consciousness.push_progress.assert_called()  # rotation event


# ── Watchdog check cycle ───────────────────────────────────────────────────

class TestWatchdogCheckCycle:
    def _make_bridge_with_models(self, models):
        bridge = MagicMock()
        bridge.re_discover = MagicMock()
        bridge.get_all_models = MagicMock(return_value=models)
        bridge.get_stats = MagicMock(return_value={
            "total": len(models), "working": len(models), "depleted": 0,
            "task": "general", "active": None,
        })
        bridge.switch_if_needed = MagicMock(return_value=None)
        bridge.is_healthy = MagicMock(return_value=True)
        return bridge

    @pytest.mark.asyncio
    async def test_check_cycle_with_healthy_models(self):
        models = [
            {"key": "azure:gpt-4o", "provider": "azure", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://test.openai.azure.com",
             "deployment": "gpt-4o", "source": "test"},
        ]
        bridge = self._make_bridge_with_models(models)
        w = Watchdog(bridge=bridge, interval=60)

        with patch("swarm.switcher.watchdog.check_all_parallel") as mock_check, \
             patch("swarm.switcher.watchdog.is_depleted", return_value=False), \
             patch("swarm.switcher.watchdog.detect_free_tier_gate", return_value=False), \
             patch("swarm.switcher.watchdog.detect_task", return_value="general"), \
             patch("swarm.switcher.watchdog.get_active", return_value=None), \
             patch("swarm.switcher.switcher._load_health_cache", return_value={}), \
             patch("swarm.switcher.switcher._save_health_cache"):
            mock_check.return_value = {"azure:gpt-4o": (True, "healthy")}
            result = await w.check_now()

        assert result["status"] == "ok"
        assert result["checked"] == 1
        assert result["depleted"] == 0
        assert result["recovered"] == 0
        assert w._check_count == 1

    @pytest.mark.asyncio
    async def test_check_cycle_marks_unhealthy_depleted(self):
        models = [
            {"key": "openrouter:gpt-4o", "provider": "openrouter", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "gpt-4o", "source": "test"},
        ]
        bridge = self._make_bridge_with_models(models)
        w = Watchdog(bridge=bridge, interval=60)

        with patch("swarm.switcher.watchdog.check_all_parallel") as mock_check, \
             patch("swarm.switcher.watchdog.is_depleted", return_value=False), \
             patch("swarm.switcher.watchdog.detect_free_tier_gate", return_value=False), \
             patch("swarm.switcher.watchdog.detect_task", return_value="general"), \
             patch("swarm.switcher.watchdog.get_active", return_value=None), \
             patch("swarm.switcher.watchdog.mark_depleted") as mock_deplete, \
             patch("swarm.switcher.switcher._load_health_cache", return_value={}), \
             patch("swarm.switcher.switcher._save_health_cache"):
            mock_check.return_value = {"openrouter:gpt-4o": (False, "rate limited (429)")}
            result = await w.check_now()

        assert result["depleted"] == 1
        mock_deplete.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_cycle_recovers_depleted(self):
        models = [
            {"key": "openrouter:gpt-4o", "provider": "openrouter", "model_id": "gpt-4o",
             "is_free": False, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "gpt-4o", "source": "test"},
        ]
        bridge = self._make_bridge_with_models(models)
        w = Watchdog(bridge=bridge, interval=60)

        with patch("swarm.switcher.watchdog.check_all_parallel") as mock_check, \
             patch("swarm.switcher.watchdog.is_depleted", return_value=True), \
             patch("swarm.switcher.watchdog.detect_free_tier_gate", return_value=False), \
             patch("swarm.switcher.watchdog.detect_task", return_value="general"), \
             patch("swarm.switcher.watchdog.get_active", return_value=None), \
             patch("swarm.switcher.watchdog.mark_recovered") as mock_recover, \
             patch("swarm.switcher.switcher._load_health_cache", return_value={}), \
             patch("swarm.switcher.switcher._save_health_cache"):
            mock_check.return_value = {"openrouter:gpt-4o": (True, "healthy")}
            result = await w.check_now()

        assert result["recovered"] == 1
        mock_recover.assert_called_once_with("openrouter:gpt-4o")
        assert w._recovery_count == 1


# ── Watchdog rotation on active model failure ──────────────────────────────

class TestWatchdogRotation:
    @pytest.mark.asyncio
    async def test_rotation_on_active_model_failure(self):
        models = [
            {"key": "openrouter:free", "provider": "openrouter", "model_id": "free",
             "is_free": True, "api_key": "test", "endpoint": "https://openrouter.ai/api/v1",
             "deployment": "free", "source": "test"},
        ]
        bridge = MagicMock()
        bridge.re_discover = MagicMock()
        bridge.get_all_models = MagicMock(return_value=models)
        bridge.get_stats = MagicMock(return_value={
            "total": 1, "working": 0, "depleted": 1,
            "task": "general", "active": "openrouter:free",
        })
        bridge.switch_if_needed = MagicMock(return_value="azure:gpt-4o")
        bridge.is_healthy = MagicMock(return_value=False)

        w = Watchdog(bridge=bridge, interval=60)

        with patch("swarm.switcher.watchdog.check_all_parallel") as mock_check, \
             patch("swarm.switcher.watchdog.is_depleted", return_value=False), \
             patch("swarm.switcher.watchdog.detect_free_tier_gate", return_value=False), \
             patch("swarm.switcher.watchdog.detect_task", return_value="general"), \
             patch("swarm.switcher.watchdog.get_active", return_value="openrouter:free"), \
             patch("swarm.switcher.watchdog.mark_depleted"), \
             patch("swarm.switcher.switcher.update_opencode_config"), \
             patch("swarm.switcher.switcher._load_health_cache", return_value={}), \
             patch("swarm.switcher.switcher._save_health_cache"):
            mock_check.return_value = {"openrouter:free": (False, "0 credits remaining")}
            result = await w.check_now()

        assert result["rotated"] is True
        assert w._rotation_count == 1
        bridge.switch_if_needed.assert_called_once()

    @pytest.mark.asyncio
    async def test_rotation_with_consciousness(self):
        bridge = MagicMock()
        bridge.re_discover = MagicMock()
        bridge.get_all_models = MagicMock(return_value=[])
        bridge.get_stats = MagicMock(return_value={
            "total": 0, "working": 0, "depleted": 0,
            "task": "general", "active": None,
        })
        bridge.switch_if_needed = MagicMock(return_value="azure:gpt-4o")

        consciousness = AsyncMock()
        w = Watchdog(bridge=bridge, consciousness=consciousness, interval=60)

        result = await w._rotate("openrouter:free", "0 credits remaining")
        assert result == "azure:gpt-4o"
        consciousness.push_progress.assert_called()

    @pytest.mark.asyncio
    async def test_rotation_no_alternative(self):
        bridge = MagicMock()
        bridge.switch_if_needed = MagicMock(return_value=None)

        consciousness = AsyncMock()
        w = Watchdog(bridge=bridge, consciousness=consciousness, interval=60)

        result = await w._rotate("openrouter:free", "0 credits remaining")
        assert result is None
        consciousness.push_error.assert_called()


# ── OpenRouter provider exhaustion ──────────────────────────────────────────

class TestOpenRouterExhaustion:
    @pytest.mark.asyncio
    async def test_402_raises_provider_error(self):
        from swarm.providers.openrouter import OpenRouterProvider
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.text = '{"error": "Payment required"}'
        mock_response.headers = {}

        with patch.object(provider._client, "post", return_value=mock_response):
            with pytest.raises(ProviderError) as exc_info:
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="openai/gpt-4o",
                )
            assert exc_info.value.is_exhaustion is True
            assert exc_info.value.status_code == 402
            assert exc_info.value.provider == "openrouter"
            assert exc_info.value.model == "openai/gpt-4o"

    @pytest.mark.asyncio
    async def test_429_with_exhaustion_pattern_raises(self):
        from swarm.providers.openrouter import OpenRouterProvider
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = '{"error": "Insufficient quota. Please purchase more credits."}'
        mock_response.headers = {}

        with patch.object(provider._client, "post", return_value=mock_response):
            with pytest.raises(ProviderError) as exc_info:
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="openai/gpt-4o",
                )
            assert exc_info.value.is_exhaustion is True
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_normal_429_retries_then_raises(self):
        from swarm.providers.openrouter import OpenRouterProvider
        provider = OpenRouterProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = '{"error": "rate limited"}'
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock(side_effect=Exception("429"))

        with patch.object(provider._client, "post", return_value=mock_response):
            with pytest.raises(Exception):
                await provider.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    model="openai/gpt-4o",
                )


# ── Orchestrator integration ───────────────────────────────────────────────

class TestOrchestratorWatchdogIntegration:
    def test_orchestrator_has_watchdog(self):
        """Verify the orchestrator initializes a watchdog."""
        from swarm.core.orchestrator import Orchestrator
        from swarm.config import SwarmConfig

        config = SwarmConfig()
        orch = Orchestrator(config=config)
        assert hasattr(orch, "watchdog")
        assert isinstance(orch.watchdog, Watchdog)
        assert orch.watchdog.bridge is orch.switcher_bridge
        assert orch.watchdog.consciousness is orch.consciousness

    def test_orchestrator_imports_provider_error(self):
        """Verify the orchestrator imports ProviderError for exhaustion detection."""
        from swarm.core.orchestrator import Orchestrator
        assert hasattr(Orchestrator, "_chat_with_fallback")

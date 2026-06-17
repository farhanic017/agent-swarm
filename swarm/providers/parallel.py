"""
Parallel Multi-Provider Execution System.

Enables multiple providers to work simultaneously for:
- Load balancing across providers
- Failover when one provider is rate-limited
- Parallel execution for faster results
- Provider health monitoring
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from swarm.providers.base import LLMProvider, LLMResponse
from swarm.config import SwarmConfig, normalize_provider_name


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    RATE_LIMITED = "rate_limited"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    provider_name: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_check: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    last_error: str = ""
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def is_usable(self) -> bool:
        return self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED, ProviderStatus.UNKNOWN)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider_name,
            "status": self.status.value,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
        }


@dataclass
class ProviderPool:
    config: SwarmConfig
    health: dict[str, ProviderHealth] = field(default_factory=dict)
    _providers: dict[str, LLMProvider] = field(default_factory=dict)

    def _get_provider(self, name: str) -> Optional[LLMProvider]:
        if name in self._providers:
            return self._providers[name]
        normalized = normalize_provider_name(name)
        if normalized in self._providers:
            return self._providers[normalized]
        return None

    def _ensure_provider(self, name: str) -> Optional[LLMProvider]:
        provider = self._get_provider(name)
        if provider:
            return provider
        from swarm.providers.factory import _build_provider
        pc = self.config.providers.get(name)
        if not pc:
            for cfg_name in self.config.providers:
                if normalize_provider_name(cfg_name) == normalize_provider_name(name):
                    pc = self.config.providers[cfg_name]
                    break
        if pc:
            provider = _build_provider(normalize_provider_name(name), pc.api_key, pc.endpoint, pc.models)
            if provider:
                self._providers[name] = provider
                self._providers[normalize_provider_name(name)] = provider
                if name not in self.health:
                    self.health[name] = ProviderHealth(provider_name=name)
                if normalize_provider_name(name) not in self.health:
                    self.health[normalize_provider_name(name)] = ProviderHealth(provider_name=normalize_provider_name(name))
        return provider

    def get_healthy_providers(self, capability: str = "chat") -> list[str]:
        healthy = []
        for name in self.config.providers:
            self._ensure_provider(name)
            h = self.health.get(name, ProviderHealth(provider_name=name))
            if h.is_usable:
                healthy.append(name)
        return healthy

    def get_best_provider(self, capability: str = "chat") -> Optional[str]:
        healthy = self.get_healthy_providers(capability)
        if not healthy:
            return None
        def score(name):
            h = self.health.get(name, ProviderHealth(provider_name=name))
            latency_penalty = min(h.avg_latency_ms / 1000, 1.0) if h.avg_latency_ms > 0 else 0
            return h.success_rate - latency_penalty
        healthy.sort(key=score, reverse=True)
        return healthy[0]

    def record_success(self, provider_name: str, latency_ms: float):
        if provider_name not in self.health:
            self.health[provider_name] = ProviderHealth(provider_name=provider_name)
        h = self.health[provider_name]
        h.success_count += 1
        h.consecutive_failures = 0
        h.status = ProviderStatus.HEALTHY
        if h.avg_latency_ms == 0:
            h.avg_latency_ms = latency_ms
        else:
            h.avg_latency_ms = (h.avg_latency_ms * 0.7) + (latency_ms * 0.3)
        h.last_check = time.time()

    def record_failure(self, provider_name: str, error: str, is_rate_limit: bool = False):
        if provider_name not in self.health:
            self.health[provider_name] = ProviderHealth(provider_name=provider_name)
        h = self.health[provider_name]
        h.failure_count += 1
        h.consecutive_failures += 1
        h.last_error = error
        h.last_check = time.time()
        if is_rate_limit:
            h.status = ProviderStatus.RATE_LIMITED
        elif h.consecutive_failures >= 3:
            h.status = ProviderStatus.DOWN
        elif h.consecutive_failures >= 1:
            h.status = ProviderStatus.DEGRADED

    def get_health_summary(self) -> dict[str, Any]:
        return {
            name: h.to_dict() for name, h in self.health.items()
        }


class ParallelProvider:
    """Execute requests across multiple providers in parallel."""

    def __init__(self, pool: ProviderPool, max_parallel: int = 3):
        self.pool = pool
        self.max_parallel = max_parallel

    async def chat_with_failover(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        providers: list[str] | None = None,
        preferred_provider: str | None = None,
    ) -> LLMResponse:
        if preferred_provider:
            provider_names = [preferred_provider]
            remaining = self.pool.get_healthy_providers()
            provider_names.extend([p for p in remaining if p != preferred_provider])
        else:
            provider_names = self.pool.get_healthy_providers()

        if not provider_names:
            raise RuntimeError("No healthy providers available")

        if providers:
            provider_names = [p for p in providers if p in provider_names] or provider_names

        last_error = None
        for provider_name in provider_names[:self.max_parallel]:
            provider = self.pool._ensure_provider(provider_name)
            if not provider:
                continue
            start = time.time()
            try:
                response = await provider.chat(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency = (time.time() - start) * 1000
                self.pool.record_success(provider_name, latency)
                return response
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower()
                self.pool.record_failure(provider_name, error_str, is_rate_limit)
                last_error = e
                continue

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def chat_parallel(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        providers: list[str] | None = None,
    ) -> dict[str, LLMResponse]:
        if not providers:
            providers = self.pool.get_healthy_providers()[:self.max_parallel]

        async def _try_provider(name: str) -> tuple[str, Optional[LLMResponse], Optional[Exception]]:
            provider = self.pool._ensure_provider(name)
            if not provider:
                return name, None, RuntimeError(f"Provider {name} not available")
            start = time.time()
            try:
                response = await provider.chat(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency = (time.time() - start) * 1000
                self.pool.record_success(name, latency)
                return name, response, None
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower()
                self.pool.record_failure(name, error_str, is_rate_limit)
                return name, None, e

        tasks = [_try_provider(name) for name in providers]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        responses = {}
        for name, response, error in results:
            responses[name] = {"response": response, "error": error}

        return responses

    async def chat_race(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        providers: list[str] | None = None,
        timeout: float = 30.0,
    ) -> LLMResponse:
        if not providers:
            providers = self.pool.get_healthy_providers()[:self.max_parallel]

        async def _try_provider(name: str) -> Optional[LLMResponse]:
            provider = self.pool._ensure_provider(name)
            if not provider:
                return None
            start = time.time()
            try:
                response = await provider.chat(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency = (time.time() - start) * 1000
                self.pool.record_success(name, latency)
                return response
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower()
                self.pool.record_failure(name, error_str, is_rate_limit)
                return None

        done, pending = await asyncio.wait(
            [asyncio.create_task(_try_provider(name)) for name in providers],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        for task in done:
            result = task.result()
            if result is not None:
                return result

        raise RuntimeError(f"All providers failed within {timeout}s timeout")


# Global parallel provider instance
_parallel_provider: ParallelProvider | None = None


def get_parallel_provider(config: SwarmConfig | None = None) -> ParallelProvider:
    global _parallel_provider
    if _parallel_provider is None:
        if config is None:
            from swarm.config import SwarmConfig
            config = SwarmConfig.auto_detect()
        pool = ProviderPool(config=config)
        _parallel_provider = ParallelProvider(pool=pool)
    return _parallel_provider


# ---------------------------------------------------------------------------
# Tool functions for registry
# ---------------------------------------------------------------------------

def parallel_chat(messages: str, providers: str = "", temperature: float = 0.3) -> str:
    msg_list = json.loads(messages) if isinstance(messages, str) else messages
    provider_list = [p.strip() for p in providers.split(",") if p.strip()] if providers else None
    pp = get_parallel_provider()

    async def _run():
        return await pp.chat_with_failover(
            messages=msg_list,
            temperature=temperature,
            providers=provider_list,
        )

    loop = asyncio.new_event_loop()
    try:
        response = loop.run_until_complete(_run())
        return json.dumps({
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }, indent=2)
    finally:
        loop.close()


def parallel_chat_race(messages: str, providers: str = "", timeout: float = 30.0) -> str:
    msg_list = json.loads(messages) if isinstance(messages, str) else messages
    provider_list = [p.strip() for p in providers.split(",") if p.strip()] if providers else None
    pp = get_parallel_provider()

    async def _run():
        return await pp.chat_race(
            messages=msg_list,
            providers=provider_list,
            timeout=timeout,
        )

    loop = asyncio.new_event_loop()
    try:
        response = loop.run_until_complete(_run())
        return json.dumps({
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }, indent=2)
    finally:
        loop.close()


def get_provider_health() -> str:
    pp = get_parallel_provider()
    return json.dumps(pp.pool.get_health_summary(), indent=2)


def list_available_providers() -> str:
    pp = get_parallel_provider()
    healthy = pp.pool.get_healthy_providers()
    return json.dumps({
        "available": healthy,
        "count": len(healthy),
        "health": pp.pool.get_health_summary(),
    }, indent=2)


PARALLEL_PROVIDER_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "parallel_chat",
        "description": "Send a chat request with automatic failover across multiple providers. If one provider fails, it tries the next available provider automatically.",
        "func": parallel_chat,
        "parameters": {
            "type": "object",
            "properties": {
                "messages": {"type": "string", "description": "JSON array of messages"},
                "providers": {"type": "string", "description": "Comma-separated provider names to try (optional)"},
                "temperature": {"type": "number", "description": "Temperature (default 0.3)"},
            },
            "required": ["messages"],
        },
    },
    {
        "name": "parallel_chat_race",
        "description": "Send a chat request to multiple providers simultaneously and return the fastest response. Use for time-sensitive requests.",
        "func": parallel_chat_race,
        "parameters": {
            "type": "object",
            "properties": {
                "messages": {"type": "string", "description": "JSON array of messages"},
                "providers": {"type": "string", "description": "Comma-separated provider names to race (optional)"},
                "timeout": {"type": "number", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["messages"],
        },
    },
    {
        "name": "get_provider_health",
        "description": "Get health status of all providers: success rates, latency, and availability.",
        "func": get_provider_health,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_available_providers",
        "description": "List all available and healthy providers with their current status.",
        "func": list_available_providers,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

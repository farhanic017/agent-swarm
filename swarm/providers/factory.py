from typing import Optional
from swarm.config import SwarmConfig, normalize_provider_name
from swarm.providers.base import LLMProvider
from swarm.providers.azure import AzureProvider
from swarm.providers.openai import OpenAIProvider
from swarm.providers.openrouter import OpenRouterProvider
from swarm.providers.google import GoogleProvider
from swarm.providers.anthropic import AnthropicProvider
from swarm.providers.openai_compatible import OpenAICompatibleProvider


OPENAI_COMPATIBLE_ENDPOINTS = {
    "openclaw": "http://localhost:7331/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "perplexity": "https://api.perplexity.ai",
    "cohere": "https://api.cohere.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "xai": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
    "llamacpp": "http://localhost:8080/v1",
}


def _build_provider(normalized: str, api_key: str, endpoint: str = None, models: dict = None):
    if normalized == "azure":
        return AzureProvider(api_key=api_key, endpoint=endpoint or "", models=models or {})
    elif normalized == "openai":
        endpoint = endpoint or "https://api.openai.com/v1"
        return OpenAIProvider(api_key=api_key, endpoint=endpoint)
    elif normalized == "openrouter":
        return OpenRouterProvider(api_key=api_key, endpoint=endpoint or "https://openrouter.ai/api/v1")
    elif normalized == "google":
        return GoogleProvider(api_key=api_key)
    elif normalized == "anthropic":
        endpoint = endpoint or "https://api.anthropic.com/v1"
        return AnthropicProvider(api_key=api_key, endpoint=endpoint)
    elif normalized == "openclaw":
        ep = endpoint or OPENAI_COMPATIBLE_ENDPOINTS[normalized]
        return OpenAICompatibleProvider(api_key=api_key, endpoint=ep, provider_name=normalized)
    elif normalized in OPENAI_COMPATIBLE_ENDPOINTS:
        ep = endpoint or OPENAI_COMPATIBLE_ENDPOINTS[normalized]
        return OpenAICompatibleProvider(api_key=api_key, endpoint=ep, provider_name=normalized)
    else:
        if endpoint:
            return OpenAICompatibleProvider(api_key=api_key, endpoint=endpoint, provider_name=normalized)
    return None


class ProviderFactory:
    _instances: dict = {}

    @classmethod
    def get_provider(cls, config: SwarmConfig, model_ref: str) -> Optional[LLMProvider]:
        if ":" not in model_ref:
            return cls._find_any_provider(config)

        raw_provider_name, model_name = model_ref.split(":", 1)
        normalized = normalize_provider_name(raw_provider_name)

        cache_key = f"{normalized}:{model_name}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]

        if raw_provider_name not in config.providers:
            for cfg_name in config.providers:
                if normalize_provider_name(cfg_name) == normalized:
                    raw_provider_name = cfg_name
                    break
            else:
                return cls._find_any_provider(config)

        pc = config.providers[raw_provider_name]
        provider = _build_provider(normalized, pc.api_key, pc.endpoint, pc.models)

        if provider:
            cls._instances[cache_key] = provider
        return provider

    @classmethod
    def get_chat_func(cls, config: SwarmConfig, model_ref: str):
        provider = cls.get_provider(config, model_ref)

        if provider is None:
            raise RuntimeError(
                f"No provider available for model '{model_ref}'. "
                "Check your API keys and configuration."
            )

        async def chat_func(messages, tools=None, temperature=0.3, max_tokens=4096, model=None):
            actual_model = model or model_ref
            if ":" in actual_model:
                _, model_name = actual_model.split(":", 1)
            else:
                model_name = actual_model

            return await provider.chat(
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model_name,
            )

        return chat_func

    @classmethod
    def _find_any_provider(cls, config: SwarmConfig) -> Optional[LLMProvider]:
        for cfg_name, pc in config._sorted_providers():
            normalized = normalize_provider_name(cfg_name)
            return _build_provider(normalized, pc.api_key, pc.endpoint, pc.models)
        return None

    @classmethod
    def clear_cache(cls):
        cls._instances.clear()

    @classmethod
    async def close_cached(cls):
        for provider in cls._instances.values():
            client = getattr(provider, "_client", None)
            if client is not None and hasattr(client, "aclose"):
                await client.aclose()
        cls.clear_cache()

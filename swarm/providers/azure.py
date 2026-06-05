import json
from typing import Optional
import httpx
from swarm.providers.base import LLMProvider, LLMResponse, MediaGenerationRequest, MediaGenerationResponse, Message
from swarm.providers.media import media_body, media_response


REASONING_MODELS = {"gpt-5", "o4", "o3", "o1"}


def _needs_max_completion_tokens(model: str) -> bool:
    model_lower = model.lower()
    return any(model_lower.startswith(prefix) for prefix in REASONING_MODELS)


class AzureProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str, models: dict = None):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.models = models or {}
        self._client = httpx.AsyncClient(timeout=60.0)

    def _get_deployment(self, model: str) -> str:
        if model in self.models:
            m = self.models[model]
            if isinstance(m, dict):
                return m.get("deployment") or m.get("model") or m.get("id") or model
        return model

    def _get_api_version(self, model: str) -> str:
        if model in self.models:
            m = self.models[model]
            if isinstance(m, dict):
                configured = m.get("api_version") or m.get("apiVersion")
                if configured:
                    return configured
        model_lower = model.lower()
        if any(model_lower.startswith(prefix) for prefix in ("o4", "o3", "o1")):
            return "2025-01-01-preview"
        return "2024-08-01-preview"

    def _uses_openai_v1(self, model: str) -> bool:
        endpoint_lower = self.endpoint.lower()
        if endpoint_lower.endswith("/openai/v1") or "/openai/v1/" in endpoint_lower:
            return True

        if model in self.models:
            m = self.models[model]
            if isinstance(m, dict):
                style = (
                    m.get("api_style")
                    or m.get("apiStyle")
                    or m.get("api_type")
                    or m.get("apiType")
                    or ""
                )
                return str(style).lower() in {
                    "openai_v1",
                    "openai-v1",
                    "foundry_v1",
                    "foundry-v1",
                    "v1",
                }
        return False

    def _chat_url(self, model: str, deployment: str, api_version: str) -> str:
        if self._uses_openai_v1(model):
            base = self.endpoint
            if base.endswith("/chat/completions"):
                return base
            if base.endswith("/openai/v1"):
                return f"{base}/chat/completions"
            return f"{base}/openai/v1/chat/completions"
        return f"{self.endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    def _media_url(self, model: str, deployment: str, api_version: str, kind: str) -> str:
        if model in self.models:
            m = self.models[model]
            if isinstance(m, dict):
                path = m.get(f"{kind}_path") or m.get(f"{kind}Path")
                if path:
                    return f"{self.endpoint}{path}"

        if self._uses_openai_v1(model):
            base = self.endpoint
            suffix = "images/generations" if kind == "image" else "videos/generations"
            if base.endswith(f"/{suffix}"):
                return base
            if base.endswith("/openai/v1"):
                return f"{base}/{suffix}"
            return f"{base}/openai/v1/{suffix}"

        route = "images/generations" if kind == "image" else "videos/generations"
        return f"{self.endpoint}/openai/deployments/{deployment}/{route}?api-version={api_version}"

    async def chat(
        self,
        messages: list,
        tools: Optional[list] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        model = model or "gpt-4.1"
        deployment = self._get_deployment(model)
        api_version = self._get_api_version(model)

        url = self._chat_url(model, deployment, api_version)

        body = {
            "messages": [m.to_dict() if isinstance(m, Message) else m for m in messages],
            "temperature": temperature,
        }
        if self._uses_openai_v1(model):
            body["model"] = deployment

        if _needs_max_completion_tokens(model):
            body["max_completion_tokens"] = max_tokens
        else:
            body["max_tokens"] = max_tokens

        if tools:
            body["tools"] = [t.to_openai_format() if hasattr(t, "to_openai_format") else t for t in tools]

        response = await self._client.post(
            url,
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        msg = choice["message"]

        return LLMResponse(
            content=msg.get("content", "") or "",
            model=data.get("model", model),
            provider="azure",
            usage=data.get("usage", {}),
            tool_calls=msg.get("tool_calls", []),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def generate_image(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        model = request.model or "gpt-image-1"
        deployment = self._get_deployment(model)
        api_version = self._get_api_version(model)
        body = media_body(request, deployment if self._uses_openai_v1(model) else model, kind="image")
        response = await self._client.post(
            self._media_url(model, deployment, api_version, "image"),
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        return media_response("image", "azure", model, response.json())

    async def generate_video(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        model = request.model or "sora"
        deployment = self._get_deployment(model)
        api_version = self._get_api_version(model)
        body = media_body(request, deployment if self._uses_openai_v1(model) else model, kind="video")
        response = await self._client.post(
            self._media_url(model, deployment, api_version, "video"),
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        return media_response("video", "azure", model, response.json())

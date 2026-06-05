from typing import Optional
import httpx
from swarm.providers.base import LLMProvider, LLMResponse, MediaGenerationRequest, MediaGenerationResponse, Message
from swarm.providers.media import media_body, media_response


class OpenAICompatibleProvider(LLMProvider):
    """Generic provider for any OpenAI-compatible API (Groq, Together, Perplexity, etc.)"""

    def __init__(self, api_key: str, endpoint: str, provider_name: str = "openai_compatible"):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.provider_name = provider_name
        self._client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        messages: list,
        tools: Optional[list] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        model = model or "gpt-4o-mini"

        body = {
            "model": model,
            "messages": [m.to_dict() if isinstance(m, Message) else m for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = [t.to_openai_format() if hasattr(t, "to_openai_format") else t for t in tools]

        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await self._client.post(
            f"{self.endpoint}/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        msg = choice["message"]

        return LLMResponse(
            content=msg.get("content", "") or "",
            model=data.get("model", model),
            provider=self.provider_name,
            usage=data.get("usage", {}),
            tool_calls=msg.get("tool_calls", []),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate_image(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        model = request.model or "image-generation"
        path = request.extra.get("path") or "/images/generations"
        body = media_body(request, model, kind="image")
        body.pop("path", None)
        response = await self._client.post(
            f"{self.endpoint}{path}",
            headers=self._headers(),
            json=body,
        )
        response.raise_for_status()
        return media_response("image", self.provider_name, model, response.json())

    async def generate_video(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        model = request.model or "video-generation"
        path = request.extra.get("path") or "/videos/generations"
        body = media_body(request, model, kind="video")
        body.pop("path", None)
        response = await self._client.post(
            f"{self.endpoint}{path}",
            headers=self._headers(),
            json=body,
        )
        response.raise_for_status()
        return media_response("video", self.provider_name, model, response.json())

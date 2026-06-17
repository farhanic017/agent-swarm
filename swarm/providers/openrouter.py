import asyncio
import re
from typing import Optional
import httpx
from swarm.providers.base import LLMProvider, LLMResponse, Message, ProviderError

_EXHAUSTION_PATTERNS = [
    r"insufficient.?quota", r"quota.?exceeded", r"credit.?limit",
    r"0.?credits?.?remaining", r"out.?of.?credits", r"payment.?required",
    r"buy.*token", r"purchase.*credit", r"add.*funds", r"free.?tier.?limit",
]


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        messages: list,
        tools: Optional[list] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        model = model or "openrouter/free"

        body = {
            "model": model,
            "messages": [m.to_dict() if isinstance(m, Message) else m for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = [t.to_openai_format() if hasattr(t, "to_openai_format") else t for t in tools]

        max_retries = 3
        for attempt in range(max_retries):
            response = await self._client.post(
                f"{self.endpoint}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/farhanic017/agent-swarm",
                },
                json=body,
            )

            if response.status_code == 200:
                data = response.json()
                choice = data["choices"][0]
                msg = choice["message"]
                return LLMResponse(
                    content=msg.get("content", "") or "",
                    model=data.get("model", model),
                    provider="openrouter",
                    usage=data.get("usage", {}),
                    tool_calls=msg.get("tool_calls", []),
                    finish_reason=choice.get("finish_reason", "stop"),
                )

            err_text = response.text[:500]

            # Detect token/credit exhaustion (402 always exhaustion, 429 only if patterns match)
            is_exhaustion = response.status_code == 402 or (
                response.status_code == 429
                and any(re.search(p, err_text.lower()) for p in _EXHAUSTION_PATTERNS)
            )
            if is_exhaustion:
                retry_after = self._parse_retry_after(response)
                raise ProviderError(
                    f"OpenRouter {response.status_code}: {err_text}",
                    status_code=response.status_code,
                    provider="openrouter",
                    model=model,
                    is_exhaustion=True,
                    retry_after=retry_after,
                )

            if response.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()

        # Should not reach here, but just in case
        raise ProviderError(
            f"OpenRouter: all retries failed",
            status_code=429, provider="openrouter", model=model,
        )

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> Optional[int]:
        h = response.headers.get("retry-after") or response.headers.get("Retry-After")
        if h:
            try:
                return int(h)
            except ValueError:
                pass
        return None

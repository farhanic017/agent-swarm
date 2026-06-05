from typing import Optional
import httpx
from swarm.providers.base import LLMProvider, LLMResponse, Message


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)

    @staticmethod
    def _normalize_model(model: str) -> str:
        name = model.strip()
        if name.startswith("gemini/"):
            name = name[len("gemini/"):]
        if name.startswith("models/"):
            name = name[len("models/"):]
        return name

    async def chat(
        self,
        messages: list,
        tools: Optional[list] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        model = self._normalize_model(model or "gemini-2.0-flash-001")

        contents = []
        system_instruction = None
        for m in messages:
            if isinstance(m, Message):
                if m.role == "system":
                    system_instruction = {"parts": [{"text": m.content}]}
                elif m.role == "user":
                    contents.append({"role": "user", "parts": [{"text": m.content}]})
                elif m.role == "assistant":
                    contents.append({"role": "model", "parts": [{"text": m.content}]})
            else:
                if m["role"] == "system":
                    system_instruction = {"parts": [{"text": m["content"]}]}
                elif m["role"] == "user":
                    contents.append({"role": "user", "parts": [{"text": m["content"]}]})
                elif m["role"] == "assistant":
                    contents.append({"role": "model", "parts": [{"text": m["content"]}]})

        body = {"contents": contents}
        if system_instruction:
            body["systemInstruction"] = system_instruction

        gen_conf = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        body["generationConfig"] = gen_conf

        url = f"{self.endpoint}/models/{model}:generateContent?key={self.api_key}"

        response = await self._client.post(url, json=body)
        response.raise_for_status()
        data = response.json()

        candidate = data.get("candidates", [{}])[0]
        content_parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in content_parts)

        usage = {}
        if "usageMetadata" in data:
            usage = data["usageMetadata"]

        return LLMResponse(
            content=text,
            model=model,
            provider="google",
            usage=usage,
            finish_reason=candidate.get("finishReason", "stop"),
        )

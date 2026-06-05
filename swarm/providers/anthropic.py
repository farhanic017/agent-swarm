from typing import Optional
import json
import httpx
from swarm.providers.base import LLMProvider, LLMResponse, Message


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str = "https://api.anthropic.com/v1"):
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
        model = model or "claude-sonnet-4-20250514"

        system_text = ""
        converted = []
        for m in messages:
            if isinstance(m, Message):
                role = m.role
                content = m.content
            else:
                role = m.get("role", "")
                content = m.get("content", "")

            if role == "system":
                system_text += content + "\n"
            elif role == "user":
                converted.append({"role": "user", "content": content})
            elif role == "assistant":
                converted.append({"role": "assistant", "content": content})
            elif role == "tool":
                converted.append({"role": "user", "content": f"[Tool result: {content}]"})

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": converted,
        }
        if system_text.strip():
            body["system"] = system_text.strip()
        if temperature is not None:
            body["temperature"] = temperature

        if tools:
            anthropic_tools = []
            for t in tools:
                if hasattr(t, "to_openai_format"):
                    oai = t.to_openai_format()
                    at = {
                        "name": oai["function"]["name"],
                        "description": oai["function"]["description"],
                        "input_schema": oai["function"]["parameters"],
                    }
                    anthropic_tools.append(at)
                elif isinstance(t, dict):
                    fn = t.get("function", t)
                    at = {
                        "name": fn.get("name", "unknown"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                    }
                    anthropic_tools.append(at)
            if anthropic_tools:
                body["tools"] = anthropic_tools

        response = await self._client.post(
            f"{self.endpoint}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        data = response.json()

        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

        tc = []
        for b in content_blocks:
            if b.get("type") == "tool_use":
                tc.append({
                    "id": b.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": b.get("name", ""),
                        "arguments": json.dumps(b.get("input", {})),
                    },
                })

        usage = data.get("usage", {})
        return LLMResponse(
            content=text,
            model=data.get("model", model),
            provider="anthropic",
            usage=usage,
            tool_calls=tc,
            finish_reason=data.get("stop_reason", "stop"),
        )

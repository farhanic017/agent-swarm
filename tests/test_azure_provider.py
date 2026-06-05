import pytest

from swarm.providers.azure import AzureProvider
from swarm.providers.base import Message


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": "AZURE_OK"}, "finish_reason": "stop"}],
            "model": "gpt-4.1",
            "usage": {"total_tokens": 3},
        }


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse()


@pytest.mark.asyncio
async def test_azure_provider_uses_deployment_chat_completions_by_default():
    provider = AzureProvider(
        api_key="x",
        endpoint="https://example.openai.azure.com",
        models={"gpt-4.1": {"deployment": "gpt-4-1-prod"}},
    )
    fake = _FakeClient()
    provider._client = fake

    response = await provider.chat(
        [Message(role="user", content="ping")],
        model="gpt-4.1",
        max_tokens=16,
    )

    call = fake.calls[0]
    assert response.content == "AZURE_OK"
    assert call["url"] == (
        "https://example.openai.azure.com/openai/deployments/"
        "gpt-4-1-prod/chat/completions?api-version=2024-08-01-preview"
    )
    assert call["json"]["max_tokens"] == 16
    assert "model" not in call["json"]


@pytest.mark.asyncio
async def test_azure_provider_supports_foundry_openai_v1_chat_completions():
    provider = AzureProvider(
        api_key="x",
        endpoint="https://example.openai.azure.com",
        models={"gpt-4.1": {"deployment": "gpt-4-1-prod", "apiStyle": "foundry-v1"}},
    )
    fake = _FakeClient()
    provider._client = fake

    response = await provider.chat(
        [Message(role="user", content="ping")],
        model="gpt-4.1",
        max_tokens=16,
    )

    call = fake.calls[0]
    assert response.content == "AZURE_OK"
    assert call["url"] == "https://example.openai.azure.com/openai/v1/chat/completions"
    assert call["json"]["model"] == "gpt-4-1-prod"
    assert call["json"]["max_tokens"] == 16

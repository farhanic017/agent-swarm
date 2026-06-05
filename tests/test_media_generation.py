import pytest

from swarm.config import ProviderConfig, SwarmConfig
from swarm.providers.base import MediaGenerationRequest
from swarm.providers.factory import ProviderFactory
from swarm.providers.openai_compatible import OpenAICompatibleProvider


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse({"model": json["model"], "data": [{"b64_json": "abc123"}]})


@pytest.mark.asyncio
async def test_openai_compatible_image_generation_request_shape():
    provider = OpenAICompatibleProvider("key", "https://media.example/v1", "media-gateway")
    fake = _FakeClient()
    provider._client = fake

    response = await provider.generate_image(
        MediaGenerationRequest(prompt="coffee cup", model="flux-pro", size="1024x1024")
    )

    call = fake.calls[0]
    assert response.kind == "image"
    assert response.provider == "media-gateway"
    assert response.assets[0]["b64_json"] == "abc123"
    assert call["url"] == "https://media.example/v1/images/generations"
    assert call["headers"]["Authorization"] == "Bearer key"
    assert call["json"]["model"] == "flux-pro"
    assert call["json"]["prompt"] == "coffee cup"
    assert call["json"]["size"] == "1024x1024"


@pytest.mark.asyncio
async def test_openai_compatible_video_generation_can_override_path():
    provider = OpenAICompatibleProvider("key", "https://media.example/v1", "media-gateway")
    fake = _FakeClient()
    provider._client = fake

    response = await provider.generate_video(
        MediaGenerationRequest(
            prompt="coffee steam",
            model="veo-3",
            duration=5,
            extra={"path": "/beta/videos"},
        )
    )

    call = fake.calls[0]
    assert response.kind == "video"
    assert call["url"] == "https://media.example/v1/beta/videos"
    assert call["json"]["model"] == "veo-3"
    assert call["json"]["duration"] == 5
    assert "path" not in call["json"]


@pytest.mark.asyncio
async def test_provider_factory_routes_image_and_video_model_refs(monkeypatch):
    provider = OpenAICompatibleProvider("", "http://localhost:9000/v1", "local-media")
    fake = _FakeClient()
    provider._client = fake

    cfg = SwarmConfig(
        providers={
            "local-media": ProviderConfig(
                api_key="",
                endpoint="http://localhost:9000/v1",
                models={
                    "flux-dev": {"modalities": ["image_generation"]},
                    "wan-video": {"modalities": ["video_generation"]},
                },
            )
        }
    )

    monkeypatch.setattr(ProviderFactory, "get_provider", classmethod(lambda cls, config, model_ref: provider))

    image = await ProviderFactory.get_image_func(cfg, "local-media:flux-dev")(
        MediaGenerationRequest(prompt="poster")
    )
    video = await ProviderFactory.get_video_func(cfg, "local-media:wan-video")(
        MediaGenerationRequest(prompt="poster motion")
    )

    assert image.model == "flux-dev"
    assert video.model == "wan-video"

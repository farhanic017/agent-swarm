import pytest

from swarm.config import ProviderConfig, SwarmConfig
from swarm.providers.base import AudioSpeechRequest, MediaGenerationRequest
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
        if "text2video" in url:
            return _FakeResponse({"model": json["model"], "task_id": "task-1", "status": "submitted"})
        if "audio/text-to-speech" in url:
            return _FakeResponse({"model": json["model"], "url": "https://audio.example/speech.wav"})
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


def test_google_flow_omni_and_veo_models_are_detected_for_generation():
    cfg = SwarmConfig(
        providers={
            "google-ai": ProviderConfig(
                api_key="x",
                models={
                    "google-flow-veo-3": {},
                    "veo-3": {},
                    "omni-image": {},
                    "omni-video": {},
                },
            )
        }
    )

    image_models = cfg.get_media_models("image")
    video_models = cfg.get_media_models("video")
    vision_models = cfg.get_media_models("vision")

    assert "google-ai:omni-image" in image_models
    assert "google-ai:google-flow-veo-3" in video_models
    assert "google-ai:veo-3" in video_models
    assert "google-ai:omni-video" in video_models
    assert "google-ai:google-flow-veo-3" in vision_models


def test_new_media_and_model_provider_families_are_auto_detected(monkeypatch):
    monkeypatch.setattr("swarm.config._detect_local_models", lambda: {})
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")
    monkeypatch.setenv("RECRAFT_API_KEY", "recraft-key")
    monkeypatch.setenv("KLING_API_KEY", "kling-key")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setenv("HF_TOKEN", "hf-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "perplexity-key")
    monkeypatch.setenv("ZYPHRA_API_KEY", "zyphra-key")
    monkeypatch.setenv("MICROSOFT_AI_API_KEY", "microsoft-key")
    monkeypatch.setenv("MICROSOFT_AI_ENDPOINT", "https://models.example/v1")

    cfg = SwarmConfig.auto_detect()

    assert {
        "moonshot",
        "recraft",
        "kling",
        "nvidia",
        "huggingface",
        "alibaba",
        "perplexity",
        "zyphra",
        "microsoft",
    }.issubset(cfg.providers)
    assert "recraft:recraftv4_1" in cfg.get_media_models("image")
    assert "huggingface:black-forest-labs/FLUX.1-dev" in cfg.get_media_models("image")
    assert "kling:kling-v2.6-pro" in cfg.get_media_models("video")
    assert "huggingface:Wan-AI/Wan2.2-T2V-A14B" in cfg.get_media_models("video")
    assert "zyphra:zonos-v0.1-transformer" in cfg.get_media_models("text_to_speech")
    assert cfg.find_model("image_generation").startswith("recraft:")
    assert cfg.find_model("video_generation").startswith("kling:")


@pytest.mark.asyncio
async def test_kling_and_zyphra_have_provider_specific_default_paths():
    kling = OpenAICompatibleProvider("key", "https://api.klingapi.com", "kling")
    kling_fake = _FakeClient()
    kling_fake.calls = []
    kling._client = kling_fake

    video = await kling.generate_video(MediaGenerationRequest(prompt="coffee steam", model="kling-v2.6-pro"))

    assert kling_fake.calls[0]["url"] == "https://api.klingapi.com/v1/videos/text2video"
    assert video.assets[0]["task_id"] == "task-1"

    zyphra = OpenAICompatibleProvider("key", "https://api.zyphra.com/v1", "zyphra")
    zyphra_fake = _FakeClient()
    zyphra._client = zyphra_fake

    await zyphra.synthesize_speech(AudioSpeechRequest(text="hello", model="zonos-v0.1-transformer"))

    assert zyphra_fake.calls[0]["url"] == "https://api.zyphra.com/v1/audio/text-to-speech"

import pytest

from swarm.config import ProviderConfig, SwarmConfig, normalize_provider_name
from swarm.providers.base import AudioSpeechRequest, AudioTranscriptionRequest
from swarm.providers.elevenlabs import ElevenLabsProvider
from swarm.providers.factory import ProviderFactory
from swarm.providers.openai_compatible import OpenAICompatibleProvider


class _FakeResponse:
    def __init__(self, data=None, content=b""):
        self._data = data
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        if self._data is None:
            raise ValueError("binary response")
        return self._data


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, headers=None, json=None, data=None, files=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "data": data, "files": files})
        if "speech" in url and json:
            return _FakeResponse(content=b"voice-bytes")
        return _FakeResponse({"model": (data or json or {}).get("model") or (data or {}).get("model_id"), "text": "hello transcript"})


@pytest.mark.asyncio
async def test_openai_compatible_audio_routes(tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    provider = OpenAICompatibleProvider("key", "https://audio.example/v1", "audio-gateway")
    fake = _FakeClient()
    provider._client = fake

    transcript = await provider.transcribe_audio(
        AudioTranscriptionRequest(str(audio), model="whisper-large", language="en")
    )
    speech = await provider.synthesize_speech(
        AudioSpeechRequest("Ship it", model="tts-pro", voice="alloy", output_format="mp3")
    )

    assert transcript.kind == "speech_to_text"
    assert transcript.text == "hello transcript"
    assert fake.calls[0]["url"] == "https://audio.example/v1/audio/transcriptions"
    assert fake.calls[0]["data"]["model"] == "whisper-large"
    assert fake.calls[0]["files"]["file"][0] == "sample.wav"
    assert speech.kind == "text_to_speech"
    assert speech.assets[0]["base64"]
    assert fake.calls[1]["url"] == "https://audio.example/v1/audio/speech"
    assert fake.calls[1]["json"]["voice"] == "alloy"


@pytest.mark.asyncio
async def test_elevenlabs_native_stt_and_tts_routes(tmp_path):
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"mp3")
    provider = ElevenLabsProvider("eleven-key")
    fake = _FakeClient()
    provider._client = fake

    transcript = await provider.transcribe_audio(
        AudioTranscriptionRequest(str(audio), model="scribe_v1", language="en")
    )
    speech = await provider.synthesize_speech(
        AudioSpeechRequest("Coffee launch", model="eleven_multilingual_v2", voice="voice-123")
    )

    assert transcript.provider == "elevenlabs"
    assert fake.calls[0]["url"] == "https://api.elevenlabs.io/v1/speech-to-text"
    assert fake.calls[0]["headers"]["xi-api-key"] == "eleven-key"
    assert fake.calls[0]["data"]["model_id"] == "scribe_v1"
    assert speech.assets[0]["base64"]
    assert fake.calls[1]["url"] == "https://api.elevenlabs.io/v1/text-to-speech/voice-123"


@pytest.mark.asyncio
async def test_provider_factory_routes_audio_model_refs(monkeypatch, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    provider = OpenAICompatibleProvider("", "http://localhost:9001/v1", "local-audio")
    provider._client = _FakeClient()

    cfg = SwarmConfig(
        providers={
            "local-audio": ProviderConfig(
                api_key="",
                endpoint="http://localhost:9001/v1",
                models={
                    "whisper-local": {"modalities": ["speech_to_text"]},
                    "tts-local": {"modalities": ["text_to_speech"]},
                },
            )
        }
    )

    monkeypatch.setattr(ProviderFactory, "get_provider", classmethod(lambda cls, config, model_ref: provider))

    transcript = await ProviderFactory.get_transcription_func(cfg, "local-audio:whisper-local")(
        AudioTranscriptionRequest(str(audio))
    )
    speech = await ProviderFactory.get_speech_func(cfg, "local-audio:tts-local")(
        AudioSpeechRequest("hello")
    )

    assert transcript.model == "whisper-local"
    assert speech.model == "tts-local"


def test_voice_provider_detection_and_aliases(monkeypatch):
    monkeypatch.delenv("OPENAI_TRANSCRIPTION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TTS_MODEL", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven-key")
    monkeypatch.setenv("MANUS_API_KEY", "test-manus-key")
    monkeypatch.setenv("MANUS_BASE_URL", "https://manus.example/v1")
    monkeypatch.setenv("MANUS_MODEL", "manus/project-agent")

    cfg = SwarmConfig.auto_detect()

    assert normalize_provider_name("eleven-labs") == "elevenlabs"
    assert normalize_provider_name("manus-ai") == "manus"
    assert cfg.find_model("speech_to_text") == "elevenlabs:scribe_v1"
    assert cfg.find_model("text_to_speech") == "elevenlabs:eleven_multilingual_v2"
    assert cfg.providers["manus"].endpoint == "https://manus.example/v1"
    assert ProviderFactory.get_provider(cfg, "elevenlabs:scribe_v1") is not None
    assert ProviderFactory.get_provider(cfg, "manus:manus/project-agent") is not None

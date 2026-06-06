from typing import Optional
import httpx
from swarm.providers.base import (
    AudioResponse,
    AudioSpeechRequest,
    AudioTranscriptionRequest,
    LLMProvider,
    LLMResponse,
    MediaGenerationRequest,
    MediaGenerationResponse,
    Message,
)
from swarm.providers.audio import audio_response, file_tuple, speech_body, transcription_fields
from swarm.providers.media import media_body, media_response


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str = "https://api.openai.com/v1"):
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
        model = model or "gpt-4o-mini"

        body = {
            "model": model,
            "messages": [m.to_dict() if isinstance(m, Message) else m for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = [t.to_openai_format() if hasattr(t, "to_openai_format") else t for t in tools]

        response = await self._client.post(
            f"{self.endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
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
            provider="openai",
            usage=data.get("usage", {}),
            tool_calls=msg.get("tool_calls", []),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def generate_image(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        model = request.model or "gpt-image-1"
        response = await self._client.post(
            f"{self.endpoint}/images/generations",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=media_body(request, model, kind="image"),
        )
        response.raise_for_status()
        return media_response("image", "openai", model, response.json())

    async def generate_video(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        model = request.model or "sora"
        path = request.extra.get("path") or "/videos/generations"
        body = media_body(request, model, kind="video")
        body.pop("path", None)
        response = await self._client.post(
            f"{self.endpoint}{path}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        return media_response("video", "openai", model, response.json())

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioResponse:
        model = request.model or "whisper-1"
        response = await self._client.post(
            f"{self.endpoint}/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            data=transcription_fields(request, model),
            files={"file": file_tuple(request.audio_path)},
        )
        response.raise_for_status()
        return audio_response("speech_to_text", "openai", model, response.json())

    async def synthesize_speech(self, request: AudioSpeechRequest) -> AudioResponse:
        model = request.model or "tts-1"
        response = await self._client.post(
            f"{self.endpoint}/audio/speech",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=speech_body(request, model),
        )
        response.raise_for_status()
        try:
            data = response.json()
        except Exception:
            data = getattr(response, "content", b"")
        return audio_response("text_to_speech", "openai", model, data)

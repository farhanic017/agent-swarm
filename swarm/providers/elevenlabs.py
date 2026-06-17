from __future__ import annotations

from typing import Optional

import httpx

from swarm.providers.audio import audio_response, file_tuple
from swarm.providers.base import (
    AudioResponse,
    AudioSpeechRequest,
    AudioTranscriptionRequest,
    LLMProvider,
    LLMResponse,
)


class ElevenLabsProvider(LLMProvider):
    def __init__(self, api_key: str, endpoint: str = "https://api.elevenlabs.io/v1"):
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
        raise NotImplementedError("ElevenLabsProvider is for speech-to-text and text-to-speech")

    def _headers(self) -> dict:
        return {"xi-api-key": self.api_key}

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioResponse:
        model = request.model or "scribe_v1"
        data = {"model_id": model}
        if request.language:
            data["language_code"] = request.language
        data.update({k: v for k, v in (request.extra or {}).items() if k != "path"})
        response = await self._client.post(
            f"{self.endpoint}/speech-to-text",
            headers=self._headers(),
            data=data,
            files={"file": file_tuple(request.audio_path)},
        )
        response.raise_for_status()
        return audio_response("speech_to_text", "elevenlabs", model, response.json())

    async def synthesize_speech(self, request: AudioSpeechRequest) -> AudioResponse:
        model = request.model or "eleven_multilingual_v2"
        voice = request.voice or request.extra.get("voice_id") or "Rachel"
        body = {
            "text": request.text,
            "model_id": model,
        }
        if request.output_format:
            body["output_format"] = request.output_format
        if request.speed is not None:
            body["voice_settings"] = {"speed": request.speed}
        for key, value in (request.extra or {}).items():
            if key not in {"path", "voice_id"}:
                body[key] = value

        response = await self._client.post(
            f"{self.endpoint}/text-to-speech/{voice}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except Exception:
            data = getattr(response, "content", b"")
        return audio_response("text_to_speech", "elevenlabs", model, data)

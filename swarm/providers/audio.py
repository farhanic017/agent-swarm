from __future__ import annotations

import base64
from pathlib import Path

from swarm.providers.base import AudioResponse, AudioSpeechRequest, AudioTranscriptionRequest


def transcription_fields(request: AudioTranscriptionRequest, model: str) -> dict:
    body = {"model": model}
    if request.language:
        body["language"] = request.language
    if request.prompt:
        body["prompt"] = request.prompt
    if request.response_format:
        body["response_format"] = request.response_format
    body.update(request.extra or {})
    body.pop("path", None)
    return body


def speech_body(request: AudioSpeechRequest, model: str) -> dict:
    body = {
        "model": model,
        "input": request.text,
    }
    if request.voice:
        body["voice"] = request.voice
    if request.output_format:
        body["response_format"] = request.output_format
    if request.speed is not None:
        body["speed"] = request.speed
    body.update(request.extra or {})
    body.pop("path", None)
    return body


def audio_response(kind: str, provider: str, model: str, data) -> AudioResponse:
    if isinstance(data, dict):
        text = str(data.get("text") or data.get("transcript") or "")
        assets = _audio_assets(data)
        return AudioResponse(kind=kind, model=data.get("model", model), provider=provider, text=text, assets=assets, raw=data)

    if isinstance(data, (bytes, bytearray)):
        encoded = base64.b64encode(bytes(data)).decode("ascii")
        return AudioResponse(
            kind=kind,
            model=model,
            provider=provider,
            assets=[{"index": 0, "base64": encoded}],
            raw={"bytes": len(data)},
        )

    return AudioResponse(kind=kind, model=model, provider=provider, text=str(data), raw={"value": data})


def file_tuple(audio_path: str) -> tuple[str, bytes, str]:
    path = Path(audio_path)
    suffix = path.suffix.lower()
    mime = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(suffix, "application/octet-stream")
    return (path.name, path.read_bytes(), mime)


def _audio_assets(data: dict) -> list[dict]:
    raw_items = data.get("data") or data.get("assets") or data.get("audio") or []
    if isinstance(raw_items, (str, bytes, dict)):
        raw_items = [raw_items]

    assets = []
    for index, item in enumerate(raw_items):
        if isinstance(item, bytes):
            assets.append({"index": index, "base64": base64.b64encode(item).decode("ascii")})
        elif isinstance(item, str):
            assets.append({"index": index, "url": item})
        elif isinstance(item, dict):
            asset = {"index": index}
            for key in ("url", "base64", "b64_json", "mime_type", "mimeType", "id"):
                if key in item:
                    asset[key] = item[key]
            if len(asset) == 1:
                asset["raw"] = item
            assets.append(asset)
    return assets

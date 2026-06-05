from __future__ import annotations

from swarm.providers.base import MediaGenerationRequest, MediaGenerationResponse


def media_body(request: MediaGenerationRequest, model: str, *, kind: str) -> dict:
    body = {"model": model, "prompt": request.prompt}

    if request.size:
        body["size"] = request.size
    if request.quality:
        body["quality"] = request.quality
    if request.output_format:
        body["output_format"] = request.output_format
    if kind == "video":
        if request.duration is not None:
            body["duration"] = request.duration
        if request.fps is not None:
            body["fps"] = request.fps
    if request.reference_paths:
        body["reference_paths"] = list(request.reference_paths)
    body.update(request.extra or {})
    return body


def media_assets(data: dict) -> list[dict]:
    raw_items = data.get("data")
    if raw_items is None:
        raw_items = data.get("assets") or data.get("output") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    assets = []
    for index, item in enumerate(raw_items):
        if isinstance(item, str):
            assets.append({"index": index, "url": item})
            continue
        if not isinstance(item, dict):
            assets.append({"index": index, "value": item})
            continue
        asset = {"index": index}
        for key in (
            "url",
            "b64_json",
            "base64",
            "mime_type",
            "mimeType",
            "revised_prompt",
            "id",
            "status",
        ):
            if key in item:
                asset[key] = item[key]
        if len(asset) == 1:
            asset["raw"] = item
        assets.append(asset)
    return assets


def media_response(kind: str, provider: str, model: str, data: dict) -> MediaGenerationResponse:
    return MediaGenerationResponse(
        kind=kind,
        model=data.get("model", model),
        provider=provider,
        assets=media_assets(data),
        raw=data,
    )

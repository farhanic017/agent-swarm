from __future__ import annotations

import json


VISION_DETAIL_AREAS = [
    "objects, people, characters, products, and text",
    "layout, spacing, alignment, hierarchy, and composition",
    "colors, materials, lighting, shadows, camera angle, and style",
    "UI states, controls, navigation, responsiveness, and accessibility hints",
    "animation timing, motion paths, transitions, cuts, and scene changes",
    "3D geometry, scale, silhouette, perspective, interior/exterior details, and missing angles",
    "risks, ambiguities, edge cases, and what must be verified by the next agent",
]


def plan_temporary_vision(
    agent_name: str,
    agent_model: str,
    task: str,
    asset_type: str = "image_or_video",
    mode: str = "build",
    available_vision_models: str | list[str] = "",
) -> dict:
    models = _coerce_models(available_vision_models)
    agent_has_vision = _looks_like_vision_model(agent_model)
    needs_visual_detail = _needs_visual_detail(task, asset_type)
    plan_mode = mode.lower() in {"plan", "planning", "planner"}

    if agent_has_vision:
        route = "use_agent_native_vision"
        questions = []
    elif models:
        route = "delegate_to_temporary_vision_model"
        questions = []
    elif plan_mode and needs_visual_detail:
        route = "ask_user_extensive_visual_questions"
        questions = build_plan_mode_visual_questions(task, asset_type)
    else:
        route = "continue_without_annoying_user"
        questions = []

    return {
        "agent_name": agent_name,
        "agent_model": agent_model,
        "task": task,
        "asset_type": asset_type,
        "mode": mode,
        "agent_has_native_vision": agent_has_vision,
        "available_vision_models": models,
        "route": route,
        "temporary_vision_model": models[0] if route == "delegate_to_temporary_vision_model" else "",
        "vision_brief_requirements": VISION_DETAIL_AREAS,
        "handoff_policy": "Vision model returns a full structured visual brief once; the requesting agent continues from that brief without repeatedly rereading the media.",
        "questions": questions,
        "question_policy": {
            "plan_mode": "ask detailed visual/function questions only when no vision model can inspect needed media",
            "build_or_normal_mode": "avoid extensive questioning; proceed with reasonable assumptions and ask only blocking questions",
            "simple_tasks": "do not ask extensive questions for simple requests such as a basic coin or simple Blender primitive",
        },
    }


def build_plan_mode_visual_questions(task: str, asset_type: str = "image_or_video") -> list[str]:
    if _is_simple_visual_task(task):
        return []
    base = [
        "What exact visual style should the final result follow?",
        "What are the main objects, layout, proportions, colors, and materials?",
        "What should be visible from the front, back, sides, top, and close-up views?",
        "What text, branding, icons, UI controls, or labels must be preserved?",
        "What animations, transitions, timing, camera moves, or interactions are required?",
        "What functions or user flows are tied to the visual design?",
        "What details are forbidden, optional, or lower priority?",
    ]
    if "building" in task.lower() or "interior" in task.lower() or "exterior" in task.lower():
        base.extend([
            "What dimensions, room list, floor count, site constraints, and entrance direction should be used?",
            "What interior finishes, furniture, lighting, facade materials, landscape, and circulation style do you want?",
        ])
    if asset_type.lower() in {"video", "animation"} or any(token in task.lower() for token in ("video", "animation", "animated")):
        base.extend([
            "What keyframes or scenes happen first, middle, and last?",
            "What frame rate, duration, transitions, captions, and audio cues are expected?",
        ])
    return base


def _coerce_models(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _looks_like_vision_model(model: str) -> bool:
    lower = model.lower()
    return any(token in lower for token in ("vision", "multimodal", "gpt-4o", "gemini", "claude", "image", "video", "scout", "flash"))


def _needs_visual_detail(task: str, asset_type: str) -> bool:
    lower = f"{task} {asset_type}".lower()
    return any(token in lower for token in ("image", "video", "design", "layout", "animation", "visual", "photo", "screenshot", "building", "interior", "exterior", "figma"))


def _is_simple_visual_task(task: str) -> bool:
    lower = task.lower()
    simple = any(token in lower for token in ("simple", "basic", "quick", "plain"))
    complex_signals = any(token in lower for token in ("full app", "building", "interior", "exterior", "dashboard", "animation", "exact", "detailed"))
    return simple and not complex_signals

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaAppAdapter:
    name: str
    category: str
    executable_hints: tuple[str, ...]
    capabilities: tuple[str, ...]
    automation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "executable_hints": list(self.executable_hints),
            "capabilities": list(self.capabilities),
            "automation": self.automation,
        }


MEDIA_APP_ADAPTERS: tuple[MediaAppAdapter, ...] = (
    MediaAppAdapter("Adobe Photoshop", "photo", ("Photoshop.exe", "photoshop"), ("layers", "retouch", "generative_fill", "batch_export"), "plugin_or_cli_bridge"),
    MediaAppAdapter("Adobe Lightroom", "photo", ("Lightroom.exe", "lightroom"), ("raw_develop", "color_grade", "batch_presets"), "preset_export_bridge"),
    MediaAppAdapter("Adobe Illustrator", "vector", ("Illustrator.exe", "illustrator"), ("vector_edit", "logo_mockup", "svg_export"), "script_bridge"),
    MediaAppAdapter("Adobe Premiere Pro", "video", ("Adobe Premiere Pro.exe", "premiere"), ("timeline", "cuts", "captions", "color", "export"), "extendscript_or_plugin_bridge"),
    MediaAppAdapter("Adobe After Effects", "motion", ("AfterFX.exe", "after effects"), ("motion_graphics", "compositing", "mockup_video", "render_queue"), "extendscript_bridge"),
    MediaAppAdapter("Adobe Media Encoder", "video", ("Adobe Media Encoder.exe", "ame"), ("transcode", "batch_render", "proxy_export"), "watch_folder_or_cli_bridge"),
    MediaAppAdapter("Adobe Audition", "audio", ("Adobe Audition.exe", "audition"), ("noise_reduction", "voiceover_edit", "podcast_mix", "batch_export"), "extendscript_or_plugin_bridge"),
    MediaAppAdapter("DaVinci Resolve", "video", ("Resolve.exe", "resolve"), ("edit", "fusion", "color", "fairlight", "deliver"), "python_lua_api"),
    MediaAppAdapter("CapCut", "video", ("CapCut.exe", "capcut"), ("short_form", "captions", "templates", "social_export"), "desktop_project_bridge"),
    MediaAppAdapter("Final Cut Pro", "video", ("Final Cut Pro",), ("timeline", "titles", "effects", "export"), "fcpxml_bridge"),
    MediaAppAdapter("Blender", "3d", ("blender.exe", "blender"), ("3d_mockup", "animation", "render", "glb_export"), "python_cli"),
    MediaAppAdapter("Figma", "design", ("figma",), ("design_mockup", "prototype", "components", "handoff"), "mcp_or_plugin_bridge"),
    MediaAppAdapter("Canva", "design", ("canva",), ("templates", "social_assets", "brand_kit"), "browser_or_api_bridge"),
    MediaAppAdapter("GIMP", "photo", ("gimp.exe", "gimp"), ("retouch", "layers", "batch_edit"), "script_fu_python"),
    MediaAppAdapter("Krita", "photo", ("krita.exe", "krita"), ("paint", "storyboard", "frame_animation"), "python_plugin"),
    MediaAppAdapter("Affinity Photo", "photo", ("Photo.exe", "affinity photo"), ("retouch", "layers", "export"), "macro_bridge"),
    MediaAppAdapter("Affinity Designer", "vector", ("Designer.exe", "affinity designer"), ("vector_edit", "mockup", "export"), "macro_bridge"),
    MediaAppAdapter("Runway", "video_ai", ("runway",), ("text_to_video", "image_to_video", "background_remove"), "api_bridge"),
    MediaAppAdapter("Pika", "video_ai", ("pika",), ("text_to_video", "image_to_video", "mockup_video"), "api_bridge"),
    MediaAppAdapter("Kling", "video_ai", ("kling",), ("text_to_video", "image_to_video"), "api_bridge"),
    MediaAppAdapter("ElevenLabs", "audio_ai", ("elevenlabs",), ("speech_to_text", "text_to_speech", "voice_clone", "voiceover"), "api_bridge"),
    MediaAppAdapter("Manus", "agent_ai", ("manus",), ("agent_workflow", "browser_control", "voice_task_routing", "project_automation"), "api_or_browser_bridge"),
    MediaAppAdapter("Whisper", "audio_ai", ("whisper", "whisper.cpp"), ("speech_to_text", "translation", "subtitle_transcription"), "local_or_api_bridge"),
    MediaAppAdapter("Audacity", "audio", ("audacity.exe", "audacity"), ("waveform_edit", "noise_reduction", "export"), "macro_or_cli_bridge"),
    MediaAppAdapter("Stable Diffusion", "image_ai", ("automatic1111", "comfyui", "forge"), ("text_to_image", "image_to_image", "controlnet", "inpaint"), "local_http_api"),
    MediaAppAdapter("ComfyUI", "image_video_ai", ("comfyui", "python main.py"), ("workflow_graph", "image_generation", "video_generation"), "local_http_api"),
)


def list_media_apps(category: str | None = None) -> list[dict]:
    apps = MEDIA_APP_ADAPTERS
    if category:
        needle = category.lower()
        apps = tuple(app for app in apps if needle in app.category.lower() or needle in " ".join(app.capabilities).lower())
    return [app.to_dict() for app in apps]


def build_mockup_video_plan(prompt: str, app: str = "auto") -> dict:
    preferred = [
        adapter for adapter in MEDIA_APP_ADAPTERS
        if "mockup_video" in adapter.capabilities or adapter.category in {"motion", "3d", "video_ai"}
    ]
    selected = preferred[0] if app == "auto" else next((item for item in MEDIA_APP_ADAPTERS if item.name.lower() == app.lower()), preferred[0])
    return {
        "prompt": prompt,
        "selected_app": selected.to_dict(),
        "steps": [
            "create storyboard frames",
            "generate or import visual assets",
            "animate camera/motion/transitions",
            "render lightweight preview",
            "export MP4/WebM plus poster frame",
        ],
        "performance_guardrails": {
            "preview_resolution": "720p",
            "draft_fps": 24,
            "final_render_requires_user_approval": True,
        },
    }


def build_voice_workflow_plan(prompt: str, mode: str = "speech_to_text", provider: str = "auto") -> dict:
    preferred = [
        adapter for adapter in MEDIA_APP_ADAPTERS
        if mode in adapter.capabilities or adapter.category in {"audio_ai", "audio"}
    ]
    selected = preferred[0] if provider == "auto" else next((item for item in MEDIA_APP_ADAPTERS if item.name.lower() == provider.lower()), preferred[0])
    if mode in {"text_to_speech", "tts", "voice_generation"}:
        steps = [
            "normalize script and pronunciation hints",
            "select voice, language, speed, and output format",
            "synthesize short preview before full render",
            "run audio QA for clipping, pacing, and artifacts",
            "export voiceover asset and transcript metadata",
        ]
    else:
        steps = [
            "validate audio format and duration",
            "transcribe with language and prompt hints when available",
            "clean transcript and preserve timestamps",
            "handoff subtitle or localization work to specialist agents",
            "store transcript artifact for council/master review",
        ]
    return {
        "prompt": prompt,
        "mode": mode,
        "selected_app": selected.to_dict(),
        "steps": steps,
        "performance_guardrails": {
            "chunk_long_audio": True,
            "preview_before_full_voice_render": True,
            "requires_user_approval_for_voice_clone": True,
        },
    }

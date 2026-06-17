import json
import os
import socket
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


PROVIDER_PRIORITY = [
    "azure",
    "openai",
    "anthropic",
    "moonshot",
    "openclaw",
    "manus",
    "google",
    "openrouter",
    "elevenlabs",
    "recraft",
    "kling",
    "nvidia",
    "huggingface",
    "alibaba",
    "microsoft",
    "zyphra",
    "groq",
    "together",
    "perplexity",
    "cohere",
    "mistral",
    "deepseek",
    "xai",
    "ollama",
    "lmstudio",
    "vllm",
    "llamacpp",
    "local",
]

PROVIDER_ALIASES = {
    "azure": "azure", "azure-openai": "azure", "azure-foundry": "azure",
    "azure-ai-foundry": "azure", "ai-foundry": "azure", "foundry": "azure",
    "openai": "openai",
    "anthropic": "anthropic", "anthropic-claude": "anthropic", "claude": "anthropic",
    "moonshot": "moonshot", "moonshot-ai": "moonshot", "kimi": "moonshot", "kimi-ai": "moonshot",
    "openclaw": "openclaw", "open-claw": "openclaw", "claw": "openclaw",
    "manus": "manus", "manus-ai": "manus", "manusai": "manus",
    "google": "google", "google-ai": "google", "googleai": "google",
    "openrouter": "openrouter",
    "elevenlabs": "elevenlabs", "eleven-labs": "elevenlabs", "11labs": "elevenlabs",
    "recraft": "recraft", "recraft-ai": "recraft",
    "kling": "kling", "kling-ai": "kling", "klingapi": "kling",
    "nvidia": "nvidia", "nvidia-nim": "nvidia", "nim": "nvidia",
    "huggingface": "huggingface", "hugging-face": "huggingface", "hf": "huggingface",
    "alibaba": "alibaba", "alibaba-cloud": "alibaba", "dashscope": "alibaba", "qwen": "alibaba",
    "microsoft": "microsoft", "azure-ai": "microsoft", "azure-ai-inference": "microsoft",
    "zyphra": "zyphra", "zonos": "zyphra",
    "groq": "groq",
    "together": "together", "together-ai": "together", "togetherai": "together",
    "perplexity": "perplexity", "purplexity": "perplexity",
    "cohere": "cohere", "cohere-ai": "cohere",
    "mistral": "mistral", "mistral-ai": "mistral",
    "deepseek": "deepseek",
    "xai": "xai", "x-ai": "xai", "grok": "xai",
    "ollama": "ollama", "ollama-ai": "ollama", "local-ollama": "ollama",
    "lmstudio": "lmstudio", "lm-studio": "lmstudio", "localai": "lmstudio", "local-ai": "lmstudio",
    "vllm": "vllm",
    "llamacpp": "llamacpp", "llama-cpp": "llamacpp", "llama.cpp": "llamacpp",
    "local": "local",
}

FREE_KEYWORDS = ["free", "mini", "nano", "flash", "small", "tiny"]
IMAGE_GENERATION_KEYWORDS = [
    "image",
    "img",
    "dall-e",
    "dalle",
    "gpt-image",
    "imagen",
    "omni",
    "omnigen",
    "google-flow",
    "googleflow",
    "flux",
    "recraft",
    "recraftv",
    "imagine",
    "nano-banana",
    "nanobanana",
    "banana",
    "stable-diffusion",
    "sdxl",
]
VIDEO_GENERATION_KEYWORDS = [
    "video",
    "sora",
    "veo",
    "veo-2",
    "veo-3",
    "google-flow",
    "googleflow",
    "omni",
    "runway",
    "kling",
    "kling-ai",
    "kling-v",
    "kling-video",
    "seedance",
    "sedance",
    "highfield",
    "wan",
    "gen-",
    "motion",
]
SPEECH_TO_TEXT_KEYWORDS = [
    "speech-to-text",
    "speech_to_text",
    "stt",
    "transcribe",
    "transcription",
    "whisper",
    "scribe",
]
TEXT_TO_SPEECH_KEYWORDS = [
    "text-to-speech",
    "text_to_speech",
    "tts",
    "speech",
    "voice",
    "eleven",
    "zyphra",
    "zonos",
]
VISION_KEYWORDS = [
    "vision",
    "multimodal",
    "gpt-4o",
    "gpt-4.1",
    "gemini",
    "omni",
    "google-flow",
    "googleflow",
    "veo",
    "claude",
    "kimi",
    "image",
    "video",
    "scout",
    "flash",
]

LOCAL_MODEL_PORTS = [
    ("ollama", 11434),
    ("lmstudio", 1234),
    ("vllm", 8000),
    ("llamacpp", 8080),
]


@dataclass
class MCPServerConfig:
    name: str
    transport: str = "stdio"
    command: Optional[str] = None
    args: list = field(default_factory=list)
    url: Optional[str] = None
    env: dict = field(default_factory=dict)
    auto_discover: bool = True


def normalize_provider_name(raw: str) -> str:
    return PROVIDER_ALIASES.get(raw.lower(), raw.lower())


def _is_cheap_model(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in FREE_KEYWORDS)


def _model_supports(model_name: str, model_config: dict | None, kind: str) -> bool:
    cfg = model_config or {}
    modalities = cfg.get("modalities") or cfg.get("capabilities") or cfg.get("supports") or []
    if isinstance(modalities, str):
        modalities = [modalities]
    modality_text = " ".join(str(item).lower() for item in modalities)
    if kind in modality_text or f"{kind}_generation" in modality_text or f"{kind}-generation" in modality_text:
        return True
    if kind == "vision" and any(token in modality_text for token in ("image", "video", "multimodal", "vision")):
        return True

    model_type = str(cfg.get("type") or cfg.get("kind") or cfg.get("mode") or "").lower()
    if kind in model_type and "generation" in model_type:
        return True
    if kind == "vision" and any(token in model_type for token in ("vision", "multimodal", "image", "video")):
        return True

    lower = model_name.lower()
    if kind == "image":
        keywords = IMAGE_GENERATION_KEYWORDS
    elif kind == "video":
        keywords = VIDEO_GENERATION_KEYWORDS
    elif kind in {"speech_to_text", "audio_transcription"}:
        keywords = SPEECH_TO_TEXT_KEYWORDS
    elif kind in {"text_to_speech", "speech_synthesis"}:
        keywords = TEXT_TO_SPEECH_KEYWORDS
    elif kind == "vision":
        keywords = VISION_KEYWORDS
    else:
        keywords = []
    return any(token in lower for token in keywords)


def _check_port(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.gaierror):
        return False


def _detect_local_models() -> dict:
    providers = {}
    for name, port in LOCAL_MODEL_PORTS:
        if _check_port("127.0.0.1", port) or _check_port("localhost", port):
            endpoint = f"http://localhost:{port}/v1"
            providers[name] = ProviderConfig(
                api_key="",
                endpoint=endpoint,
            )
    return providers


@dataclass
class ProviderConfig:
    api_key: str
    endpoint: Optional[str] = None
    models: dict = field(default_factory=dict)

    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


@dataclass
class SwarmConfig:
    max_iterations: int = 25
    agent_timeout_seconds: int = 60
    loop_detection_threshold: int = 3
    default_temperature: float = 0.3
    default_max_tokens: int = 4096
    triage_model: Optional[str] = None
    worker_model: Optional[str] = None
    providers: dict = field(default_factory=dict)
    mcp_servers: list = field(default_factory=list)
    state_dir: str = "swarm_state"

    @classmethod
    def auto_detect(cls) -> "SwarmConfig":
        cfg = cls()
        providers = {}

        azure_key = os.environ.get("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if azure_key and azure_endpoint:
            providers["azure"] = ProviderConfig(
                api_key=azure_key,
                endpoint=azure_endpoint,
            )

        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key:
            providers["openrouter"] = ProviderConfig(
                api_key=openrouter_key,
                endpoint=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            )

        google_key = os.environ.get("GOOGLE_API_KEY")
        if google_key:
            providers["google"] = ProviderConfig(
                api_key=google_key,
                endpoint="https://generativelanguage.googleapis.com/v1beta",
            )

        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            openai_models = {}
            if os.environ.get("OPENAI_IMAGE_MODEL"):
                openai_models[os.environ["OPENAI_IMAGE_MODEL"]] = {"modalities": ["image_generation"]}
            if os.environ.get("OPENAI_VIDEO_MODEL"):
                openai_models[os.environ["OPENAI_VIDEO_MODEL"]] = {"modalities": ["video_generation"]}
            if os.environ.get("OPENAI_TRANSCRIPTION_MODEL"):
                openai_models[os.environ["OPENAI_TRANSCRIPTION_MODEL"]] = {"modalities": ["speech_to_text"]}
            if os.environ.get("OPENAI_TTS_MODEL"):
                openai_models[os.environ["OPENAI_TTS_MODEL"]] = {"modalities": ["text_to_speech"]}
            providers["openai"] = ProviderConfig(
                api_key=openai_key,
                models=openai_models,
            )

        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            providers["anthropic"] = ProviderConfig(
                api_key=anthropic_key,
            )

        moonshot_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
        if moonshot_key:
            moonshot_model = os.environ.get("MOONSHOT_MODEL") or os.environ.get("KIMI_MODEL") or "kimi-k2.6"
            providers["moonshot"] = ProviderConfig(
                api_key=moonshot_key,
                endpoint=os.environ.get("MOONSHOT_BASE_URL") or os.environ.get("KIMI_BASE_URL") or "https://api.moonshot.ai/v1",
                models={moonshot_model: {"modalities": ["chat", "reasoning", "coding"]}},
            )

        openclaw_endpoint = os.environ.get("OPENCLAW_BASE_URL") or os.environ.get("OPENCLAW_ENDPOINT")
        if openclaw_endpoint:
            openclaw_model = os.environ.get("OPENCLAW_MODEL", "openclaw/default")
            providers["openclaw"] = ProviderConfig(
                api_key=os.environ.get("OPENCLAW_API_KEY", ""),
                endpoint=openclaw_endpoint,
                models={openclaw_model: {}},
            )

        manus_key = os.environ.get("MANUS_API_KEY")
        manus_endpoint = os.environ.get("MANUS_BASE_URL") or os.environ.get("MANUS_ENDPOINT")
        if manus_key or manus_endpoint:
            manus_model = os.environ.get("MANUS_MODEL", "manus/default")
            providers["manus"] = ProviderConfig(
                api_key=manus_key or "",
                endpoint=manus_endpoint,
                models={manus_model: {}},
            )

        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY")
        if elevenlabs_key:
            providers["elevenlabs"] = ProviderConfig(
                api_key=elevenlabs_key,
                endpoint=os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1"),
                models={
                    os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v1"): {"modalities": ["speech_to_text"]},
                    os.environ.get("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2"): {"modalities": ["text_to_speech"]},
                },
            )

        recraft_key = os.environ.get("RECRAFT_API_KEY") or os.environ.get("RECRAFT_API_TOKEN")
        if recraft_key:
            providers["recraft"] = ProviderConfig(
                api_key=recraft_key,
                endpoint=os.environ.get("RECRAFT_BASE_URL", "https://external.api.recraft.ai/v1"),
                models={os.environ.get("RECRAFT_IMAGE_MODEL", "recraftv4_1"): {"modalities": ["image_generation"]}},
            )

        kling_key = os.environ.get("KLING_API_KEY") or os.environ.get("KLINGAI_API_KEY")
        if kling_key:
            providers["kling"] = ProviderConfig(
                api_key=kling_key,
                endpoint=os.environ.get("KLING_BASE_URL", "https://api.klingapi.com"),
                models={os.environ.get("KLING_VIDEO_MODEL", "kling-v2.6-pro"): {"modalities": ["video_generation"]}},
            )

        nvidia_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY")
        if nvidia_key:
            providers["nvidia"] = ProviderConfig(
                api_key=nvidia_key,
                endpoint=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
                models={os.environ.get("NVIDIA_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1"): {"modalities": ["chat", "reasoning"]}},
            )

        huggingface_key = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        if huggingface_key:
            providers["huggingface"] = ProviderConfig(
                api_key=huggingface_key,
                endpoint=os.environ.get("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1"),
                models={
                    os.environ.get("HUGGINGFACE_MODEL", "openai/gpt-oss-120b:fastest"): {"modalities": ["chat", "reasoning"]},
                    os.environ.get("HUGGINGFACE_IMAGE_MODEL", "black-forest-labs/FLUX.1-dev"): {"modalities": ["image_generation"]},
                    os.environ.get("HUGGINGFACE_VIDEO_MODEL", "Wan-AI/Wan2.2-T2V-A14B"): {"modalities": ["video_generation"]},
                },
            )

        alibaba_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ALIBABA_API_KEY")
        if alibaba_key:
            providers["alibaba"] = ProviderConfig(
                api_key=alibaba_key,
                endpoint=os.environ.get("DASHSCOPE_BASE_URL") or os.environ.get("ALIBABA_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                models={os.environ.get("ALIBABA_MODEL", "qwen-plus"): {"modalities": ["chat", "reasoning"]}},
            )

        perplexity_key = os.environ.get("PERPLEXITY_API_KEY") or os.environ.get("PURPLEXITY_API_KEY")
        if perplexity_key:
            providers["perplexity"] = ProviderConfig(
                api_key=perplexity_key,
                endpoint=os.environ.get("PERPLEXITY_BASE_URL", "https://api.perplexity.ai"),
                models={os.environ.get("PERPLEXITY_MODEL", "sonar-pro"): {"modalities": ["chat", "research"]}},
            )

        microsoft_key = os.environ.get("MICROSOFT_AI_API_KEY") or os.environ.get("AZURE_AI_FOUNDRY_API_KEY")
        microsoft_endpoint = os.environ.get("MICROSOFT_AI_ENDPOINT") or os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")
        if microsoft_key and microsoft_endpoint:
            providers["microsoft"] = ProviderConfig(
                api_key=microsoft_key,
                endpoint=microsoft_endpoint,
                models={os.environ.get("MICROSOFT_MODEL", "phi-4"): {"modalities": ["chat", "reasoning"]}},
            )

        zyphra_key = os.environ.get("ZYPHRA_API_KEY")
        if zyphra_key:
            providers["zyphra"] = ProviderConfig(
                api_key=zyphra_key,
                endpoint=os.environ.get("ZYPHRA_BASE_URL", "https://api.zyphra.com/v1"),
                models={os.environ.get("ZYPHRA_TTS_MODEL", "zonos-v0.1-transformer"): {"modalities": ["text_to_speech"]}},
            )

        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            providers["groq"] = ProviderConfig(
                api_key=groq_key,
                endpoint="https://api.groq.com/openai/v1",
            )

        local_providers = _detect_local_models()
        providers.update(local_providers)

        cfg.providers = providers
        return cfg

    @classmethod
    def from_opencode_config(cls, path: Optional[str] = None) -> "SwarmConfig":
        if path is None:
            home = Path.home()
            candidates = [
                home / ".config" / "opencode" / "opencode.jsonc",
                home / ".config" / "opencode" / "opencode.json",
                Path.cwd() / "opencode.jsonc",
                Path.cwd() / "opencode.json",
            ]
            for c in candidates:
                if c.exists():
                    path = str(c)
                    break

        if not path or not os.path.exists(path):
            return cls.auto_detect()

        raw = Path(path).read_text(encoding="utf-8")
        import re

        def strip_jsonc(text: str) -> str:
            result = []
            i = 0
            in_string = False
            in_single_line_comment = False
            in_multi_line_comment = False
            while i < len(text):
                ch = text[i]
                if in_single_line_comment:
                    if ch == "\n":
                        in_single_line_comment = False
                        result.append(ch)
                    i += 1
                    continue
                if in_multi_line_comment:
                    if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                        in_multi_line_comment = False
                        i += 2
                        continue
                    i += 1
                    continue
                if in_string:
                    if ch == "\\" and i + 1 < len(text):
                        result.append(ch)
                        result.append(text[i + 1])
                        i += 2
                        continue
                    if ch == '"':
                        in_string = False
                    result.append(ch)
                    i += 1
                    continue
                if ch == '"':
                    in_string = True
                    result.append(ch)
                    i += 1
                    continue
                if ch == "/" and i + 1 < len(text):
                    if text[i + 1] == "/":
                        in_single_line_comment = True
                        i += 2
                        continue
                    if text[i + 1] == "*":
                        in_multi_line_comment = True
                        i += 2
                        continue
                result.append(ch)
                i += 1
            return "".join(result)

        raw = strip_jsonc(raw)
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        data = json.loads(raw)

        cfg = cls()
        providers = {}
        provider_configs = data.get("provider", {})

        for name, pc in provider_configs.items():
            options = pc.get("options", {})
            api_key = options.get("apiKey") or os.environ.get(f"{name.upper()}_API_KEY", "")
            endpoint = (
                options.get("endpoint")
                or options.get("baseUrl")
                or options.get("baseURL")
                or pc.get("endpoint")
                or pc.get("baseUrl")
                or pc.get("baseURL")
            )
            models = pc.get("models", {})

            providers[name] = ProviderConfig(
                api_key=api_key,
                endpoint=endpoint,
                models=models,
            )

        mcp_configs = data.get("mcpServers", {})
        for mcp_name, mc in mcp_configs.items():
            transport = mc.get("transport", mc.get("type", "stdio"))
            command = mc.get("command")
            args = mc.get("args", [])
            url = mc.get("url")
            env = mc.get("env", {})
            cfg.mcp_servers.append(MCPServerConfig(
                name=mcp_name,
                transport=transport,
                command=command,
                args=args,
                url=url,
                env=env,
            ))

        local_providers = _detect_local_models()
        for name, lpc in local_providers.items():
            if name not in providers:
                providers[name] = lpc

        cfg.providers = providers
        return cfg

    def _sorted_providers(self) -> list[tuple[str, ProviderConfig]]:
        """Return configured providers sorted by priority (best first)."""
        scored = []
        for cfg_name, pc in self.providers.items():
            normalized = normalize_provider_name(cfg_name)
            try:
                priority = PROVIDER_PRIORITY.index(normalized)
            except ValueError:
                priority = len(PROVIDER_PRIORITY) + 10
            scored.append((priority, cfg_name, pc))
        scored.sort(key=lambda x: x[0])
        return [(cn, pc) for _, cn, pc in scored]

    def _find_provider(self, names: list[str]) -> tuple[Optional[str], Optional[ProviderConfig]]:
        for target in names:
            for cfg_name, pc in self.providers.items():
                if normalize_provider_name(cfg_name) == target:
                    return cfg_name, pc
        return None, None

    def get_best_model(self) -> Optional[str]:
        for cfg_name, pc in self._sorted_providers():
            if pc.models:
                first_model = next(iter(pc.models.keys()))
                return f"{cfg_name}:{first_model}"
        return None

    def get_cheapest_model(self) -> Optional[str]:
        cheapest = None
        cheapest_priority = -1
        for cfg_name, pc in self._sorted_providers():
            if not pc.models:
                continue
            normalized = normalize_provider_name(cfg_name)
            try:
                priority = PROVIDER_PRIORITY.index(normalized)
            except ValueError:
                priority = len(PROVIDER_PRIORITY) + 10
            for model_name in pc.models:
                if _is_cheap_model(model_name):
                    if cheapest is None or priority > cheapest_priority:
                        cheapest = f"{cfg_name}:{model_name}"
                        cheapest_priority = priority
        if cheapest:
            return cheapest
        for cfg_name, pc in reversed(self._sorted_providers()):
            if pc.models:
                first_model = next(iter(pc.models.keys()))
                return f"{cfg_name}:{first_model}"
        return None

    def get_media_models(self, kind: str) -> list[str]:
        matches = []
        for cfg_name, pc in self._sorted_providers():
            for model_name, model_config in pc.models.items():
                cfg = model_config if isinstance(model_config, dict) else {}
                if _model_supports(model_name, cfg, kind):
                    matches.append(f"{cfg_name}:{model_name}")
        return matches

    def get_best_image_model(self) -> Optional[str]:
        models = self.get_media_models("image")
        return models[0] if models else None

    def get_best_video_model(self) -> Optional[str]:
        models = self.get_media_models("video")
        return models[0] if models else None

    def get_best_vision_model(self) -> Optional[str]:
        models = self.get_media_models("vision")
        return models[0] if models else None

    def get_best_speech_to_text_model(self) -> Optional[str]:
        models = self.get_media_models("speech_to_text")
        return models[0] if models else None

    def get_best_text_to_speech_model(self) -> Optional[str]:
        models = self.get_media_models("text_to_speech")
        return models[0] if models else None

    def find_model(self, preference: str = "best") -> str:
        if preference in {"image", "image_generation", "image-generation"}:
            m = self.get_best_image_model()
            if m:
                return m
        if preference in {"video", "video_generation", "video-generation"}:
            m = self.get_best_video_model()
            if m:
                return m
        if preference in {"vision", "multimodal", "temporary_vision"}:
            m = self.get_best_vision_model()
            if m:
                return m
        if preference in {"speech_to_text", "speech-to-text", "transcription", "audio_transcription"}:
            m = self.get_best_speech_to_text_model()
            if m:
                return m
        if preference in {"text_to_speech", "text-to-speech", "speech_synthesis", "voice_generation"}:
            m = self.get_best_text_to_speech_model()
            if m:
                return m
        if preference == "best":
            m = self.get_best_model()
            if m:
                return m
        if preference == "cheap":
            m = self.get_cheapest_model()
            if m:
                return m
        if preference == "triage" and self.triage_model:
            return self.triage_model
        if preference == "worker" and self.worker_model:
            return self.worker_model
        m = self.get_best_model()
        if m:
            return m
        return "openrouter:openrouter/free"

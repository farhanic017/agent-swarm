from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)
    finish_reason: str = "stop"


@dataclass
class ToolCall:
    id: str
    type: str = "function"
    function: dict = field(default_factory=dict)


@dataclass
class MediaGenerationRequest:
    prompt: str
    model: Optional[str] = None
    size: Optional[str] = None
    quality: Optional[str] = None
    duration: Optional[int] = None
    fps: Optional[int] = None
    output_format: Optional[str] = None
    reference_paths: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class MediaGenerationResponse:
    kind: str
    model: str
    provider: str
    assets: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class AudioTranscriptionRequest:
    audio_path: str
    model: Optional[str] = None
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class AudioSpeechRequest:
    text: str
    model: Optional[str] = None
    voice: Optional[str] = None
    output_format: Optional[str] = None
    speed: Optional[float] = None
    extra: dict = field(default_factory=dict)


@dataclass
class AudioResponse:
    kind: str
    model: str
    provider: str
    text: str = ""
    assets: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class ToolDef:
    def __init__(self, name: str, description: str, parameters: dict):
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class Message:
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list,
        tools: Optional[list] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        ...

    async def generate_image(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        raise NotImplementedError(f"{self.__class__.__name__} does not support image generation")

    async def generate_video(self, request: MediaGenerationRequest) -> MediaGenerationResponse:
        raise NotImplementedError(f"{self.__class__.__name__} does not support video generation")

    async def transcribe_audio(self, request: AudioTranscriptionRequest) -> AudioResponse:
        raise NotImplementedError(f"{self.__class__.__name__} does not support speech-to-text")

    async def synthesize_speech(self, request: AudioSpeechRequest) -> AudioResponse:
        raise NotImplementedError(f"{self.__class__.__name__} does not support text-to-speech")

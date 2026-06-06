from __future__ import annotations

from dataclasses import dataclass

from swarm.config import SwarmConfig, normalize_provider_name
from swarm.core.agent import Agent


@dataclass(frozen=True)
class ProviderAssignment:
    agent_name: str
    role: str
    provider: str
    model: str
    model_ref: str
    opencode_model: str
    model_preference: str
    parent_agent: str = ""
    route_type: str = "cloud"
    score: int = 0
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "model_ref": self.model_ref,
            "opencode_model": self.opencode_model,
            "model_preference": self.model_preference,
            "parent_agent": self.parent_agent,
            "route_type": self.route_type,
            "score": self.score,
            "rationale": self.rationale,
        }


def assign_distinct_provider_models(
    agents: list[Agent],
    config: SwarmConfig,
    include_sub_agents: bool = True,
    limit: int | None = None,
) -> list[ProviderAssignment]:
    candidates = [
        _candidate(provider_name, model_name)
        for provider_name, provider_config in config.providers.items()
        for model_name in provider_config.models.keys()
    ]
    if not candidates:
        return []

    provider_order = [
        name
        for name, provider_config in config.providers.items()
        if provider_config.models
    ]
    if not provider_order:
        return []

    work_items: list[tuple[Agent, str, str]] = _build_work_items(agents, include_sub_agents)

    if limit is not None:
        work_items = work_items[:limit]

    assignments = []
    used_providers: list[str] = []
    for index, (agent, role, parent_agent) in enumerate(work_items):
        best = _select_best_candidate(agent, role, candidates, used_providers)
        used_providers.append(best["provider"])
        assignments.append(
            ProviderAssignment(
                agent_name=agent.name,
                role=role,
                provider=best["provider"],
                model=best["model"],
                model_ref=f"{best['provider']}:{best['model']}",
                opencode_model=f"{best['provider']}/{best['model']}",
                model_preference=agent.model_preference,
                parent_agent=parent_agent,
                route_type=best["route_type"],
                score=best["score"],
                rationale=best["rationale"],
            )
        )
    return assignments


def _build_work_items(agents: list[Agent], include_sub_agents: bool) -> list[tuple[Agent, str, str]]:
    work_items: list[tuple[Agent, str, str]] = []
    for agent in agents:
        role = "master" if agent.name in {"council_master", "master"} else "agent"
        work_items.append((agent, role, ""))
        if include_sub_agents:
            for sub_agent_name in agent.sub_agent_roles[:2]:
                sub_agent = next((candidate for candidate in agents if candidate.name == sub_agent_name), None)
                if sub_agent:
                    work_items.append((sub_agent, "sub_agent", agent.name))
    return work_items


def _candidate(provider: str, model: str) -> dict:
    provider_norm = normalize_provider_name(provider)
    model_lower = model.lower()
    route_type = "cloud"
    if provider_norm == "openclaw":
        route_type = "agent_gateway"
    elif provider_norm in {"ollama", "lmstudio", "vllm", "llamacpp", "local"}:
        route_type = "local"
    elif provider_norm in {"mcp"} or provider.lower().startswith("mcp"):
        route_type = "mcp"

    specialties = set()
    if any(token in model_lower for token in ("coder", "code", "qwen", "codestral", "gpt-oss", "glm")):
        specialties.add("coding")
    if any(token in model_lower for token in ("reason", "r1", "o4", "o3", "gpt-5", "glm", "deepseek")):
        specialties.add("reasoning")
    if any(token in model_lower for token in ("hermes", "nous")):
        specialties.update({"chat", "reasoning"})
    if any(token in model_lower for token in ("vision", "multimodal", "image", "flash", "scout")):
        specialties.add("vision")
    if any(token in model_lower for token in ("image", "img", "dall-e", "dalle", "gpt-image", "imagen", "flux", "imagine", "nano-banana", "nanobanana", "banana", "stable-diffusion", "sdxl")):
        specialties.update({"image_generation", "vision"})
    if any(token in model_lower for token in ("video", "sora", "veo", "runway", "kling", "seedance", "sedance", "highfield", "wan", "motion")):
        specialties.update({"video_generation", "vision"})
    if any(token in model_lower for token in ("speech-to-text", "speech_to_text", "stt", "transcribe", "transcription", "whisper", "scribe")):
        specialties.add("speech_to_text")
    if any(token in model_lower for token in ("text-to-speech", "text_to_speech", "tts", "voice", "speech", "eleven")):
        specialties.add("text_to_speech")
    if any(token in model_lower for token in ("mini", "small", "flash", "instant", "haiku", "nano")):
        specialties.add("chat")
    if not specialties:
        specialties.add("general")

    cheap = any(token in model_lower for token in ("free", "mini", "nano", "flash", "small", "instant"))
    premium = any(token in model_lower for token in ("opus", "gpt-5.4", "gpt-5", "large", "pro"))
    return {
        "provider": provider,
        "model": model,
        "route_type": route_type,
        "specialties": specialties,
        "cheap": cheap,
        "premium": premium,
    }


def _select_best_candidate(agent: Agent, role: str, candidates: list[dict], used_providers: list[str]) -> dict:
    all_providers = {candidate["provider"] for candidate in candidates}
    unused_providers = all_providers - set(used_providers)
    scoring_pool = (
        [candidate for candidate in candidates if candidate["provider"] in unused_providers]
        if unused_providers
        else candidates
    )
    scored = []
    for candidate in scoring_pool:
        score, reasons = _score_candidate(agent, role, candidate, used_providers)
        item = dict(candidate)
        item["score"] = score
        item["rationale"] = "; ".join(reasons)
        scored.append(item)
    scored.sort(key=lambda item: (item["score"], -used_providers.count(item["provider"])), reverse=True)
    return scored[0]


def _score_candidate(agent: Agent, role: str, candidate: dict, used_providers: list[str]) -> tuple[int, list[str]]:
    preference = agent.model_preference
    score = 0
    reasons = []
    core_decision_agent = agent.name in {"triage", "council_master", "master"}
    desired_preference = "reasoning" if preference == "best" or core_decision_agent else preference

    if desired_preference in candidate["specialties"]:
        score += 50
        reasons.append(f"matches {desired_preference}")
    elif desired_preference in {"image_generation", "video_generation"} and "vision" in candidate["specialties"]:
        score += 30
        reasons.append("vision fallback for media generation")
    elif desired_preference in {"speech_to_text", "text_to_speech"} and candidate["provider"].lower() == "elevenlabs":
        score += 45
        reasons.append("ElevenLabs voice provider fit")
    elif "general" in candidate["specialties"]:
        score += 12
        reasons.append("general fallback")

    if role == "master" or core_decision_agent:
        if "reasoning" in candidate["specialties"]:
            score += 25
            reasons.append("decision agent needs reasoning")
        if candidate["premium"]:
            score += 10
            reasons.append("premium decision model")
        if candidate["route_type"] == "mcp":
            score -= 18
            reasons.append("decision agent avoids tool-only route")
    elif role == "sub_agent":
        if candidate["cheap"] or candidate["route_type"] in {"local", "mcp"}:
            score += 18
            reasons.append("sub-agent cost efficient")
    else:
        if candidate["premium"] and desired_preference in {"reasoning", "coding"}:
            score += 8
            reasons.append("strong primary model")

    if candidate["route_type"] == "local" and role == "sub_agent":
        score += 22
        reasons.append("local helper workload")
    if candidate["route_type"] == "mcp" and agent.name in {"researcher", "analytics", "figma_controller"}:
        score += 20
        reasons.append("MCP-friendly specialist")
    if candidate["route_type"] == "agent_gateway":
        if agent.pillar == "act" or agent.name in {"triage", "council_master"}:
            score += 16
            reasons.append("OpenClaw agent gateway fit")
        if role == "sub_agent":
            score -= 10
            reasons.append("gateway reserved for orchestration")
    if candidate["provider"] not in used_providers:
        score += 35
        reasons.append("provider diversity")
    else:
        score -= min(45, used_providers.count(candidate["provider"]) * 12)

    if not reasons:
        reasons.append("fallback candidate")
    return score, reasons


def assign_hybrid_provider_models(
    agents: list[Agent],
    config: SwarmConfig,
    include_sub_agents: bool = True,
    limit: int | None = None,
) -> list[ProviderAssignment]:
    return assign_distinct_provider_models(
        agents=agents,
        config=config,
        include_sub_agents=include_sub_agents,
        limit=limit,
    )


def summarize_hybrid_routes(assignments: list[ProviderAssignment]) -> dict:
    summary: dict[str, int] = {"local": 0, "mcp": 0, "cloud": 0}
    for assignment in assignments:
        summary[assignment.route_type] = summary.get(assignment.route_type, 0) + 1
    return summary

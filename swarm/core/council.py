from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import mean

from swarm.core.agent import Agent


POSITIVE_SIGNALS = {
    "add",
    "build",
    "improve",
    "dark",
    "demand",
    "users",
    "profit",
    "works",
    "passed",
    "positive",
    "compliant",
    "analytics",
    "market",
}

RISK_SIGNALS = {
    "delete",
    "remove",
    "breaking",
    "unsafe",
    "risk",
    "illegal",
    "loss",
    "unverified",
    "private",
    "secret",
    "credentials",
}


@dataclass(frozen=True)
class CouncilOpinion:
    agent_name: str
    pillar: str
    stance: str
    confidence: int
    reasoning: str
    risks: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "pillar": self.pillar,
            "stance": self.stance,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risks": list(self.risks),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class CouncilDecision:
    question: str
    verdict: str
    yes_votes: int
    no_votes: int
    confidence: int
    opinions: tuple[CouncilOpinion, ...] = field(default_factory=tuple)
    conflicts: tuple[str, ...] = field(default_factory=tuple)
    summary: str = ""

    @property
    def vote_line(self) -> str:
        return f"{self.yes_votes}/{self.yes_votes + self.no_votes} YES"

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "verdict": self.verdict,
            "yes_votes": self.yes_votes,
            "no_votes": self.no_votes,
            "confidence": self.confidence,
            "vote_line": self.vote_line,
            "opinions": [opinion.to_dict() for opinion in self.opinions],
            "conflicts": list(self.conflicts),
            "summary": self.summary,
        }


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _agent_evidence(agent: Agent, tokens: set[str]) -> tuple[str, ...]:
    name = agent.name.replace("_", " ")
    evidence = []
    if agent.pillar == "code":
        evidence.append("implementation and test impact reviewed")
    if agent.pillar == "see":
        evidence.append("research, user signal, or visual evidence requested")
    if agent.pillar == "design":
        evidence.append("UX, content, and interaction fit checked")
    if agent.pillar == "act":
        evidence.append("business, operational, and execution impact assessed")
    if "dark" in tokens and agent.name in {"ux_research", "design", "analytics"}:
        evidence.append("dark mode adoption signal considered")
    if "crypto" in tokens and agent.name in {"trading", "finance", "legal", "analytics"}:
        evidence.append("market, financial, and compliance risk considered")
    return tuple(evidence or (f"{name} reviewed the request from its specialty",))


def _agent_risks(agent: Agent, tokens: set[str]) -> tuple[str, ...]:
    risks = []
    if tokens & RISK_SIGNALS:
        risks.append("request contains explicit risk language")
    if agent.name == "security":
        risks.append("security assumptions must be validated before release")
    if agent.name == "legal" and {"trading", "crypto", "finance"} & tokens:
        risks.append("financial or trading guidance may require compliance review")
    if agent.name == "testing":
        risks.append("edge cases need regression coverage")
    return tuple(risks)


def collect_opinion(agent: Agent, question: str) -> CouncilOpinion:
    tokens = _tokenize(question)
    positive = len(tokens & POSITIVE_SIGNALS)
    risky = len(tokens & RISK_SIGNALS)
    risks = _agent_risks(agent, tokens)
    evidence = _agent_evidence(agent, tokens)

    if risky > positive and agent.name in {"security", "legal", "finance", "testing"}:
        stance = "reject"
        confidence = max(52, min(88, 68 + risky * 6))
    else:
        stance = "proceed"
        confidence = max(55, min(96, 72 + positive * 4 - risky * 5))

    reasoning = (
        f"{agent.name} recommends {stance} after checking {agent.pillar}/{agent.category} "
        f"concerns with {len(evidence)} evidence point(s) and {len(risks)} risk flag(s)."
    )
    return CouncilOpinion(
        agent_name=agent.name,
        pillar=agent.pillar,
        stance=stance,
        confidence=confidence,
        reasoning=reasoning,
        risks=risks,
        evidence=evidence,
    )


def run_council_vote(
    question: str,
    agents: list[Agent],
    quorum: int = 6,
) -> CouncilDecision:
    if not question.strip():
        raise ValueError("Council question cannot be empty.")
    if quorum < 1:
        raise ValueError("Council quorum must be at least 1.")
    if len(agents) < quorum:
        raise ValueError(f"Council requires at least {quorum} agents; got {len(agents)}.")

    selected = _select_council_agents(question, agents, quorum)
    opinions = tuple(collect_opinion(agent, question) for agent in selected)
    yes_votes = sum(1 for opinion in opinions if opinion.stance == "proceed")
    no_votes = len(opinions) - yes_votes
    verdict = "proceed" if yes_votes > no_votes else "reject"
    avg_confidence = int(round(mean(opinion.confidence for opinion in opinions)))
    agreement_bonus = int(round(abs(yes_votes - no_votes) / len(opinions) * 8))
    final_confidence = max(1, min(99, avg_confidence + agreement_bonus))
    conflicts = tuple(
        f"{opinion.agent_name} voted {opinion.stance}"
        for opinion in opinions
        if opinion.stance != verdict
    )
    summary = (
        f"Council vote: {yes_votes}/{len(opinions)} YES. "
        f"Verdict: {verdict}. Confidence: {final_confidence}%."
    )
    return CouncilDecision(
        question=question,
        verdict=verdict,
        yes_votes=yes_votes,
        no_votes=no_votes,
        confidence=final_confidence,
        opinions=opinions,
        conflicts=conflicts,
        summary=summary,
    )


def _select_council_agents(question: str, agents: list[Agent], quorum: int) -> list[Agent]:
    tokens = _tokenize(question)
    priority = []
    if tokens & RISK_SIGNALS:
        priority.extend(["security", "legal", "testing", "finance"])
    if {"build", "feature", "code", "bug", "test", "dark"} & tokens:
        priority.extend(["coder", "testing", "security", "ux_research", "analytics", "product_manager", "design"])
    if {"market", "profit", "crypto", "trading", "finance"} & tokens:
        priority.extend(["trading", "finance", "analytics", "legal", "marketing", "sales"])
    priority.extend(["researcher", "reviewer", "council_master"])

    by_name = {agent.name: agent for agent in agents}
    selected = []
    for name in priority:
        agent = by_name.get(name)
        if agent and agent not in selected:
            selected.append(agent)
        if len(selected) >= quorum:
            return selected

    for agent in agents:
        if agent not in selected:
            selected.append(agent)
        if len(selected) >= quorum:
            return selected
    return selected

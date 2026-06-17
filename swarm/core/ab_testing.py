from __future__ import annotations

from dataclasses import dataclass

from swarm.core.agent import Agent


@dataclass(frozen=True)
class ABCandidate:
    id: str
    name: str
    strategy: str
    strengths: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    score: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "strategy": self.strategy,
            "strengths": list(self.strengths),
            "tradeoffs": list(self.tradeoffs),
            "score": self.score,
        }


@dataclass(frozen=True)
class ABTestResult:
    prompt: str
    candidates: tuple[ABCandidate, ABCandidate]
    winner_id: str
    loser_id: str
    council_votes: dict[str, str]
    summary: str

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "council_votes": dict(self.council_votes),
            "summary": self.summary,
        }

    @property
    def winner(self) -> ABCandidate:
        return next(candidate for candidate in self.candidates if candidate.id == self.winner_id)

    @property
    def loser(self) -> ABCandidate:
        return next(candidate for candidate in self.candidates if candidate.id == self.loser_id)


def run_ab_test(prompt: str, council_agents: list[Agent]) -> ABTestResult:
    candidate_a = ABCandidate(
        id="A",
        name="Lean Single-Path Plan",
        strategy=(
            "Use the smallest specialist set, keep token usage low, build the core path first, "
            "then run focused master review."
        ),
        strengths=("lower token cost", "faster delivery", "less coordination overhead"),
        tradeoffs=("less parallel exploration", "may miss creative alternatives"),
        score=_score_candidate(prompt, "A"),
    )
    candidate_b = ABCandidate(
        id="B",
        name="Hybrid Multi-Agent Plan",
        strategy=(
            "Use cloud models for master/council reasoning, local or cheap models for sub-agent checks, "
            "MCP/browser tools for external state, and integrate after specialist work."
        ),
        strengths=("stronger coverage", "hybrid routing", "better validation breadth"),
        tradeoffs=("slightly higher token use", "more moving parts"),
        score=_score_candidate(prompt, "B"),
    )

    votes: dict[str, str] = {}
    for agent in council_agents:
        votes[agent.name] = _vote(agent, prompt, candidate_a, candidate_b)
    a_votes = sum(1 for vote in votes.values() if vote == "A")
    b_votes = sum(1 for vote in votes.values() if vote == "B")

    if b_votes > a_votes:
        winner, loser = candidate_b, candidate_a
    elif a_votes > b_votes:
        winner, loser = candidate_a, candidate_b
    else:
        # Tie-break on deterministic score, then choose lower-cost A.
        winner, loser = (
            (candidate_b, candidate_a)
            if candidate_b.score > candidate_a.score
            else (candidate_a, candidate_b)
        )

    return ABTestResult(
        prompt=prompt,
        candidates=(candidate_a, candidate_b),
        winner_id=winner.id,
        loser_id=loser.id,
        council_votes=votes,
        summary=(
            f"Council selected version {winner.id}: {winner.name}. "
            f"Vote A/B: {a_votes}/{b_votes}. Alternative shown: {loser.id}: {loser.name}."
        ),
    )


def _score_candidate(prompt: str, candidate_id: str) -> int:
    lower = prompt.lower()
    complex_tokens = {"browser", "mcp", "hybrid", "test", "media", "video", "image", "figma", "local", "cloud"}
    simple_tokens = {"small", "quick", "simple", "cheap", "single"}
    if candidate_id == "B":
        return 70 + min(20, sum(token in lower for token in complex_tokens) * 4)
    return 72 + min(18, sum(token in lower for token in simple_tokens) * 4)


def _vote(agent: Agent, prompt: str, candidate_a: ABCandidate, candidate_b: ABCandidate) -> str:
    lower = prompt.lower()
    if agent.name in {"testing", "security", "analytics", "council_master"}:
        return "B"
    if agent.name in {"finance", "product_manager"} and any(token in lower for token in ("cheap", "budget", "simple")):
        return "A"
    if agent.pillar in {"see", "code"} and candidate_b.score >= candidate_a.score:
        return "B"
    return "A" if candidate_a.score >= candidate_b.score else "B"

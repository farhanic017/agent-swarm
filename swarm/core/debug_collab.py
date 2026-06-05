"""Collaborative Debugging Protocol — agents work together to fix issues.

Provides a structured protocol where agents can request help, propose
fixes, review each other's solutions, and collaboratively apply fixes.
Every debugging session is transparent — all agents can see and contribute.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DebugIssue:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    reporter: str = ""
    description: str = ""
    suspected_area: str = ""
    attempted_fixes: list = field(default_factory=list)
    status: str = "open"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reporter": self.reporter,
            "description": self.description[:200],
            "suspected_area": self.suspected_area,
            "attempted_fixes": self.attempted_fixes[:3],
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class FixProposal:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    issue_id: str = ""
    proposer: str = ""
    description: str = ""
    code: str = ""
    status: str = "pending"
    reviews: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "proposer": self.proposer,
            "description": self.description[:200],
            "status": self.status,
            "reviews": len(self.reviews),
            "created_at": self.created_at,
        }


@dataclass
class FixReview:
    reviewer: str = ""
    decision: str = ""
    feedback: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "reviewer": self.reviewer,
            "decision": self.decision,
            "feedback": self.feedback[:200],
            "timestamp": self.timestamp,
        }


class DebugCollaboration:
    """Manages collaborative debugging sessions across agents."""

    def __init__(self):
        self._issues: dict[str, DebugIssue] = {}
        self._proposals: dict[str, FixProposal] = {}
        self._max_issues: int = 200

    # ── Issue Management ──────────────────────────────────────────────

    def report_issue(self, reporter: str, description: str,
                     suspected_area: str = "",
                     attempted_fixes: list = None) -> DebugIssue:
        issue = DebugIssue(
            reporter=reporter,
            description=description,
            suspected_area=suspected_area,
            attempted_fixes=attempted_fixes or [],
        )
        self._issues[issue.id] = issue
        if len(self._issues) > self._max_issues:
            oldest = min(self._issues.keys(),
                         key=lambda k: self._issues[k].created_at)
            del self._issues[oldest]
        return issue

    def get_issue(self, issue_id: str) -> Optional[DebugIssue]:
        return self._issues.get(issue_id)

    def get_open_issues(self) -> list[DebugIssue]:
        return [i for i in self._issues.values() if i.status == "open"]

    # ── Fix Proposals ─────────────────────────────────────────────────

    def propose_fix(self, issue_id: str, proposer: str,
                    description: str, code: str = "") -> Optional[FixProposal]:
        issue = self._issues.get(issue_id)
        if not issue or issue.status == "resolved":
            return None
        proposal = FixProposal(
            issue_id=issue_id,
            proposer=proposer,
            description=description,
            code=code,
        )
        self._proposals[proposal.id] = proposal
        issue.status = "in_review"
        return proposal

    def review_fix(self, proposal_id: str, reviewer: str,
                   decision: str, feedback: str = "") -> Optional[FixReview]:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        review = FixReview(
            reviewer=reviewer,
            decision=decision,
            feedback=feedback,
        )
        proposal.reviews.append(review)

        issue = self._issues.get(proposal.issue_id)
        if decision == "approve":
            proposal.status = "approved"
            if issue:
                issue.status = "resolved"
        elif decision == "reject":
            proposal.status = "rejected"
            if issue:
                issue.status = "open"
        else:
            proposal.status = "revise_needed"
            if issue:
                issue.status = "in_review"

        return review

    def apply_fix(self, proposal_id: str, applier: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if not proposal or proposal.status != "approved":
            return False
        proposal.status = "applied"
        issue = self._issues.get(proposal.issue_id)
        if issue:
            issue.status = "resolved"
        return True

    # ── Query ─────────────────────────────────────────────────────────

    def get_proposals(self, issue_id: str) -> list[FixProposal]:
        return [p for p in self._proposals.values()
                if p.issue_id == issue_id]

    def get_issue_summary(self, issue_id: str) -> str:
        issue = self._issues.get(issue_id)
        if not issue:
            return "Issue not found."
        lines = [
            f"=== Debug Issue: {issue.id} ===",
            f"Reporter: {issue.reporter}",
            f"Description: {issue.description[:300]}",
            f"Area: {issue.suspected_area}",
            f"Status: {issue.status}",
            f"Attempted fixes: {', '.join(issue.attempted_fixes[:3]) or 'none'}",
        ]
        proposals = self.get_proposals(issue_id)
        if proposals:
            lines.append(f"Proposals ({len(proposals)}):")
            for p in proposals:
                lines.append(f"  [{p.status}] by {p.proposer}: {p.description[:150]}")
                if p.reviews:
                    for r in p.reviews:
                        lines.append(f"    Review by {r.reviewer}: {r.decision} - {r.feedback[:100]}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "open_issues": len(self.get_open_issues()),
            "total_issues": len(self._issues),
            "issues": [i.to_dict() for i in list(self._issues.values())[-10:]],
        }

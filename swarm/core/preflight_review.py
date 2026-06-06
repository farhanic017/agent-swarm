from __future__ import annotations

import re
from dataclasses import dataclass, field


SECURITY_PATTERNS = (
    ("hardcoded_secret", re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]")),
    ("shell_injection", re.compile(r"(?i)(shell=True|os\.system\(|subprocess\.(call|run|Popen)\([^)]*\+)")),
    ("unsafe_eval", re.compile(r"\b(eval|exec)\s*\(")),
    ("sql_injection", re.compile(r"(?i)(select|insert|update|delete).*(\+|f['\"])")),
)

PERFORMANCE_PATTERNS = (
    ("unbounded_loop", re.compile(r"\bwhile\s+True\s*:")),
    ("quadratic_loop", re.compile(r"for\s+\w+\s+in\s+.+:\s*\n\s+for\s+\w+\s+in\s+")),
    ("sync_network_in_loop", re.compile(r"for\s+.+:\s*\n(?:\s+.*\n){0,4}\s+(requests\.|urllib\.)")),
)

LOGIC_PATTERNS = (
    ("bare_except", re.compile(r"except\s*:")),
    ("mutable_default", re.compile(r"def\s+\w+\([^)]*=\s*(\[\]|\{\})")),
    ("comparison_to_none", re.compile(r"(?<!is)\s(==|!=)\s+None\b")),
)


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int
    body: str
    severity: str = "warning"
    category: str = "logic"
    agent_name: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "body": self.body,
            "severity": self.severity,
            "category": self.category,
            "agent_name": self.agent_name,
        }


@dataclass(frozen=True)
class AgentReviewResult:
    agent_name: str
    passed: bool
    comments: tuple[InlineComment, ...] = ()
    fix_prompt: str = ""
    summary: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "passed": self.passed,
            "comments": [comment.to_dict() for comment in self.comments],
            "fix_prompt": self.fix_prompt,
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _scan_patterns(agent_name: str, path: str, text: str, category: str, patterns: tuple) -> list[InlineComment]:
    comments = []
    for rule, pattern in patterns:
        for match in pattern.finditer(text):
            line = _line_for_offset(text, match.start())
            comments.append(
                InlineComment(
                    path=path,
                    line=line,
                    category=category,
                    severity="error" if category == "security" else "warning",
                    agent_name=agent_name,
                    body=(
                        f"[{agent_name}] {category} reviewer flagged `{rule}`. "
                        "Fix this before integration so the master agent receives safer work."
                    ),
                )
            )
    return comments


def review_agent_output(
    agent_name: str,
    output: str,
    path: str = "agent-output.md",
    max_comments: int = 20,
) -> AgentReviewResult:
    comments = []
    comments.extend(_scan_patterns(agent_name, path, output, "security", SECURITY_PATTERNS))
    comments.extend(_scan_patterns(agent_name, path, output, "performance", PERFORMANCE_PATTERNS))
    comments.extend(_scan_patterns(agent_name, path, output, "logic", LOGIC_PATTERNS))
    comments = comments[:max_comments]

    passed = not comments
    if passed:
        summary = f"{agent_name} preflight review passed: no obvious security, performance, or logic issues."
        fix_prompt = ""
    else:
        grouped = {}
        for comment in comments:
            grouped.setdefault(comment.category, 0)
            grouped[comment.category] += 1
        summary = (
            f"{agent_name} preflight review found {len(comments)} issue(s): "
            + ", ".join(f"{count} {category}" for category, count in sorted(grouped.items()))
        )
        fix_prompt = (
            f"Fix {agent_name}'s work before integration. Address every inline comment, "
            "preserve intended behavior, add focused tests, and return only the corrected work."
        )
    return AgentReviewResult(
        agent_name=agent_name,
        passed=passed,
        comments=tuple(comments),
        fix_prompt=fix_prompt,
        summary=summary,
        metadata={"max_comments": max_comments},
    )


def format_github_review_comments(result: AgentReviewResult, commit_id: str = "") -> list[dict]:
    return [
        {
            "path": comment.path,
            "line": comment.line,
            "side": "RIGHT",
            "body": comment.body,
            **({"commit_id": commit_id} if commit_id else {}),
        }
        for comment in result.comments
    ]

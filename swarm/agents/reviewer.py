from swarm.core.agent import Agent

REVIEWER_SYSTEM_PROMPT = """You are the **Review Agent** — a quality assurance specialist that reviews work before it's final.

**Capabilities:**
- Review code for bugs, security issues, and best practices
- Review written content for clarity, accuracy, and tone
- Check for completeness against the original requirements
- Suggest improvements and fixes

**Rules:**
- Be constructive and specific in your feedback
- Check against the original task requirements
- For code: check logic, edge cases, security, performance, and style
- For content: check accuracy, readability, structure, and tone
- If issues are found, hand back to the original agent with clear instructions
- If everything looks good, confirm completion"""

REVIEWER_TOOLS = [
    "read_file", "list_directory", "run_python", "run_react_doctor",
    "send_message", "broadcast_message", "get_messages", "get_thread",
    "request_help", "propose_fix", "review_fix", "apply_fix", "get_issue_status",
    "log_lesson", "get_relevant_lessons", "get_learning_stats",
    "initiate_brainstorm", "contribute_idea", "finalize_brainstorm", "get_brainstorm_summary",
]


def create_reviewer_agent(handoff_targets: list[str] = None) -> Agent:
    return Agent(
        name="reviewer",
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        description="Reviews code and content for bugs, issues, and quality. Ensures work meets requirements.",
        tools=REVIEWER_TOOLS,
        handoff_targets=handoff_targets or [],
        temperature=0.2,
    )

from swarm.core.agent import Agent

CODER_SYSTEM_PROMPT = """You are the **Coding Agent** — an expert software engineer that writes, debugs, and optimizes code.

**Capabilities:**
- Write code in any language (Python, JavaScript, TypeScript, Go, Rust, etc.)
- Debug existing code and fix bugs
- Refactor and optimize codebases
- Write tests and documentation
- Explain code architecture and design patterns

**Rules:**
- Always write clean, well-structured, production-ready code
- Follow best practices and design patterns appropriate for the language
- Include error handling and edge cases
- When creating files, use the write_file tool
- After writing code, hand off to a reviewer if one is available
- If the task is complete, summarize what was created"""

CODER_TOOLS = [
    "write_file", "read_file", "list_directory", "save_artifact",
    "run_python", "run_react_doctor",
    "send_message", "broadcast_message", "get_messages", "get_thread",
    "request_help", "propose_fix", "review_fix", "apply_fix", "get_issue_status",
    "log_lesson", "get_relevant_lessons", "get_learning_stats",
    "initiate_brainstorm", "contribute_idea", "finalize_brainstorm", "get_brainstorm_summary",
]


def create_coder_agent(handoff_targets: list[str] = None) -> Agent:
    return Agent(
        name="coder",
        system_prompt=CODER_SYSTEM_PROMPT,
        description="Writes, debugs, and optimizes code across any language. Creates files and implements features.",
        tools=CODER_TOOLS,
        handoff_targets=handoff_targets or [],
        temperature=0.2,
    )

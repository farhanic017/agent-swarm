from swarm.core.agent import Agent

WRITER_SYSTEM_PROMPT = """You are the **Writing Agent** — an expert content creator and editor.

**Capabilities:**
- Write articles, documentation, reports, and marketing copy
- Edit and polish existing content
- Format content with proper structure (headings, lists, tables)
- Adapt tone and style for different audiences

**Rules:**
- Be clear, concise, and engaging
- Match the tone to the audience (technical, general, executive)
- Structure content for readability
- Save written content using the save_artifact tool
- After writing, hand off to reviewer if available
- If the task is done, present the final content clearly"""

WRITER_TOOLS = [
    "write_file", "read_file", "save_artifact",
    "send_message", "broadcast_message", "get_messages", "get_thread",
    "request_help", "propose_fix", "review_fix", "get_issue_status",
    "log_lesson", "get_relevant_lessons", "get_learning_stats",
    "initiate_brainstorm", "contribute_idea", "finalize_brainstorm", "get_brainstorm_summary",
]


def create_writer_agent(handoff_targets: list[str] = None) -> Agent:
    return Agent(
        name="writer",
        system_prompt=WRITER_SYSTEM_PROMPT,
        description="Creates and edits written content — articles, docs, reports, and copy. Formats and polishes text.",
        tools=WRITER_TOOLS,
        handoff_targets=handoff_targets or [],
        temperature=0.4,
    )

from swarm.core.agent import Agent

RESEARCHER_SYSTEM_PROMPT = """You are the **Research Agent** — a thorough information gatherer and analyst.

Your job is to research topics deeply and provide comprehensive, well-structured findings.

**Capabilities:**
- Search the web for current information
- Read and analyze documents
- Compile structured research reports
- Find relevant sources and citations

**Rules:**
- Be thorough but focused on exactly what was asked
- Always cite your sources when possible
- Structure findings with clear headings
- If you find conflicting information, present both sides
- When done, hand off to the next appropriate agent (writer, coder, etc.)
- If the task doesn't need further agents, summarize your findings clearly"""

RESEARCHER_TOOLS = [
    "search_web", "read_file", "list_directory",
    "send_message", "broadcast_message", "get_messages", "get_thread",
    "request_help", "propose_fix", "review_fix", "get_issue_status",
    "log_lesson", "get_relevant_lessons", "get_learning_stats",
    "initiate_brainstorm", "contribute_idea", "finalize_brainstorm", "get_brainstorm_summary",
]


def create_researcher_agent(handoff_targets: list[str] = None) -> Agent:
    return Agent(
        name="researcher",
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        description="Researches topics thoroughly using web search and document analysis. Provides structured findings.",
        tools=RESEARCHER_TOOLS,
        handoff_targets=handoff_targets or [],
        temperature=0.3,
    )

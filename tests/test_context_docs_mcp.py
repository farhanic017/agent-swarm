import json

from swarm.core.context import build_compaction_summary, format_compaction_summary
from swarm.core.docs_integration import plan_docs_for_task
from swarm.core.mcp_marketplace import list_mcp_marketplace, plan_mcp_connectors
from swarm.core.state import AgentTurn, SharedState
from swarm.tools.registry import ToolRegistry


def test_compaction_summary_preserves_progress_and_pending_work():
    state = SharedState(user_input="build skateboard store", summary="homepage complete")
    state.add_turn(AgentTurn("frontend_ui", "build UI", "Implemented src/app/page.tsx and tests passed", "test"))
    state.add_turn(AgentTurn("security", "review", "Risk: checkout auth still needs validation", "test"))
    summary = build_compaction_summary(
        state,
        project_tree="src/app\nsrc/components\nREADME.md",
        pending=["finish checkout", "run deployment smoke test"],
    )
    text = format_compaction_summary(summary)

    assert summary["command"] == "/compact"
    assert "finish checkout" in summary["pending"]
    assert "src/app/page.tsx" in summary["project"]["important_files"]
    assert "Do not reread the entire codebase" in summary["next_agent_instruction"]
    assert "Compact Context Summary" in text


def test_docs_planner_selects_framework_docs():
    plan = plan_docs_for_task("Build Next.js App Router checkout with React Tailwind and Supabase auth")
    names = {source["name"] for source in plan["sources"]}

    assert "Next.js docs" in names
    assert "React docs" in names
    assert "Tailwind CSS docs" in names
    assert "Supabase docs" in names


def test_mcp_marketplace_lists_and_plans_connectors():
    design = list_mcp_marketplace(category="Design")
    names = {entry["name"] for entry in design}
    assert {"Figma", "Canva", "Adobe for creativity"}.issubset(names)

    plan = plan_mcp_connectors("sync Stripe payments, Shopify orders, Slack alerts, and Supabase database")
    selected = {entry["name"] for entry in plan["selected"]}
    assert {"Stripe", "Shopify", "Slack", "Supabase"}.issubset(selected)
    assert "do not enable broad access" in plan["install_policy"].lower()


def test_context_docs_mcp_tools_are_registered():
    registry = ToolRegistry.create_default()
    tools = set(registry.list_tools())

    assert "compact_context" in tools
    assert "plan_docs_integration" in tools
    assert "list_mcp_marketplace" in tools
    assert "plan_mcp_connectors" in tools

    docs_tool = registry.get("plan_docs_integration")
    result = json.loads(docs_tool.func("Use React and Stripe"))
    assert result["sources"]

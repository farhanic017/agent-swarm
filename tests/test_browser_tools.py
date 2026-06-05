from swarm.tools.registry import ToolRegistry


def test_browser_tools_are_registered():
    registry = ToolRegistry.create_default()
    tools = set(registry.list_tools())
    assert {
        "browser_open",
        "browser_snapshot",
        "browser_click",
        "browser_get_title",
        "browser_stop",
    }.issubset(tools)


def test_browser_tools_export_openai_schema():
    registry = ToolRegistry.create_default()
    schema = registry.to_openai_format(["browser_open", "browser_snapshot"])
    names = [item["function"]["name"] for item in schema]
    assert names == ["browser_open", "browser_snapshot"]
    assert schema[0]["function"]["parameters"]["required"] == ["url"]

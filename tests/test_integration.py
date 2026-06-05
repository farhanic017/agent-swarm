"""Integration tests for agent swarm"""
import sys
sys.path.insert(0, r"C:\Users\Farhan\Desktop\agent swarm")

import pytest
from swarm.config import SwarmConfig
from swarm.config import normalize_provider_name
from swarm.providers.factory import ProviderFactory
from swarm.tools.registry import ToolRegistry


def test_provider_detection():
    cfg = SwarmConfig.from_opencode_config()
    providers = list(cfg.providers.keys())
    assert len(providers) > 0, "Should detect at least one provider"
    print(f"Providers: {providers}")


def test_best_model_found():
    cfg = SwarmConfig.from_opencode_config()
    best = cfg.get_best_model()
    assert best is not None, "Should find a best model"
    assert ":" in best, "Model should have provider:model format"
    print(f"Best: {best}")


def test_cheapest_model_found():
    cfg = SwarmConfig.from_opencode_config()
    cheap = cfg.get_cheapest_model()
    assert cheap is not None, "Should find a cheap model"
    assert ":" in cheap
    print(f"Cheapest: {cheap}")


def test_provider_factory_resolves():
    cfg = SwarmConfig.from_opencode_config()
    best = cfg.get_best_model()
    provider = ProviderFactory.get_provider(cfg, best)
    assert provider is not None, f"Should resolve provider for {best}"


def test_openclaw_env_provider_detection(monkeypatch):
    monkeypatch.setenv("OPENCLAW_BASE_URL", "http://localhost:7331/v1")
    monkeypatch.setenv("OPENCLAW_MODEL", "openclaw/director")
    monkeypatch.delenv("OPENCLAW_API_KEY", raising=False)

    cfg = SwarmConfig.auto_detect()

    assert normalize_provider_name("open-claw") == "openclaw"
    assert "openclaw" in cfg.providers
    assert cfg.providers["openclaw"].endpoint == "http://localhost:7331/v1"
    assert "openclaw/director" in cfg.providers["openclaw"].models
    assert ProviderFactory.get_provider(cfg, "openclaw:openclaw/director") is not None


def test_azure_foundry_aliases_resolve_to_azure():
    assert normalize_provider_name("azure-foundry") == "azure"
    assert normalize_provider_name("azure-ai-foundry") == "azure"
    assert normalize_provider_name("foundry") == "azure"


def test_opencode_azure_foundry_provider_alias_is_parsed(tmp_path):
    cfg_path = tmp_path / "opencode.jsonc"
    cfg_path.write_text(
        """
        {
          "provider": {
            "azure-foundry": {
              "options": {
                "apiKey": "x",
                "endpoint": "https://example.openai.azure.com"
              },
              "models": {
                "gpt-4.1": { "deployment": "gpt-4-1-prod" }
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )

    cfg = SwarmConfig.from_opencode_config(str(cfg_path))

    assert cfg.providers["azure-foundry"].endpoint == "https://example.openai.azure.com"
    assert ProviderFactory.get_provider(cfg, "azure-foundry:gpt-4.1") is not None


def test_opencode_base_url_is_parsed(tmp_path):
    cfg_path = tmp_path / "opencode.jsonc"
    cfg_path.write_text(
        """
        {
          "provider": {
            "cloudflare": {
              "options": {
                "apiKey": "x",
                "baseUrl": "https://api.cloudflare.com/client/v4/accounts/test/ai/v1/"
              },
              "models": {
                "@cf/qwen/qwen2.5-coder-32b-instruct": {}
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )

    cfg = SwarmConfig.from_opencode_config(str(cfg_path))

    assert cfg.providers["cloudflare"].endpoint == "https://api.cloudflare.com/client/v4/accounts/test/ai/v1/"
    assert ProviderFactory.get_provider(cfg, "cloudflare:@cf/qwen/qwen2.5-coder-32b-instruct") is not None


def test_opencode_provider_level_base_url_is_parsed(tmp_path):
    cfg_path = tmp_path / "opencode.jsonc"
    cfg_path.write_text(
        """
        {
          "provider": {
            "zai": {
              "options": { "apiKey": "x" },
              "baseURL": "https://open.bigmodel.cn/api/paas/v4",
              "models": { "glm-4.7": {} }
            }
          }
        }
        """,
        encoding="utf-8",
    )

    cfg = SwarmConfig.from_opencode_config(str(cfg_path))

    assert cfg.providers["zai"].endpoint == "https://open.bigmodel.cn/api/paas/v4"


def test_tool_registry_defaults():
    reg = ToolRegistry.create_default()
    tools = reg.list_tools()
    assert len(tools) >= 5
    assert "get_current_time" in tools
    assert "write_file" in tools
    assert "read_file" in tools


def test_agent_handoff_chain():
    from swarm.core.agent import Agent
    from swarm.core.handoff import build_handoff_tools, parse_handoff

    agents = {
        "triage": Agent(name="triage", system_prompt="Route", handoff_targets=["researcher", "coder"]),
        "researcher": Agent(name="researcher", system_prompt="Research", handoff_targets=["writer"]),
        "writer": Agent(name="writer", system_prompt="Write"),
        "coder": Agent(name="coder", system_prompt="Code"),
    }

    triage_tools = build_handoff_tools(agents, "triage")
    names = [t["function"]["name"] for t in triage_tools]
    assert "transfer_to_researcher" in names
    assert "transfer_to_coder" in names
    assert "transfer_to_writer" not in names

    researcher_tools = build_handoff_tools(agents, "researcher")
    rnames = [t["function"]["name"] for t in researcher_tools]
    assert "transfer_to_writer" in rnames


def test_full_orchestrator_creation():
    from swarm.core.orchestrator import Orchestrator
    from swarm.agents.triage import create_triage_agent
    from swarm.agents.researcher import create_researcher_agent
    from swarm.agents.coder import create_coder_agent

    cfg = SwarmConfig.from_opencode_config()
    orch = Orchestrator(config=cfg)

    triage = create_triage_agent(handoff_targets=["researcher", "coder"])
    researcher = create_researcher_agent(handoff_targets=["coder"])
    coder = create_coder_agent()

    orch.register_agents(triage, researcher, coder)
    assert len(orch.agents) == 3
    assert "triage" in orch.agents
    assert "researcher" in orch.agents
    assert "coder" in orch.agents


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

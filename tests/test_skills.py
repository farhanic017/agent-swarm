from pathlib import Path
import tempfile

from swarm.skills import SkillLoader, parse_skill_md, discover_project_skills
from swarm.skills.models import Skill


def _make_skill(name="react-testing", desc="Test React with Jest",
                triggers=None, content="Test content.", filename="SKILL.md"):
    tmp = Path(tempfile.mkdtemp())
    triggers_str = "\n".join(f"  - {t}" for t in (triggers or ["react", "jest"]))
    (tmp / filename).write_text(f"""\
---
name: {name}
description: {desc}
triggers:
{triggers_str}
---
{content}
""")
    return tmp


def test_parse_skill_md():
    tmp = _make_skill()
    skill = parse_skill_md(str(tmp / "SKILL.md"))
    assert skill is not None
    assert skill.name == "react-testing"
    assert "Test React with Jest" in skill.description
    assert len(skill.triggers) == 2


def test_discover_project_skills_root():
    tmp = _make_skill(filename="SKILL.md")
    skills = discover_project_skills(str(tmp))
    assert len(skills) >= 1
    assert any(s.name == "react-testing" for s in skills)


def test_discover_project_skills_nested():
    tmp = _make_skill(filename="SKILL.md")
    nested = tmp / ".claude" / "skills"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "nested.md").write_text("""\
---
name: nested-skill
description: A nested skill
triggers:
  - nested
---
Body
""")
    skills = discover_project_skills(str(tmp))
    names = [s.name for s in skills]
    assert "nested-skill" in names
    assert "react-testing" in names


def test_parse_invalid_file():
    tmp = Path(tempfile.mkdtemp())
    f = tmp / "no-frontmatter.md"
    f.write_text("Just some text without frontmatter")
    skill = parse_skill_md(str(f))
    assert skill is None


def test_parse_nonexistent_file():
    skill = parse_skill_md("C:/nonexistent/file.md")
    assert skill is None


def test_skill_loader_match():
    skill = Skill(
        name="react-testing",
        description="Testing React components with Jest",
        content="Use @testing-library/react",
        source="/tmp/test.md",
        triggers=["react", "jest", "testing"],
    )

    loader = SkillLoader()
    loader._all_skills = [skill]
    loader._discovered = True

    matched = loader.match_skills("write tests for a React component with Jest", max_skills=2)
    assert len(matched) >= 1
    assert matched[0].name == "react-testing"


def test_skill_loader_no_match_stop_words():
    skill = Skill(
        name="react-testing",
        description="Testing React components",
        content="Content",
        source="/tmp/test.md",
        triggers=["react"],
    )

    loader = SkillLoader()
    loader._all_skills = [skill]
    loader._discovered = True

    matched = loader.match_skills("the and of for with are", max_skills=2)
    assert len(matched) == 0


def test_format_skills_block():
    skill = Skill(
        name="python-tips",
        description="Tips for Python",
        content="Always use type hints.",
        source="/tmp/test.md",
        triggers=["python", "coding"],
    )

    loader = SkillLoader()
    block = loader.format_skills_block([skill])
    assert "<injected_skills>" in block
    assert "python-tips" in block
    assert "Always use type hints." in block


def test_get_injected_prompt():
    skill = Skill(
        name="react-testing",
        description="React testing",
        content="Use screen.getByRole",
        source="/tmp/test.md",
        triggers=["react", "testing"],
    )

    loader = SkillLoader()
    loader._all_skills = [skill]
    loader._discovered = True

    class FakeAgent:
        system_prompt = "You are a React expert."

    agent = FakeAgent()
    prompt = loader.get_injected_prompt(agent, "how do I test a React form?")
    assert "<injected_skills>" in prompt
    assert "You are a React expert." in prompt
    assert prompt.startswith("<injected_skills>")


def test_get_injected_prompt_no_match():
    skill = Skill(
        name="react-testing",
        description="React testing",
        content="Content",
        source="/tmp/test.md",
        triggers=["react"],
    )

    loader = SkillLoader()
    loader._all_skills = [skill]
    loader._discovered = True

    class FakeAgent:
        system_prompt = "You are a helper."

    agent = FakeAgent()
    prompt = loader.get_injected_prompt(agent, "what time is it")
    assert prompt == "You are a helper."


def test_get_stats():
    skill = Skill(
        name="my-skill",
        description="Desc",
        content="Body",
        source="/tmp/test.md",
    )

    loader = SkillLoader()
    loader._all_skills = [skill]
    loader._discovered = True

    stats = loader.get_stats()
    assert stats["total_skills"] == 1
    assert stats["local"] == 1
    assert stats["web"] == 0


def test_discover_and_match_real_skills():
    """Integration test: real discovery + matching via root SKILL.md."""
    tmp = _make_skill(name="botany-guide", desc="Plant care guide",
                      triggers=["plant", "water", "soil", "sunlight"],
                      content="Water plants weekly.")
    loader = SkillLoader()
    loader.discover(str(tmp))

    matched = loader.match_skills("how much water does my plant need", max_skills=3)
    assert any(s.name == "botany-guide" for s in matched), (
        f"Expected botany-guide in matches, got: {[s.name for s in matched]}"
    )


def test_match_min_score():
    skill = Skill(
        name="kubernetes",
        description="K8s deployment and management",
        content="Use kubectl",
        source="/tmp/test.md",
        triggers=["kubernetes", "k8s", "docker"],
    )

    loader = SkillLoader()
    loader._all_skills = [skill]
    loader._discovered = True

    matched = loader.match_skills("deploy to kubernetes with kubectl", max_skills=1, min_score=5.0)
    assert len(matched) == 0, "min_score too high, should exclude weak match"

    matched = loader.match_skills("kubernetes k8s docker deploy", max_skills=1, min_score=0.1)
    assert len(matched) == 1, "low min_score should include"


# ---- Future-proof platform registration tests ----


def _register_cleanup():
    """Revert module-level state modified during tests."""
    from swarm.skills import sources as _s
    _s._KNOWN_PLATFORMS.pop("_test_platform_", None)
    _s._custom_source_fns.clear()


def test_register_platform_dynamic():
    _register_cleanup()
    tmp = Path(tempfile.mkdtemp())
    skill_dir = tmp / ".mysdk" / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "test.md").write_text("""\
---
name: mysdk-skill
description: My SDK skill
triggers:
  - sdk
---
Body
""")

    from swarm.skills.sources import register_platform, discover_all_skills
    register_platform("mysdk", project_dir=str(skill_dir))

    skills = discover_all_skills(str(tmp))
    names = [s.name for s in skills]
    assert "mysdk-skill" in names, f"Expected mysdk-skill, got {names}"

    from swarm.skills.sources import list_registered_platforms
    all_platforms = list_registered_platforms()
    assert "mysdk" in all_platforms
    assert all_platforms["mysdk"] == (None, str(skill_dir))


def test_convention_dynamic_platform():
    """Register a new platform dynamically and discover its skills."""
    _register_cleanup()
    tmp = Path(tempfile.mkdtemp())
    skill_dir = tmp / ".futurecode" / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "future.md").write_text("""\
---
name: future-skill
description: Future AI coding assistant
triggers:
  - future
---
Convention works
""")

    from swarm.skills.sources import register_platform, discover_from_registered_platforms
    register_platform("futurecode", user_dir=str(skill_dir))

    skills = discover_from_registered_platforms()
    names = [s.name for s in skills]
    assert "future-skill" in names, (
        f"Dynamic platform registration failed. Got: {names}"
    )


def test_convention_path_expansion():
    """Verify convention path generation is correct."""
    from swarm.skills.sources import _convention_user_dir, _convention_project_dir
    assert _convention_user_dir("vscode") == "~/.vscode/skills"
    assert _convention_project_dir("vscode") == ".vscode/skills"
    assert _convention_user_dir("antigravity") == "~/.antigravity/skills"
    assert _convention_project_dir("antigravity") == ".antigravity/skills"
    assert _convention_user_dir("futureai") == "~/.futureai/skills"


def test_custom_source():
    _register_cleanup()
    from swarm.skills.sources import add_custom_source, discover_all_skills, discover_from_custom_sources

    def my_source():
        return [Skill(name="custom-one", description="Custom", content="Body", source="custom")]

    add_custom_source(my_source)

    result = discover_from_custom_sources()
    assert any(s.name == "custom-one" for s in result)

    result2 = discover_all_skills()
    assert any(s.name == "custom-one" for s in result2)


def test_vscode_discovery():
    _register_cleanup()
    tmp = Path(tempfile.mkdtemp())

    # VS Code project-level: .vscode/
    vscode_dir = tmp / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    (vscode_dir / "vscode-skill.md").write_text("""\
---
name: vscode-extension
description: VS Code extension development
triggers:
  - vscode
  - extension
---
Use extension.ts
""")

    # Convention: .vscode/skills/ also
    conv_dir = tmp / ".vscode" / "skills"
    conv_dir.mkdir(parents=True, exist_ok=True)
    (conv_dir / "vscode-conv.md").write_text("""\
---
name: vscode-convention
description: Discovered by convention
triggers:
  - convention
---
Works
""")

    from swarm.skills.sources import discover_project_skills
    skills = discover_project_skills(str(tmp))
    names = [s.name for s in skills]
    assert "vscode-extension" in names, f".vscode/ not scanned. Got: {names}"
    assert "vscode-convention" in names, f".vscode/skills/ convention not scanned"


def test_antigravity_discovery():
    _register_cleanup()
    tmp = Path(tempfile.mkdtemp())
    antigravity_dir = tmp / ".antigravity" / "skills"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    (antigravity_dir / "ag-skill.md").write_text("""\
---
name: antigravity-core
description: Antigravity core skill
triggers:
  - antigravity
---
Core content
""")

    from swarm.skills.sources import register_platform, discover_project_skills
    register_platform("antigravity", project_dir=str(antigravity_dir))

    skills = discover_project_skills(str(tmp))
    names = [s.name for s in skills]
    assert "antigravity-core" in names, (
        f"Antigravity discovery failed. Got: {names}"
    )


def test_list_registered_platforms():
    from swarm.skills.sources import list_registered_platforms
    platforms = list_registered_platforms()
    assert "vscode" in platforms
    assert "antigravity" in platforms
    assert "claude" in platforms
    assert "opencode" in platforms
    assert "cursor" in platforms
    assert "continue" in platforms
    assert "copilot" in platforms
    assert "aider" in platforms
    assert "cline" in platforms
    assert "openclaw" in platforms
    print(f"Registered platforms ({len(platforms)}): {list(platforms.keys())}")


def test_backward_compat_discover_local_skills():
    from swarm.skills.sources import discover_local_skills, discover_from_registered_platforms
    assert discover_local_skills is discover_from_registered_platforms

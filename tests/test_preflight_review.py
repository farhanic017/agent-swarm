from swarm.core.preflight_review import format_github_review_comments, review_agent_output
from swarm.core.state import SharedState
from swarm.core.master_review import build_integration_report, run_master_review


def test_preflight_review_flags_security_performance_and_logic():
    output = """
api_key = "super-secret-value"
while True:
    pass
try:
    work()
except:
    pass
"""
    result = review_agent_output("coder", output, path="src/app.py")

    assert not result.passed
    categories = {comment.category for comment in result.comments}
    assert {"security", "performance", "logic"}.issubset(categories)
    assert "Fix coder" in result.fix_prompt


def test_preflight_review_flags_xss_patterns():
    result = review_agent_output(
        "frontend_ui",
        "element.innerHTML = userInput\n<div>{{ userInput }}</div>",
        path="src/App.jsx",
    )

    assert not result.passed
    rules = " ".join(comment.body for comment in result.comments)
    assert "xss_raw_html_assignment" in rules
    assert "xss_unescaped_template" in rules


def test_preflight_review_formats_pr_inline_comments():
    result = review_agent_output("coder", "eval(user_input)", path="src/app.py")
    comments = format_github_review_comments(result, commit_id="abc123")

    assert comments
    assert comments[0]["path"] == "src/app.py"
    assert comments[0]["side"] == "RIGHT"
    assert comments[0]["commit_id"] == "abc123"


def test_master_review_fails_unresolved_preflight_comments():
    state = SharedState(user_input="build")
    state.set_artifact("council_decision", {"verdict": "proceed"})
    state.metadata["preflight_reviews"] = [review_agent_output("coder", "eval(x)").to_dict()]
    state.metadata["pr_inline_comments"] = state.metadata["preflight_reviews"][0]["comments"]
    integration = build_integration_report(state)
    state.set_artifact("integration_report", integration.to_dict())

    review = run_master_review(state)

    assert review.status == "needs_attention"
    assert "preflight inline comment" in " ".join(review.risks)

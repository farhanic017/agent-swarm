import pytest
from swarm.core.debug_collab import DebugCollaboration


@pytest.fixture
def debug():
    return DebugCollaboration()


def test_report_issue(debug):
    issue = debug.report_issue("coder", "API returns 500", "backend", ["restarted server"])
    assert issue.reporter == "coder"
    assert issue.description == "API returns 500"
    assert issue.suspected_area == "backend"
    assert issue.attempted_fixes == ["restarted server"]
    assert issue.status == "open"


def test_get_issue(debug):
    issue = debug.report_issue("coder", "Bug")
    assert debug.get_issue(issue.id) is not None
    assert debug.get_issue("nonexistent") is None


def test_get_open_issues(debug):
    debug.report_issue("coder", "Bug 1")
    debug.report_issue("writer", "Bug 2")
    assert len(debug.get_open_issues()) == 2


def test_propose_fix(debug):
    issue = debug.report_issue("coder", "Login broken")
    proposal = debug.propose_fix(issue.id, "researcher", "Check the auth module", "def fix(): pass")
    assert proposal is not None
    assert proposal.proposer == "researcher"
    assert "auth module" in proposal.description
    assert proposal.code == "def fix(): pass"
    assert proposal.status == "pending"

    issue2 = debug.get_issue(issue.id)
    assert issue2.status == "in_review"


def test_propose_fix_resolved_issue(debug):
    issue = debug.report_issue("coder", "Bug")
    p1 = debug.propose_fix(issue.id, "coder", "Fix 1")
    debug.review_fix(p1.id, "reviewer", "approve")

    proposal2 = debug.propose_fix(issue.id, "coder", "Fix 2")
    assert proposal2 is None


def test_review_fix_approve(debug):
    issue = debug.report_issue("coder", "Bug")
    proposal = debug.propose_fix(issue.id, "coder", "The fix")
    review = debug.review_fix(proposal.id, "reviewer", "approve", "Looks good")
    assert review is not None
    assert review.decision == "approve"
    assert review.feedback == "Looks good"

    p2 = debug.get_proposals(issue.id)[0]
    assert p2.status == "approved"
    assert debug.get_issue(issue.id).status == "resolved"


def test_review_fix_reject(debug):
    issue = debug.report_issue("coder", "Bug")
    proposal = debug.propose_fix(issue.id, "coder", "The fix")
    debug.review_fix(proposal.id, "reviewer", "reject", "Wrong approach")

    p2 = debug.get_proposals(issue.id)[0]
    assert p2.status == "rejected"
    assert debug.get_issue(issue.id).status == "open"


def test_review_fix_revise(debug):
    issue = debug.report_issue("coder", "Bug")
    proposal = debug.propose_fix(issue.id, "coder", "The fix")
    debug.review_fix(proposal.id, "reviewer", "revise", "Needs more error handling")

    p2 = debug.get_proposals(issue.id)[0]
    assert p2.status == "revise_needed"
    assert debug.get_issue(issue.id).status == "in_review"


def test_apply_fix(debug):
    issue = debug.report_issue("coder", "Bug")
    proposal = debug.propose_fix(issue.id, "coder", "Fix")
    debug.review_fix(proposal.id, "reviewer", "approve")
    ok = debug.apply_fix(proposal.id, "coder")
    assert ok

    p2 = debug.get_proposals(issue.id)[0]
    assert p2.status == "applied"
    assert debug.get_issue(issue.id).status == "resolved"


def test_apply_fix_not_approved(debug):
    issue = debug.report_issue("coder", "Bug")
    proposal = debug.propose_fix(issue.id, "coder", "Fix")
    ok = debug.apply_fix(proposal.id, "coder")
    assert not ok


def test_get_issue_summary(debug):
    issue = debug.report_issue("coder", "Database timeout", "db", ["increased pool"])
    proposal = debug.propose_fix(issue.id, "researcher", "Optimize queries")
    debug.review_fix(proposal.id, "reviewer", "approve")

    summary = debug.get_issue_summary(issue.id)
    assert "Database timeout" in summary
    assert "db" in summary
    assert "Optimize queries" in summary


def test_to_dict(debug):
    debug.report_issue("coder", "Bug 1")
    debug.report_issue("writer", "Bug 2")
    d = debug.to_dict()
    assert d["open_issues"] == 2
    assert d["total_issues"] == 2

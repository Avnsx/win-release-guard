from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

FORBIDDEN_ACTION_REFS = (
    "actions/checkout@" + "v4",
    "actions/setup-python@" + "v5",
    "actions/configure-pages@" + "v5",
    "actions/upload-pages-artifact@" + "v4",
    "actions/deploy-pages@" + "v4",
)
INSECURE_NODE_OPT_OUT = "ACTIONS_ALLOW_USE_" + "UNSECURE_NODE_VERSION"


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def test_workflows_use_node24_ready_action_versions() -> None:
    findings: list[str] = []
    for workflow in _workflow_files():
        text = workflow.read_text(encoding="utf-8")
        for action_ref in FORBIDDEN_ACTION_REFS:
            if action_ref in text:
                findings.append(f"{workflow.relative_to(ROOT)} contains {action_ref}")
        if INSECURE_NODE_OPT_OUT in text:
            findings.append(f"{workflow.relative_to(ROOT)} contains insecure Node opt-out")

    assert findings == []


def test_javascript_action_workflows_opt_into_node24() -> None:
    findings: list[str] = []
    for workflow in _workflow_files():
        text = workflow.read_text(encoding="utf-8")
        if "uses:" in text and "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true" not in text:
            findings.append(f"{workflow.relative_to(ROOT)} uses actions without Node 24 opt-in")

    assert findings == []


def test_publish_workflow_still_uses_same_repo_pages_artifact_deployment() -> None:
    text = (WORKFLOWS / "publish-policy.yml").read_text(encoding="utf-8")

    assert "contents: read" in text
    assert "pages: write" in text
    assert "id-token: write" in text
    assert "actions/configure-pages@v6" in text
    assert "actions/upload-pages-artifact@v5" in text
    assert "actions/deploy-pages@v5" in text
    assert "contents: write" not in text
    assert ("github" + "_pat_") not in text.lower()
    assert ("gh" + "p_") not in text.lower()
    assert "gh-pages" not in text
    assert "git push" not in text

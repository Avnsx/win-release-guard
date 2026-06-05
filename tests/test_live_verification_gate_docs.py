from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_GATE_COMMANDS = (
    "python -m compileall -q win11_release_guard tools",
    "pytest -q",
    "python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html",
    "python tools/scan_for_secret_material.py site win11_release_guard tests tools docs wiki README.md CHANGELOG.md AGENTS.md pyproject.toml .github",
    "python -m win11_release_guard --check-policy-source",
    "python -m win11_release_guard --check-public-pages",
)


def test_readme_documents_deployment_affecting_live_gate() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Deployment-affecting changes require the live Pages gate before handover." in text
    assert "workflow changes" in text
    assert "policy generator changes" in text
    assert "signing changes" in text
    assert "Pages landing page changes" in text
    assert "manifest/API alias changes" in text
    assert "source URL or published URL changes" in text
    assert "CLI changes to `--check-policy-source`" in text
    assert "`--check-public-pages`" in text
    assert "do not claim live success" in text
    assert "exact failing URL, status, and error" in text

    for command in REQUIRED_GATE_COMMANDS:
        assert command in text

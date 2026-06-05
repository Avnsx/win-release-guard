from __future__ import annotations

from pathlib import Path

from tools.check_github_action_versions import PYPA_PUBLISH_ACTION_SHA


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pypi-publish.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pypi_publish_workflow_exists_with_manual_and_release_triggers() -> None:
    text = _workflow_text()

    assert WORKFLOW.exists()
    assert "name: Publish Python package" in text
    assert "workflow_dispatch:" in text
    assert "release:" in text
    assert "types: [published]" in text
    assert "\npush:" not in text
    assert "\npull_request:" not in text
    assert "tag:" in text


def test_pypi_publish_workflow_uses_trusted_publishing_oidc_without_credentials() -> None:
    text = _workflow_text()
    lowered = text.lower()

    assert "environment:\n      name: pypi" in text
    assert "url: https://pypi.org/project/${{ needs.build.outputs.package-name }}/" in text
    assert "permissions:\n      id-token: write" in text
    assert "contents: write" not in text
    assert f"pypa/gh-action-pypi-publish@{PYPA_PUBLISH_ACTION_SHA}" in text

    forbidden = (
        "PYPI_TOKEN",
        "TWINE_PASSWORD",
        "TWINE_USERNAME",
        "__token__",
        "password:",
        "username:",
        "repository-url:",
        "https://test.pypi.org/legacy/",
    )
    for pattern in forbidden:
        assert pattern.lower() not in lowered


def test_pypi_publish_workflow_builds_and_uploads_dist_artifact() -> None:
    text = _workflow_text()

    assert "actions/checkout@v6" in text
    assert "actions/setup-python@v6" in text
    assert 'python-version: "3.12"' in text
    assert 'python -m pip install -e ".[test]"' in text
    assert "python -m pip install --upgrade build twine" in text
    assert "python -m build" in text
    assert "python -m twine check dist/*" in text
    assert "actions/upload-artifact@v7" in text
    assert "actions/download-artifact@v8" in text
    assert "name: python-package-distributions" in text
    assert "path: dist/" in text
    assert "if-no-files-found: error" in text


def test_workflow_dispatch_without_tag_is_build_only_and_cannot_publish_directly() -> None:
    text = _workflow_text()

    assert "Leave blank for build/twine/self-test only." in text
    assert 'publish_enabled="false"' in text
    assert "Manual dispatch without tag: build/twine/self-test only; publish job will be skipped." in text
    assert "Build-only PyPI workflow run for package version" in text
    assert "if: needs.build.outputs.publish-enabled == 'true'" in text
    assert 'event_tag="v${requested_version}"' not in text
    assert "${{ inputs.version }}" not in text
    assert "Manual PyPI publish must run from main." not in text


def test_workflow_dispatch_with_tag_verifies_existing_tag_before_publish() -> None:
    text = _workflow_text()

    assert 'elif [ -n "${{ inputs.tag }}" ]; then' in text
    assert 'event_tag="${{ inputs.tag }}"' in text
    assert "git rev-parse -q --verify \"refs/tags/${event_tag}^{commit}\"" in text
    assert "PyPI publish tag ${event_tag} does not exist in this repository." in text
    assert 'git checkout --detach "$event_tag"' in text
    assert 'echo "publish_enabled=${publish_enabled}" >> "$GITHUB_OUTPUT"' in text


def test_release_published_event_uses_release_tag_for_publish() -> None:
    text = _workflow_text()

    assert 'if [ "${{ github.event_name }}" = "release" ]; then' in text
    assert 'event_tag="${{ github.event.release.tag_name }}"' in text
    assert 'publish_enabled="true"' in text
    assert "release:\n    types: [published]" in text


def test_pypi_publish_workflow_runs_project_gates_before_publish() -> None:
    text = _workflow_text()

    assert "python -m compileall -q win11_release_guard tools tests" in text
    assert "python tools/check_project_identity.py" in text
    assert "python tools/check_version_consistency.py" in text
    assert "python tools/check_github_action_versions.py" in text
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in text
    assert "pytest -q --durations=20" in text
    assert "python -m win11_release_guard --self-test" in text
    assert "python tools/scan_for_secret_material.py" in text
    for target in (
        "README.md",
        "CHANGELOG.md",
        "AGENTS.md",
        "docs",
        "wiki",
        "win11_release_guard",
        "tests",
        "tools",
        "pyproject.toml",
        ".github",
    ):
        assert target in text


def test_pypi_publish_workflow_enforces_tag_version_parity_without_tag_creation() -> None:
    text = _workflow_text()

    assert "tomllib.loads" in text
    assert 'data["project"]["name"]' in text
    assert 'data["project"]["version"]' in text
    assert 'expected_tag="v${package_version}"' in text
    assert "github.event.release.tag_name" in text
    assert "Tag version ${requested_version} does not match pyproject version" in text
    assert "does not match expected" in text
    assert "Unexpected package name" in text
    assert "git tag" not in text
    assert "git push" not in text

from __future__ import annotations

from pathlib import Path

from tools import check_project_identity


OLD_PROJECT_NAME = "win" + "-release-guard"
OLD_REPO_NAME = "Avnsx/" + OLD_PROJECT_NAME
OLD_REPO_URL = "https://github.com/" + OLD_REPO_NAME
OLD_PAGES_URL = "https://avnsx.github.io/" + OLD_PROJECT_NAME
OLD_ARCHIVE_NAME = OLD_PROJECT_NAME + "-source.zip"
OLD_PROTOTYPE_NAME = "_".join(("windows", "releases", "info")) + ".py"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _messages(findings: list[check_project_identity.Finding]) -> str:
    return "\n".join(finding.format() for finding in findings)


def test_project_identity_scanner_passes_current_repo() -> None:
    assert check_project_identity.check_project_identity() == []


def test_project_identity_scanner_fails_old_repo_url_in_readme(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", f"{OLD_REPO_URL}\n")

    findings = check_project_identity.check_project_identity(tmp_path, (Path("README.md"),))

    assert "old GitHub repository URL" in _messages(findings)


def test_project_identity_scanner_fails_old_pages_url_in_workflow(tmp_path: Path) -> None:
    workflow = _write(tmp_path / ".github/workflows/publish-policy.yml", f"url: {OLD_PAGES_URL}/\n")

    findings = check_project_identity.check_project_identity(tmp_path, (workflow.relative_to(tmp_path),))

    assert "old GitHub Pages URL" in _messages(findings)


def test_project_identity_scanner_fails_old_archive_name_in_tools(tmp_path: Path) -> None:
    tool = _write(tmp_path / "tools/export.py", f"archive = '{OLD_ARCHIVE_NAME}'\n")

    findings = check_project_identity.check_project_identity(tmp_path, (tool.relative_to(tmp_path),))

    assert "old clean archive name" in _messages(findings)


def test_project_identity_scanner_fails_removed_prototype_file_name(tmp_path: Path) -> None:
    prototype = _write(tmp_path / OLD_PROTOTYPE_NAME, "obsolete\n")

    findings = check_project_identity.check_project_identity(tmp_path, (prototype.relative_to(tmp_path),))

    assert "removed prototype entry point" in _messages(findings)


def test_project_identity_scanner_fails_old_project_name_in_active_source(tmp_path: Path) -> None:
    source = _write(tmp_path / "tools/example.py", f"name = '{OLD_PROJECT_NAME}'\n")

    findings = check_project_identity.check_project_identity(tmp_path, (source.relative_to(tmp_path),))

    assert "old project name" in _messages(findings)


def test_project_identity_scanner_rejects_old_identity_in_bundled_policy(tmp_path: Path) -> None:
    policy = _write(
        tmp_path / check_project_identity.SIGNED_BUNDLED_POLICY,
        f'{{"generator_version": "{OLD_PROJECT_NAME}/0.2", "metadata": {{"generator": "{OLD_PROJECT_NAME}/0.2"}}}}\n',
    )
    _write(tmp_path / check_project_identity.SIGNED_BUNDLED_SIGNATURE, "signature\n")

    findings = check_project_identity.check_project_identity(tmp_path, (Path("win11_release_guard"),))

    assert "old project name" in _messages(findings)
    assert policy.read_text(encoding="utf-8")


def test_project_identity_scanner_verifies_clean_bundled_policy_signature(monkeypatch, tmp_path: Path) -> None:
    policy = _write(
        tmp_path / check_project_identity.SIGNED_BUNDLED_POLICY,
        '{"generator_version": "win11_release_guard/0.2"}\n',
    )
    signature = _write(tmp_path / check_project_identity.SIGNED_BUNDLED_SIGNATURE, "signature\n")
    calls: list[tuple[bytes, bytes]] = []

    def fake_verify(policy_bytes: bytes, signature_bytes: bytes) -> bool:
        calls.append((policy_bytes, signature_bytes))
        return True

    monkeypatch.setattr(check_project_identity, "verify_policy_signature", fake_verify)
    findings = check_project_identity.check_project_identity(tmp_path, (Path("win11_release_guard"),))

    assert findings == []
    assert calls == [(policy.read_bytes(), signature.read_bytes())]


def test_project_identity_scanner_fails_unsigned_bundled_policy(tmp_path: Path) -> None:
    _write(tmp_path / check_project_identity.SIGNED_BUNDLED_POLICY, '{"generator": "win11_release_guard/0.2"}\n')

    findings = check_project_identity.check_project_identity(tmp_path, (Path("win11_release_guard"),))

    assert "required bundled policy signature is missing" in _messages(findings)

from __future__ import annotations

from pathlib import Path

from tools import check_version_consistency


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _minimal_repo(tmp_path: Path, identity_version: str = "win11_release_guard/0.3.0") -> Path:
    _write(tmp_path / "pyproject.toml", '[project]\nname = "win11_release_guard"\nversion = "0.3.0"\n')
    _write(tmp_path / "win11_release_guard/version.py", 'PACKAGE_NAME = "win11_release_guard"\n')
    _write(tmp_path / "win11_release_guard/config.py", f'DEFAULT_USER_AGENT = "{identity_version}"\n')
    _write(tmp_path / "win11_release_guard/policy_schema.py", f'GENERATOR_VERSION = "{identity_version}"\n')
    _write(tmp_path / "win11_release_guard/wua_probe.py", f'CLIENT_APPLICATION_ID = "{identity_version}"\n')
    return tmp_path


def test_version_consistency_check_passes_current_repo() -> None:
    assert check_version_consistency.check_version_consistency() == []


def test_version_consistency_check_fails_runtime_marker_mismatch(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path, "win11_release_guard/0.1")

    findings = check_version_consistency.check_version_consistency(root)

    assert len(findings) == 3
    assert all("expected 'win11_release_guard/0.3.0'" in finding.message for finding in findings)


def test_version_consistency_cli_returns_nonzero_for_mismatch(tmp_path: Path, capsys) -> None:
    root = _minimal_repo(tmp_path, "win11_release_guard/0.1")

    code = check_version_consistency.main(["--root", str(root)])

    captured = capsys.readouterr()
    assert code == 1
    assert "Version consistency check failed:" in captured.out


def test_version_consistency_check_fails_stale_program_version_marker(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    _write(tmp_path / "README.md", "old marker: " + "win11_release_guard/0." + "2\n")

    findings = check_version_consistency.check_version_consistency(root)

    assert len(findings) == 1
    assert "stale 0.2 version marker" in findings[0].message


def test_version_consistency_check_fails_stale_marker_in_arbitrary_docs(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    _write(tmp_path / "docs" / "notes.md", "old marker: " + "win11_release_guard/0." + "2\n")

    findings = check_version_consistency.check_version_consistency(root)

    assert len(findings) == 1
    assert findings[0].path == Path("docs/notes.md")


def test_version_consistency_check_fails_stale_marker_in_arbitrary_tests(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    _write(tmp_path / "tests" / "test_random.py", "OLD = 'win11_release_guard/0." + "2'\n")

    findings = check_version_consistency.check_version_consistency(root)

    assert len(findings) == 1
    assert findings[0].path == Path("tests/test_random.py")


def test_version_helper_lives_inside_package_not_repo_root() -> None:
    root = Path(__file__).resolve().parents[1]

    assert not (root / "version.py").exists()
    assert (root / "win11_release_guard" / "version.py").is_file()

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

from tools import check_dependency_freshness


def _pypi_payload(*versions: str) -> dict[str, object]:
    return {
        "releases": {
            version: [{"filename": f"pkg-{version}.tar.gz", "yanked": False}]
            for version in versions
        }
    }


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._data
        return self._data[:size]


def test_dependency_freshness_current_when_latest_satisfies_specifier(monkeypatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\ndependencies = [\"demo-package>=1\"]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        check_dependency_freshness,
        "fetch_pypi_json",
        lambda name, *, timeout_seconds: _pypi_payload("1.0.0", "1.2.0"),
    )

    summary, exit_code = check_dependency_freshness.build_summary(pyproject, timeout_seconds=1)

    assert exit_code == 0
    assert summary["status"] == "current"
    assert summary["dependencies"][0]["update_available"] is False


def test_dependency_freshness_detects_outdated_direct_dependency(monkeypatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\ndependencies = [\"demo-package==1.0.0\"]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        check_dependency_freshness,
        "fetch_pypi_json",
        lambda name, *, timeout_seconds: _pypi_payload("1.0.0", "1.1.0"),
    )

    summary, exit_code = check_dependency_freshness.build_summary(pyproject, timeout_seconds=1)

    assert exit_code == 1
    assert summary["status"] == "updates_available"
    assert summary["update_count"] == 1
    assert summary["dependencies"][0]["latest_stable_version"] == "1.1.0"


def test_dependency_freshness_ignores_prerelease_latest(monkeypatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\ndependencies = [\"demo-package==1.0.0\"]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        check_dependency_freshness,
        "fetch_pypi_json",
        lambda name, *, timeout_seconds: _pypi_payload("1.0.0", "1.1.0rc1"),
    )

    summary, exit_code = check_dependency_freshness.build_summary(pyproject, timeout_seconds=1)

    assert exit_code == 0
    assert summary["status"] == "current"
    assert summary["dependencies"][0]["latest_stable_version"] == "1.0.0"


def test_dependency_freshness_network_failure_is_explicit(monkeypatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\ndependencies = [\"demo-package>=1\"]\n",
        encoding="utf-8",
    )

    def fail_fetch(name: str, *, timeout_seconds: float) -> dict[str, object]:
        raise RuntimeError("failed to query PyPI for demo-package: network down")

    monkeypatch.setattr(check_dependency_freshness, "fetch_pypi_json", fail_fetch)

    summary, exit_code = check_dependency_freshness.build_summary(pyproject, timeout_seconds=1)

    assert exit_code == 2
    assert summary["status"] == "unavailable"
    assert "network down" in summary["errors"][0]


def test_dependency_freshness_rejects_oversized_pypi_json(monkeypatch) -> None:
    monkeypatch.setattr(check_dependency_freshness, "MAX_PYPI_JSON_BYTES", 8)
    oversized = b"0123456789"

    monkeypatch.setattr(
        check_dependency_freshness.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(oversized),
    )

    try:
        check_dependency_freshness.fetch_pypi_json("demo-package", timeout_seconds=1)
    except RuntimeError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("oversized PyPI JSON was accepted")


def test_dependency_freshness_reports_http_errors(monkeypatch) -> None:
    def fail_urlopen(request: object, timeout: float) -> object:
        raise HTTPError(
            url="https://pypi.org/pypi/demo-package/json",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(check_dependency_freshness.urllib.request, "urlopen", fail_urlopen)

    try:
        check_dependency_freshness.fetch_pypi_json("demo-package", timeout_seconds=1)
    except RuntimeError as exc:
        assert "failed to query PyPI for demo-package" in str(exc)
        assert "404" in str(exc)
    else:
        raise AssertionError("HTTP error was not reported")


def test_dependency_freshness_reports_pyproject_decode_failure(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(b"\xff")

    summary, exit_code = check_dependency_freshness.build_summary(pyproject, timeout_seconds=1)

    assert exit_code == 2
    assert summary["status"] == "unavailable"
    assert "not valid UTF-8" in summary["errors"][0]


def test_dependency_freshness_parses_pyproject_dependencies() -> None:
    pyproject = {
        "project": {
            "dependencies": ["cryptography>=41"],
            "optional-dependencies": {"test": ["pytest>=8", "packaging>=24"]},
        }
    }

    dependencies = check_dependency_freshness.parse_direct_dependencies(pyproject)

    assert [dependency.requirement.name for dependency in dependencies] == [
        "cryptography",
        "packaging",
        "pytest",
    ]
    assert {dependency.group for dependency in dependencies} == {
        "project.dependencies",
        "project.optional-dependencies.test",
    }


def test_dependency_freshness_cli_writes_json(monkeypatch, tmp_path: Path, capsys) -> None:
    pyproject = tmp_path / "pyproject.toml"
    output = tmp_path / "freshness.json"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\ndependencies = [\"demo-package>=1\"]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        check_dependency_freshness,
        "fetch_pypi_json",
        lambda name, *, timeout_seconds: _pypi_payload("1.0.0"),
    )

    assert check_dependency_freshness.main(["--pyproject", str(pyproject), "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "current"
    assert "Dependency freshness: current" in capsys.readouterr().out


def test_dependency_freshness_cli_reports_output_write_failure(monkeypatch, tmp_path: Path, capsys) -> None:
    pyproject = tmp_path / "pyproject.toml"
    output = tmp_path / "missing" / "freshness.json"
    pyproject.write_text(
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\ndependencies = [\"demo-package>=1\"]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        check_dependency_freshness,
        "fetch_pypi_json",
        lambda name, *, timeout_seconds: _pypi_payload("1.0.0"),
    )

    assert check_dependency_freshness.main(["--pyproject", str(pyproject), "--output", str(output)]) == 2
    assert "Failed to write dependency freshness output" in capsys.readouterr().out

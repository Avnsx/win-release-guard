from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".css",
    ".html",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SCAN_TARGETS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs",
    ROOT / "tests",
    ROOT / "tools",
    ROOT / "win11_release_guard",
    ROOT / ".github",
)
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".cache",
    ".tmp",
    "build",
    "dist",
    "site",
}
LEGACY_PROTOTYPE_NAME = "_".join(("windows", "releases", "info")) + ".py"
FORBIDDEN_STALE_PATTERNS = (
    "w11_" + "versioning" + "_api_controller",
    "w11" + "-versioning-api-controller",
    "versioning" + "_api_controller",
    "win11" + "-release-guard",
)
FAKE_DOMAIN = "example" + ".invalid"


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        if not target.exists():
            continue
        candidates = [target] if target.is_file() else [path for path in target.rglob("*") if path.is_file()]
        for path in candidates:
            if "handover" in path.name and path.suffix.lower() == ".md":
                continue
            if set(path.relative_to(ROOT).parts).intersection(EXCLUDED_PARTS):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def _line_findings(patterns: tuple[str, ...]) -> list[str]:
    findings: list[str] = []
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if pattern in line:
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}: {pattern}")
    return findings


def test_public_brand_and_python_namespace_are_fixed() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "win-release-guard" in readme
    assert "win-release-guard" in pyproject
    assert (ROOT / "win11_release_guard").is_dir()
    assert not (ROOT / "win-release-guard").exists()


def test_removed_prototype_entrypoint_is_absent() -> None:
    assert not (ROOT / LEGACY_PROTOTYPE_NAME).exists()


def test_no_stale_package_or_project_identities() -> None:
    assert _line_findings(FORBIDDEN_STALE_PATTERNS + (LEGACY_PROTOTYPE_NAME,)) == []


def test_fake_invalid_domains_are_limited_to_fixtures() -> None:
    findings: list[str] = []
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if FAKE_DOMAIN not in line:
                continue
            relative_parts = path.relative_to(ROOT).parts
            if len(relative_parts) >= 2 and relative_parts[0] == "tests" and relative_parts[1] == "fixtures":
                continue
            findings.append(f"{path.relative_to(ROOT)}:{line_number}: {FAKE_DOMAIN}")

    assert findings == []

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
    "win" + "-release-guard",
    "win11" + "-release-guard",
)
FAKE_DOMAIN = "example" + ".invalid"


def _iter_source_files(*, include_signed_policy: bool = False) -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        if not target.exists():
            continue
        candidates = [target] if target.is_file() else [path for path in target.rglob("*") if path.is_file()]
        for path in candidates:
            relative_path = path.relative_to(ROOT)
            if "handover" in path.name and path.suffix.lower() == ".md":
                continue
            if set(relative_path.parts).intersection(EXCLUDED_PARTS):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def _line_findings(patterns: tuple[str, ...], *, include_signed_policy: bool = False) -> list[str]:
    findings: list[str] = []
    for path in _iter_source_files(include_signed_policy=include_signed_policy):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if pattern in line:
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}: {pattern}")
    return findings


def test_public_brand_and_python_namespace_are_fixed() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "win11_release_guard" in readme
    assert "win11_release_guard" in pyproject
    assert (ROOT / "win11_release_guard").is_dir()
    assert not (ROOT / ("win" + "-release-guard")).exists()


def test_default_public_pages_urls_use_renamed_repository_path() -> None:
    from win11_release_guard.config import (
        DEFAULT_PAGES_BASE_URL,
        DEFAULT_POLICY_URL,
        DEFAULT_PUBLISHED_POLICY_URLS,
    )

    base_url = "https://avnsx.github.io/win11_release_guard"

    assert DEFAULT_PAGES_BASE_URL == base_url
    assert DEFAULT_POLICY_URL == f"{base_url}/windows-release-policy.json"
    assert DEFAULT_PUBLISHED_POLICY_URLS == {
        "landing": f"{base_url}/",
        "policy": f"{base_url}/windows-release-policy.json",
        "signature": f"{base_url}/windows-release-policy.json.sig",
        "manifest": f"{base_url}/policy-manifest.json",
        "api_policy": f"{base_url}/api/v1/policy.json",
        "api_signature": f"{base_url}/api/v1/policy.sig",
        "api_manifest": f"{base_url}/api/v1/manifest.json",
    }


def test_removed_prototype_entrypoint_is_absent() -> None:
    assert not (ROOT / LEGACY_PROTOTYPE_NAME).exists()


def test_no_stale_package_or_project_identities() -> None:
    assert _line_findings(FORBIDDEN_STALE_PATTERNS + (LEGACY_PROTOTYPE_NAME,)) == []


def test_signed_bundled_policy_json_has_current_identity_and_valid_signature() -> None:
    from win11_release_guard.signing import verify_policy_signature

    policy_path = ROOT / "win11_release_guard" / "data" / "windows-release-policy.json"
    signature_path = policy_path.with_name(policy_path.name + ".sig")
    old_project_name = "win" + "-release-guard"
    old_repo_name = "Avnsx/" + old_project_name
    old_pages_root = "avnsx.github.io/" + old_project_name
    old_hyphenated_import = "win11" + "-release-guard"

    findings = _line_findings(
        (old_project_name, old_hyphenated_import, old_repo_name, old_pages_root),
        include_signed_policy=True,
    )

    assert findings == []
    assert "win11_release_guard/0.2" in policy_path.read_text(encoding="utf-8")
    assert verify_policy_signature(policy_path.read_bytes(), signature_path.read_bytes())


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

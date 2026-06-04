from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from win11_release_guard.signing import verify_policy_signature


REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNED_BUNDLED_POLICY = Path("win11_release_guard/data/windows-release-policy.json")
SIGNED_BUNDLED_SIGNATURE = Path("win11_release_guard/data/windows-release-policy.json.sig")
LEGACY_PROJECT_NAME = "win" + "-release-guard"
LEGACY_IMPORT_NAME = "win11" + "-release-guard"
LEGACY_REPO_NAME = "Avnsx/" + LEGACY_PROJECT_NAME
LEGACY_REPO_URL = "https://github.com/" + LEGACY_REPO_NAME
LEGACY_PAGES_ROOT = "avnsx.github.io/" + LEGACY_PROJECT_NAME
LEGACY_PAGES_URL = "https://" + LEGACY_PAGES_ROOT
LEGACY_ARCHIVE_NAME = LEGACY_PROJECT_NAME + "-source.zip"
LEGACY_PROTOTYPE_NAME = "_".join(("windows", "releases", "info"))
PACKAGING_AUTHOR = 'Mikail ("Avnsx") C.'
PYPROJECT_AUTHOR_SNIPPET = f"authors = [{{ name = '{PACKAGING_AUTHOR}' }}]"
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
DEFAULT_SCAN_TARGETS = (
    Path("README.md"),
    Path("AGENTS.md"),
    Path("pyproject.toml"),
    Path("docs"),
    Path("tests"),
    Path("tools"),
    Path("win11_release_guard"),
    Path(".github"),
)
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".cache",
    ".tmp",
    ".venv",
    "build",
    "dist",
    "site",
}
FORBIDDEN_PATTERNS = (
    (LEGACY_REPO_URL, "old GitHub repository URL"),
    (LEGACY_REPO_NAME, "old GitHub repository name"),
    (LEGACY_PAGES_URL, "old GitHub Pages URL"),
    (LEGACY_PAGES_ROOT, "old GitHub Pages host path"),
    (LEGACY_ARCHIVE_NAME, "old clean archive name"),
    (LEGACY_IMPORT_NAME, "old hyphenated import/package spelling"),
    (LEGACY_PROTOTYPE_NAME, "removed prototype entry point"),
    (LEGACY_PROJECT_NAME, "old project name"),
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int | None
    message: str

    def format(self) -> str:
        location = self.path.as_posix()
        if self.line_number is not None:
            location = f"{location}:{self.line_number}"
        return f"{location}: {self.message}"


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _is_excluded(relative_path: Path) -> bool:
    if set(relative_path.parts).intersection(EXCLUDED_PARTS):
        return True
    if "handover" in relative_path.name.lower() and relative_path.suffix.lower() == ".md":
        return True
    if relative_path.name == "dependency-freshness.json":
        return True
    if relative_path.name.endswith(".egg-info") or any(part.endswith(".egg-info") for part in relative_path.parts):
        return True
    return False


def _iter_files(root: Path, targets: Sequence[Path]) -> Iterable[Path]:
    for target in targets:
        source = root / target
        if not source.exists():
            continue
        candidates = [source] if source.is_file() else (path for path in source.rglob("*") if path.is_file())
        for path in candidates:
            relative_path = path.relative_to(root)
            if _is_excluded(relative_path):
                continue
            if _is_text_file(path):
                yield path


def _line_findings(path: Path, relative_path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern, description in FORBIDDEN_PATTERNS:
            if pattern in line:
                findings.append(Finding(relative_path, line_number, description))
    return findings


def _path_findings(relative_path: Path) -> list[Finding]:
    path_text = relative_path.as_posix()
    findings: list[Finding] = []
    for pattern, description in FORBIDDEN_PATTERNS:
        if pattern in path_text:
            findings.append(Finding(relative_path, None, description))
    return findings


def _verify_signed_bundled_policy(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    policy_path = root / SIGNED_BUNDLED_POLICY
    signature_path = root / SIGNED_BUNDLED_SIGNATURE
    if not policy_path.exists():
        return findings

    if not signature_path.exists():
        findings.append(Finding(SIGNED_BUNDLED_SIGNATURE, None, "required bundled policy signature is missing"))
    elif not verify_policy_signature(policy_path.read_bytes(), signature_path.read_bytes()):
        findings.append(Finding(SIGNED_BUNDLED_SIGNATURE, None, "bundled policy signature does not verify"))
    return findings


def _check_generated_site(root: Path) -> list[Finding]:
    site = root / "site"
    if not site.exists():
        return []
    findings: list[Finding] = []
    for path in site.rglob("*"):
        if not path.is_file() or not _is_text_file(path):
            continue
        relative_path = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern, description in FORBIDDEN_PATTERNS:
                if pattern in line:
                    findings.append(Finding(relative_path, line_number, f"generated site contains {description}"))
    return findings


def _check_packaging_metadata(root: Path) -> list[Finding]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return []
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    if PYPROJECT_AUTHOR_SNIPPET in text:
        return []
    return [
        Finding(
            Path("pyproject.toml"),
            None,
            f"required packaging author metadata is missing or changed; expected {PACKAGING_AUTHOR!r}",
        )
    ]


def check_project_identity(root: Path = REPO_ROOT, targets: Sequence[Path] = DEFAULT_SCAN_TARGETS) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    for path in _iter_files(root, targets):
        relative_path = path.relative_to(root)
        findings.extend(_path_findings(relative_path))
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(_line_findings(path, relative_path, text))
    findings.extend(_verify_signed_bundled_policy(root))
    findings.extend(_check_packaging_metadata(root))
    findings.extend(_check_generated_site(root))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail if old project/repository identity strings remain active.")
    parser.add_argument("paths", nargs="*", type=Path, help="Optional paths to scan relative to the repository root.")
    args = parser.parse_args(argv)
    targets = tuple(args.paths) if args.paths else DEFAULT_SCAN_TARGETS
    findings = check_project_identity(REPO_ROOT, targets)
    if findings:
        print("Project identity check failed:")
        for finding in findings:
            print(f"- {finding.format()}")
        return 1
    print("Project identity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

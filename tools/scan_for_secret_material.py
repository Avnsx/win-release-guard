from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_SCAN_PATHS = (
    "site",
    "win11_release_guard",
    "tests",
    "tools",
    "docs",
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    ".github",
)

EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".cache",
    ".tmp",
    "build",
    "dist",
    ".venv",
    "venv",
}
EXCLUDED_FILE_PATTERNS = (
    "*handover*.md",
)

PRIVATE_KEY_FILE_NAMES = {
    "private-" + "key.b64",
    "id_ed25519",
    "id_rsa",
    "id_ecdsa",
}

SAFE_FIXTURE_MARKERS = (
    "SAFE_SECRET_SCANNER_FIXTURE",
    "safe secret scanner fixture",
    "safe fixture",
)

SECRET_ENV_VAR = "WIN11_RELEASE_GUARD_POLICY_SIGNING_KEY_B64"

PRIVATE_KEY_BLOCKS = (
    "BEGIN " + "PRIVATE KEY",
    "BEGIN OPENSSH " + "PRIVATE KEY",
)

GITHUB_CLASSIC_PAT_RE = re.compile(r"\b" + re.escape("gh" + "p_") + r"[A-Za-z0-9_]{20,}\b")
GITHUB_FINE_GRAINED_PAT_RE = re.compile(r"\b" + re.escape("github" + "_pat_") + r"[A-Za-z0-9_]{20,}\b")
SECRET_ENV_VALUE_RE = re.compile(rf"\b{re.escape(SECRET_ENV_VAR)}\s*=\s*(?P<value>[^\s#\"']+|\"[^\"]+\"|'[^']+')")
ED25519_PRIVATE_SEED_LABEL_RE = re.compile(
    r"\b(?:ed25519[_ -]?private[_ -]?seed|private[_ -]?ed25519[_ -]?seed|ed25519[_ -]?seed[_ -]?private)\b\s*[:=]",
    re.IGNORECASE,
)
GENERIC_TOKEN_LITERAL_RE = re.compile(
    r"\b(?:github[_-]?pat|github[_-]?token|gh[_-]?token|personal[_-]?access[_-]?token|"
    r"access[_-]?token|api[_-]?token|auth[_-]?token|bearer[_-]?token|token)"
    r"\b\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9_./+=-]{20,})[\"']?",
    re.IGNORECASE,
)
AUTHORIZATION_BEARER_RE = re.compile(
    r"\bAuthorization\s*[:=]\s*Bearer\s+[A-Za-z0-9._~+/=-]{20,}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int | None
    kind: str
    message: str

    def format(self, root: Path) -> str:
        try:
            display_path = self.path.resolve().relative_to(root.resolve())
        except ValueError:
            display_path = self.path
        line_text = f":{self.line}" if self.line is not None else ""
        return f"{display_path}{line_text}: {self.kind}: {self.message}"


def _is_safe_fixture_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker.lower() in lowered for marker in SAFE_FIXTURE_MARKERS)


def _has_env_secret_value(line: str) -> bool:
    match = SECRET_ENV_VALUE_RE.search(line)
    if not match:
        return False
    value = match.group("value").strip().strip("\"'")
    if not value:
        return False
    placeholders = ("${{", "$", "%", "<", "example", "redacted")
    return not value.lower().startswith(placeholders)


def _path_findings(path: Path) -> list[Finding]:
    name = path.name.lower()
    findings: list[Finding] = []
    if name in PRIVATE_KEY_FILE_NAMES:
        findings.append(
            Finding(
                path=path,
                line=None,
                kind="private_key_file",
                message="private key file name is not allowed in the source tree",
            )
        )
    if name.endswith((".pem", ".key")):
        findings.append(
            Finding(
                path=path,
                line=None,
                kind="private_key_file",
                message="PEM/key files are not allowed in scanned source paths",
            )
        )
    if "private" in name and "key" in name:
        findings.append(
            Finding(
                path=path,
                line=None,
                kind="private_key_file",
                message="file name looks like private key material",
            )
        )
    return findings


def _content_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for marker in PRIVATE_KEY_BLOCKS:
            if marker in line:
                findings.append(
                    Finding(
                        path=path,
                        line=line_number,
                        kind="private_key_block",
                        message="private key PEM block marker is not allowed",
                    )
                )
        if GITHUB_CLASSIC_PAT_RE.search(line):
            findings.append(
                Finding(
                    path=path,
                    line=line_number,
                    kind="github_pat",
                    message="classic GitHub PAT-like token is not allowed",
                )
            )
        if GITHUB_FINE_GRAINED_PAT_RE.search(line):
            findings.append(
                Finding(
                    path=path,
                    line=line_number,
                    kind="github_pat",
                    message="fine-grained GitHub PAT-like token is not allowed",
                )
            )
        if _has_env_secret_value(line):
            findings.append(
                Finding(
                    path=path,
                    line=line_number,
                    kind="signing_secret_value",
                    message=f"{SECRET_ENV_VAR} must not be assigned a literal value",
                )
            )
        if ED25519_PRIVATE_SEED_LABEL_RE.search(line):
            findings.append(
                Finding(
                    path=path,
                    line=line_number,
                    kind="ed25519_private_seed",
                    message="Ed25519 private seed labels are not allowed in source files",
                )
            )
        if not _is_safe_fixture_line(line):
            if GENERIC_TOKEN_LITERAL_RE.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line=line_number,
                        kind="token_literal",
                        message="obvious token literal assignment is not allowed",
                    )
                )
            if AUTHORIZATION_BEARER_RE.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line=line_number,
                        kind="token_literal",
                        message="Bearer token literal is not allowed",
                    )
                )
    return findings


def _is_probably_binary(data: bytes) -> bool:
    return b"\0" in data[:4096]


def _iter_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        return
    if path.is_file():
        if not any(path.name and Path(path.name).match(pattern) for pattern in EXCLUDED_FILE_PATTERNS):
            yield path
        return
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in EXCLUDED_DIR_NAMES]
        current_dir = Path(dirpath)
        for filename in filenames:
            if any(Path(filename).match(pattern) for pattern in EXCLUDED_FILE_PATTERNS):
                continue
            yield current_dir / filename


def scan_paths(paths: Sequence[str | Path], *, root: Path | None = None) -> list[Finding]:
    scan_root = (root or Path.cwd()).resolve()
    findings: list[Finding] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_absolute():
            path = scan_root / path
        for file_path in _iter_files(path):
            findings.extend(_path_findings(file_path))
            try:
                data = file_path.read_bytes()
            except OSError as exc:
                findings.append(
                    Finding(
                        path=file_path,
                        line=None,
                        kind="read_error",
                        message=f"could not read file: {exc}",
                    )
                )
                continue
            if _is_probably_binary(data):
                continue
            text = data.decode("utf-8", errors="replace")
            findings.extend(_content_findings(file_path, text))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan source paths for committed secret material.")
    parser.add_argument("paths", nargs="*", help="Files or directories to scan.")
    args = parser.parse_args(argv)

    paths = args.paths or list(DEFAULT_SCAN_PATHS)
    root = Path.cwd()
    findings = scan_paths(paths, root=root)
    if findings:
        print("Secret material scan failed:", file=sys.stderr)
        for finding in findings:
            print(finding.format(root), file=sys.stderr)
        return 1

    print("Secret material scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

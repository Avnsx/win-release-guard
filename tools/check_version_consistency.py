from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "win11_release_guard"
PYPROJECT = Path("pyproject.toml")
VERSION_HELPER = Path("win11_release_guard/version.py")
VERSIONED_ASSIGNMENTS = (
    (Path("win11_release_guard/config.py"), "DEFAULT_USER_AGENT", "runtime_user_agent"),
    (Path("win11_release_guard/policy_schema.py"), "GENERATOR_VERSION", "generator_version"),
    (Path("win11_release_guard/wua_probe.py"), "CLIENT_APPLICATION_ID", "client_application_id"),
)
STALE_VERSION_MARKERS = (
    "0." + "2.0",
    PROJECT_NAME + "/0." + "2",
)
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
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".cache",
    ".tmp",
    "build",
    "dist",
    "site",
    "win11_release_guard.egg-info",
    "win_release_guard.egg-info",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str

    def format(self) -> str:
        return f"{self.path.as_posix()}: {self.message}"


@dataclass(frozen=True)
class AssignmentValue:
    kind: str
    value: str


def _read_project_version(root: Path) -> str | None:
    path = root / PYPROJECT
    if not path.exists():
        return None

    in_project_section = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            in_project_section = line == "[project]"
            continue
        if in_project_section and line.startswith("version"):
            name, separator, value = line.partition("=")
            if separator and name.strip() == "version":
                return value.strip().strip('"').strip("'")
    return None


def _read_assignment(path: Path, name: str) -> AssignmentValue | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None

    for node in tree.body:
        target_names: list[str] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            target_names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_names = [node.target.id]
            value = node.value
        if name not in target_names or value is None:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return AssignmentValue("literal", value.value)
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            return AssignmentValue("call", value.func.id)
    return None


def _expected_marker(project_version: str) -> str:
    return f"{PROJECT_NAME}/{project_version}"


def _load_version_helper(root: Path) -> ModuleType | None:
    if root.resolve() == REPO_ROOT.resolve():
        root_text = str(root)
        if sys.path[0] != root_text:
            sys.path.insert(0, root_text)
        current_version = importlib.import_module("win11_release_guard.version")
        module_path = Path(getattr(current_version, "__file__", "")).resolve()
        try:
            module_path.relative_to(root)
        except ValueError:
            sys.modules.pop("win11_release_guard.version", None)
            current_version = importlib.import_module("win11_release_guard.version")
        return current_version
    helper_path = root / VERSION_HELPER
    if not helper_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_win11_release_guard_version_check_target", helper_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runtime_helper_findings(root: Path, project_version: str) -> list[Finding]:
    if root.resolve() != REPO_ROOT.resolve():
        return []

    helper = _load_version_helper(root)
    if helper is None:
        return [Finding(VERSION_HELPER, "missing central version helper")]

    findings: list[Finding] = []
    expected_identity = _expected_marker(project_version)
    expected_values = {
        "PACKAGE_NAME": PROJECT_NAME,
        "source_tree_package_version": project_version,
        "package_version": project_version,
        "runtime_user_agent": expected_identity,
        "generator_version": expected_identity,
        "client_application_id": expected_identity,
    }
    for name, expected in expected_values.items():
        try:
            raw_value = getattr(helper, name)
            actual = raw_value(root) if name == "source_tree_package_version" else raw_value() if callable(raw_value) else raw_value
        except Exception as exc:
            findings.append(Finding(VERSION_HELPER, f"{name} failed: {exc}"))
            continue
        if actual != expected:
            findings.append(Finding(VERSION_HELPER, f"{name} returned {actual!r}, expected {expected!r}"))
    return findings


def _static_marker_findings(root: Path, project_version: str) -> list[Finding]:
    findings: list[Finding] = []
    helper_package_name = _read_assignment(root / VERSION_HELPER, "PACKAGE_NAME")
    if helper_package_name is None:
        findings.append(Finding(VERSION_HELPER, "missing PACKAGE_NAME assignment"))
    elif helper_package_name.kind != "literal" or helper_package_name.value != PROJECT_NAME:
        findings.append(Finding(VERSION_HELPER, f"PACKAGE_NAME is {helper_package_name.value!r}, expected {PROJECT_NAME!r}"))

    expected_identity = _expected_marker(project_version)
    for relative_path, constant_name, helper_function in VERSIONED_ASSIGNMENTS:
        path = root / relative_path
        value = _read_assignment(path, constant_name)
        if value is None:
            findings.append(Finding(relative_path, f"missing assignment {constant_name}"))
            continue
        if value.kind == "call":
            if value.value != helper_function:
                findings.append(
                    Finding(
                        relative_path,
                        f"{constant_name} calls {value.value!r}, expected {helper_function!r}",
                    )
                )
            continue
        if value.value != expected_identity:
            findings.append(
                Finding(
                    relative_path,
                    f"{constant_name} is {value.value!r}, expected {expected_identity!r}",
                )
            )
    return findings


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if set(relative.parts).intersection(EXCLUDED_PARTS):
            continue
        if "handover" in path.name.lower() and path.suffix.lower() == ".md":
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return sorted(files)


def _is_allowed_stale_marker(relative: Path, line: str) -> bool:
    if relative == Path("win11_release_guard/data/windows-release-policy.json"):
        return True
    if relative == Path("tests/test_signing.py") and "raw_policy" in line and "generator_version" in line:
        return True
    if relative == Path("tests/test_branding_contract.py") and "policy_path" in line:
        return True
    return False


def _stale_version_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_text_files(root):
        relative = path.relative_to(root)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if not any(marker in line for marker in STALE_VERSION_MARKERS):
                continue
            if _is_allowed_stale_marker(relative, line):
                continue
            findings.append(Finding(relative, f"stale 0.2 version marker on line {line_number}"))
    return findings


def check_version_consistency(root: Path = REPO_ROOT) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    project_version = _read_project_version(root)
    if not project_version:
        return [Finding(PYPROJECT, "missing [project] version")]

    findings.extend(_runtime_helper_findings(root, project_version))
    findings.extend(_static_marker_findings(root, project_version))
    findings.extend(_stale_version_findings(root))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if package and runtime version identity markers drift apart."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to check. Defaults to the current tool's repository.",
    )
    args = parser.parse_args(argv)

    findings = check_version_consistency(args.root)
    if findings:
        print("Version consistency check failed:")
        for finding in findings:
            print(f"- {finding.format()}")
        return 1
    print("Version consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .config import DEFAULT_DISM_TIMEOUT_SECONDS, DEFAULT_PANTHER_TAIL_MAX_BYTES


DISM_PACKAGES_COMMAND = ["dism.exe", "/Online", "/Get-Packages", "/Format:List"]
PANTHER_SETUP_LOG_PATHS = (
    r"%WINDIR%\Panther\setupact.log",
    r"C:\$Windows.~BT\Sources\Panther\setupact.log",
    r"C:\$Windows.~BT\Sources\Rollback\setupact.log",
)
WINDOWS_UPDATE_POLICY_PATH = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
WINDOWS_UPDATE_AU_POLICY_PATH = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
OS_UPGRADE_POLICY_PATH = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\OSUpgrade"
PENDING_REBOOT_REGISTRY_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootInProgress",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\PostRebootReporting",
    r"SYSTEM\CurrentControlSet\Control\Session Manager",
)
POLICY_VALUE_NAMES = (
    "TargetReleaseVersion",
    "TargetReleaseVersionInfo",
    "ProductVersion",
    "DeferFeatureUpdates",
    "DeferFeatureUpdatesPeriodInDays",
    "BranchReadinessLevel",
    "DisableOSUpgrade",
    "UseWUServer",
    "WUServer",
    "WUStatusServer",
)


def _kb_ids_from_text(text: str | None) -> list[str]:
    return list(dict.fromkeys(match.upper() for match in re.findall(r"(?<![A-Z0-9])KB\d{6,8}\b", text or "", re.IGNORECASE)))


def parse_dism_packages(text: str) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    current: dict[str, Any] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                packages.append(_normalize_dism_package(current))
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower().replace(" ", "_")
        current[normalized_key] = value.strip()

    if current:
        packages.append(_normalize_dism_package(current))
    return packages


def _normalize_dism_package(raw: Mapping[str, Any]) -> dict[str, Any]:
    package_name = str(raw.get("package_identity") or raw.get("package_name") or raw.get("identity") or "")
    package_text = " ".join(str(value) for value in raw.values())
    release_type = str(raw.get("release_type") or "")
    return {
        "package_name": package_name or None,
        "kb_ids": _kb_ids_from_text(package_text),
        "state": raw.get("state"),
        "release_type": release_type or None,
        "install_time": raw.get("install_time"),
        "is_lcu_hint": bool(re.search(r"(rollupfix|cumulative|latest cumulative|lcu)", f"{package_name} {release_type}", re.IGNORECASE)),
        "raw": dict(raw),
    }


def query_dism_packages(timeout_seconds: float = DEFAULT_DISM_TIMEOUT_SECONDS) -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "packages": [], "latest_lcu_hints": [], "errors": ["DISM package audit requires Windows."]}
    try:
        proc = subprocess.run(
            DISM_PACKAGES_COMMAND,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "available": False,
            "packages": [],
            "latest_lcu_hints": [],
            "errors": [f"DISM Get-Packages timed out after {timeout_seconds:g} seconds."],
            "timed_out": True,
        }
    except OSError as exc:
        return {"available": False, "packages": [], "latest_lcu_hints": [], "errors": [f"DISM Get-Packages unavailable: {exc}"]}

    text = f"{proc.stdout}\n{proc.stderr}"
    packages = parse_dism_packages(text)
    errors = []
    if proc.returncode != 0:
        errors.append(f"DISM Get-Packages failed with exit code {proc.returncode}.")
    latest_lcu_hints = [package for package in packages if package.get("is_lcu_hint") and package.get("state") == "Installed"]
    return {
        "available": proc.returncode == 0,
        "packages": packages,
        "latest_lcu_hints": latest_lcu_hints[-10:],
        "errors": errors,
        "returncode": proc.returncode,
    }


def _expand_windows_path(path: str) -> str:
    return os.path.expandvars(path)


def read_file_tail(path: str | Path, max_bytes: int = DEFAULT_PANTHER_TAIL_MAX_BYTES) -> str:
    log_path = Path(path)
    size = log_path.stat().st_size
    bytes_to_read = max(0, min(int(max_bytes), int(size)))
    with log_path.open("rb") as handle:
        if bytes_to_read and size > bytes_to_read:
            handle.seek(-bytes_to_read, os.SEEK_END)
        return handle.read(bytes_to_read).decode("utf-8", errors="replace")


def read_panther_logs(
    paths: tuple[str, ...] = PANTHER_SETUP_LOG_PATHS,
    max_bytes: int = DEFAULT_PANTHER_TAIL_MAX_BYTES,
) -> dict[str, Any]:
    logs: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw_path in paths:
        try:
            path = Path(_expand_windows_path(raw_path))
        except (NotImplementedError, OSError) as exc:
            errors.append(f"Panther path unavailable {raw_path}: {exc}")
            continue
        if not path.exists() or not path.is_file():
            continue
        try:
            content = read_file_tail(path, max_bytes=max_bytes)
        except OSError as exc:
            errors.append(f"Panther log read failed {path}: {exc}")
            continue
        logs.append(
            {
                "path": str(path),
                "tail_bytes": len(content.encode("utf-8", errors="replace")),
                "content": content,
                "evidence": extract_setup_log_evidence(content, source_path=str(path)),
            }
        )
    setup_failure_evidence = [
        evidence
        for log in logs
        for evidence in log.get("evidence", [])
        if evidence.get("kind") in {"setup_failure", "rollback"}
    ]
    return {
        "available": bool(logs),
        "logs": logs,
        "setup_failure_evidence": setup_failure_evidence,
        "errors": errors,
    }


def extract_setup_log_evidence(text: str, *, source_path: str | None = None) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        lower = line.lower()
        release_match = re.search(r"\b(?:target(?:release|version)?|version)\s*[:= ]+\s*(\d{2}H[12])\b", line, re.IGNORECASE)
        build_match = re.search(r"\b(?:target(?:build)?|build)\s*[:= ]+\s*(\d{5}(?:\.\d+)?)\b", line, re.IGNORECASE)
        if release_match:
            evidence.append(
                {
                    "kind": "target_release",
                    "target_release": release_match.group(1).upper(),
                    "line_number": line_number,
                    "line": line,
                    "source_path": source_path,
                }
            )
        if build_match:
            evidence.append(
                {
                    "kind": "target_build",
                    "target_build": build_match.group(1),
                    "line_number": line_number,
                    "line": line,
                    "source_path": source_path,
                }
            )
        if "rollback" in lower or "roll back" in lower or "rolled back" in lower:
            evidence.append({"kind": "rollback", "line_number": line_number, "line": line, "source_path": source_path})
        elif (
            "setup failed" in lower
            or "setup failure" in lower
            or "installation failed" in lower
            or "upgrade failed" in lower
            or re.search(r"\b0x[0-9a-f]{8}\b", lower)
        ):
            evidence.append({"kind": "setup_failure", "line_number": line_number, "line": line, "source_path": source_path})
    return evidence


def _read_registry_values(path: str, value_names: tuple[str, ...] = POLICY_VALUE_NAMES) -> tuple[dict[str, Any], list[str]]:
    values: dict[str, Any] = {}
    errors: list[str] = []
    if os.name != "nt":
        return values, ["Registry policy audit requires Windows."]
    try:
        import winreg
    except Exception as exc:
        return values, [f"winreg unavailable: {exc}"]
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for name in value_names:
                try:
                    values[name] = winreg.QueryValueEx(key, name)[0]
                except OSError:
                    continue
    except FileNotFoundError:
        return values, []
    except OSError as exc:
        errors.append(f"Registry read failed for HKLM\\{path}: {exc}")
    return values, errors


def read_windows_update_policy_registry() -> dict[str, Any]:
    paths = (WINDOWS_UPDATE_POLICY_PATH, WINDOWS_UPDATE_AU_POLICY_PATH, OS_UPGRADE_POLICY_PATH)
    merged: dict[str, Any] = {}
    by_path: dict[str, Any] = {}
    errors: list[str] = []
    for path in paths:
        values, path_errors = _read_registry_values(path)
        if values:
            by_path[f"HKLM\\{path}"] = values
            merged.update(values)
        errors.extend(path_errors)
    return {"available": bool(by_path), "values": merged, "by_path": by_path, "errors": errors}


def read_pending_reboot_state() -> dict[str, Any]:
    if os.name != "nt":
        return {"pending": False, "evidence": [], "errors": ["Pending reboot audit requires Windows."]}
    try:
        import winreg
    except Exception as exc:
        return {"pending": False, "evidence": [], "errors": [f"winreg unavailable: {exc}"]}

    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in PENDING_REBOOT_REGISTRY_PATHS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                if path.endswith(r"Session Manager"):
                    try:
                        value = winreg.QueryValueEx(key, "PendingFileRenameOperations")[0]
                    except OSError:
                        continue
                    evidence.append({"path": f"HKLM\\{path}", "value": "PendingFileRenameOperations", "data": value})
                else:
                    evidence.append({"path": f"HKLM\\{path}"})
        except FileNotFoundError:
            continue
        except OSError as exc:
            errors.append(f"Pending reboot registry read failed for HKLM\\{path}: {exc}")
    return {"pending": bool(evidence), "evidence": evidence, "errors": errors}


def collect_audit_diagnostics(
    *,
    dism_timeout_seconds: float = DEFAULT_DISM_TIMEOUT_SECONDS,
    panther_tail_max_bytes: int = DEFAULT_PANTHER_TAIL_MAX_BYTES,
) -> dict[str, Any]:
    """Collect read-only audit evidence for conflict resolution."""

    dism_packages = query_dism_packages(timeout_seconds=dism_timeout_seconds)
    panther_logs = read_panther_logs(max_bytes=panther_tail_max_bytes)
    windows_update_policy = read_windows_update_policy_registry()
    pending_reboot = read_pending_reboot_state()
    return {
        "dism_packages": dism_packages,
        "panther_logs": panther_logs,
        "setup_failure_evidence": panther_logs.get("setup_failure_evidence", []),
        "windows_update_policy": windows_update_policy,
        "pending_reboot": pending_reboot,
    }


__all__ = [
    "collect_audit_diagnostics",
    "extract_setup_log_evidence",
    "parse_dism_packages",
    "query_dism_packages",
    "read_file_tail",
    "read_panther_logs",
    "read_pending_reboot_state",
    "read_windows_update_policy_registry",
]

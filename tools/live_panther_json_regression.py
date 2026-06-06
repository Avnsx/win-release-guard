from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


RAW_PANTHER_STRINGS = (
    "$WINDOWS.~BT",
    "SetupPlatform.exe",
    "SERIALIZEVERBOSE",
    "Set boot command",
    "Update Boot Sector",
)

COMPACT_MARKERS = (
    "content_omitted",
    "content_chars",
    "content_bytes_utf8",
)

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
JSON_TOOL_TIMEOUT_SECONDS = 30
PROCESS_TIMEOUT_RETURNCODE = 124
PROCESS_START_RETURNCODE = 127


@dataclass(frozen=True)
class HarnessCheck:
    name: str
    ok: bool
    detail: str
    data: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "data": dict(self.data),
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _text_counts(text: str, needles: Sequence[str]) -> dict[str, int]:
    return {needle: text.count(needle) for needle in needles}


def _coerce_process_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _process_failure(
    *,
    args: object,
    returncode: int,
    stderr: str,
    stdout: object = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=_coerce_process_text(stdout),
        stderr=stderr,
    )


def _file_status(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {
            "path": str(path),
            "exists": False,
            "is_file": False,
            "size_bytes": None,
        }
    except OSError as exc:
        return {
            "path": str(path),
            "exists": None,
            "is_file": None,
            "size_bytes": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "path": str(path),
        "exists": True,
        "is_file": path.is_file(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _remove_stale_output(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        if not path.is_file():
            return f"{path} exists and is not a file."
        path.unlink()
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _cmd_redirection_command(
    *,
    python_executable: str,
    output_path: Path,
    include_raw_local_diagnostics: bool,
) -> str:
    raw_arg = " --include-raw-local-diagnostics" if include_raw_local_diagnostics else ""
    return f'call "{python_executable}" -m win11_release_guard --json-pretty{raw_arg} > "{output_path}"'


def _run_cmd_redirection(
    *,
    root: Path,
    python_executable: str,
    output_path: Path,
    include_raw_local_diagnostics: bool,
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> tuple[str, subprocess.CompletedProcess[str]]:
    command = _cmd_redirection_command(
        python_executable=python_executable,
        output_path=output_path,
        include_raw_local_diagnostics=include_raw_local_diagnostics,
    )
    env = os.environ.copy()
    env["WIN11_RELEASE_GUARD_STRICT_PRODUCTION"] = "1"
    command_line = f"cmd.exe /d /c {command}"
    try:
        proc = subprocess.run(
            command_line,
            cwd=root,
            capture_output=True,
            env=env,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = _coerce_process_text(exc.stderr)
        if stderr:
            stderr += "\n"
        stderr += f"Timed out after {timeout_seconds} seconds."
        proc = _process_failure(
            args=command_line,
            returncode=PROCESS_TIMEOUT_RETURNCODE,
            stdout=exc.stdout,
            stderr=stderr,
        )
    except OSError as exc:
        proc = _process_failure(
            args=command_line,
            returncode=PROCESS_START_RETURNCODE,
            stderr=f"{type(exc).__name__}: {exc}",
        )
    return command, proc


def _validate_json_tool(
    *,
    python_executable: str,
    path: Path,
    timeout_seconds: int = JSON_TOOL_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    args = [python_executable, "-m", "json.tool", str(path)]
    try:
        return subprocess.run(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = _coerce_process_text(exc.stderr)
        if stderr:
            stderr += "\n"
        stderr += f"Timed out after {timeout_seconds} seconds."
        return _process_failure(
            args=args,
            returncode=PROCESS_TIMEOUT_RETURNCODE,
            stderr=stderr,
        )
    except OSError as exc:
        return _process_failure(
            args=args,
            returncode=PROCESS_START_RETURNCODE,
            stderr=f"{type(exc).__name__}: {exc}",
        )


def _read_json(path: Path) -> tuple[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object.")
    return text, payload


def _verdict_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    target = payload.get("target")
    target_payload = target if isinstance(target, Mapping) else {}
    return {
        "status": payload.get("status"),
        "source_status": payload.get("source_status"),
        "policy_signature_status": payload.get("policy_signature_status"),
        "strict_production": payload.get("strict_production"),
        "installed_release": payload.get("installed_release"),
        "target.version": target_payload.get("version"),
        "target.build_family": target_payload.get("build_family"),
    }


def _valid_panther_compaction_marker_count(value: object, *, in_panther_context: bool = False) -> int:
    count = 0
    if isinstance(value, Mapping):
        item_context = in_panther_context or value.get("source") == "panther"
        content_chars = value.get("content_chars")
        content_bytes = value.get("content_bytes_utf8")
        if (
            value.get("content_omitted") is True
            and isinstance(content_chars, int)
            and not isinstance(content_chars, bool)
            and content_chars >= 0
            and isinstance(content_bytes, int)
            and not isinstance(content_bytes, bool)
            and content_bytes >= 0
            and item_context
        ):
            count += 1
        for key, child in value.items():
            child_context = item_context or _looks_like_panther_context(key)
            count += _valid_panther_compaction_marker_count(child, in_panther_context=child_context)
    elif isinstance(value, list):
        for child in value:
            count += _valid_panther_compaction_marker_count(child, in_panther_context=in_panther_context)
    return count


def _looks_like_panther_context(value: object) -> bool:
    text = str(value).lower()
    return (
        text == "panther_logs"
        or "panther" in text
        or "$windows.~bt" in text
        or "setupact.log" in text
        or "setuperr.log" in text
    )


def _format_json_path(parts: Sequence[str]) -> str:
    path = "$"
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            path += part
        elif part.isidentifier():
            path += f".{part}"
        else:
            path += f"[{json.dumps(part)}]"
    return path


def _panther_content_stats(value: object) -> dict[str, Any]:
    sample_paths: list[str] = []
    content_values = 0
    content_chars = 0
    content_bytes_utf8 = 0

    def walk(item: object, path: tuple[str, ...], in_panther_context: bool) -> None:
        nonlocal content_values, content_chars, content_bytes_utf8

        if isinstance(item, Mapping):
            item_context = in_panther_context or item.get("source") == "panther"
            for key, child in item.items():
                key_text = str(key)
                child_path = (*path, key_text)
                child_context = item_context or _looks_like_panther_context(key_text)
                if key_text == "content" and isinstance(child, str) and child_context:
                    content_values += 1
                    content_chars += len(child)
                    content_bytes_utf8 += len(child.encode("utf-8", errors="replace"))
                    if len(sample_paths) < 5:
                        sample_paths.append(_format_json_path(child_path))
                walk(child, child_path, child_context)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, (*path, f"[{index}]"), in_panther_context)

    walk(value, (), False)
    return {
        "content_values": content_values,
        "content_chars": content_chars,
        "content_bytes_utf8": content_bytes_utf8,
        "sample_paths": sample_paths,
    }


def validate_live_outputs(
    *,
    default_text: str,
    default_payload: Mapping[str, Any],
    raw_text: str,
    raw_payload: Mapping[str, Any],
) -> list[HarnessCheck]:
    checks: list[HarnessCheck] = []

    default_raw_counts = _text_counts(default_text, RAW_PANTHER_STRINGS)
    checks.append(
        HarnessCheck(
            name="default_raw_strings_absent",
            ok=all(count == 0 for count in default_raw_counts.values()),
            detail="Default JSON must not contain raw Panther/setup log strings.",
            data=default_raw_counts,
        )
    )

    default_panther_content = _panther_content_stats(default_payload)
    checks.append(
        HarnessCheck(
            name="default_raw_panther_content_absent",
            ok=default_panther_content["content_values"] == 0,
            detail="Default JSON must not contain raw Panther/setup content fields.",
            data=default_panther_content,
        )
    )

    marker_counts = _text_counts(default_text, COMPACT_MARKERS)
    valid_marker_count = _valid_panther_compaction_marker_count(default_payload)
    raw_counts = _text_counts(raw_text, RAW_PANTHER_STRINGS)
    raw_panther_content = _panther_content_stats(raw_payload)
    default_compacted_source_present = valid_marker_count > 0
    raw_panther_source_present = raw_panther_content["content_values"] > 0
    no_panther_source_present = not default_compacted_source_present and not raw_panther_source_present
    if raw_panther_source_present:
        panther_source_status = "raw_diagnostics_present"
    elif default_compacted_source_present:
        panther_source_status = "default_compaction_without_raw_opt_in"
    else:
        panther_source_status = "no_panther_source_present"
    checks.append(
        HarnessCheck(
            name="panther_source_status",
            ok=True,
            detail=(
                "Reports whether readable Panther/setup diagnostics were present in this live run. "
                "No Panther source is acceptable on clean machines."
            ),
            data={
                "status": panther_source_status,
                "no_panther_source_present": no_panther_source_present,
                "default_compaction_marker_objects": valid_marker_count,
                "raw_content_values": raw_panther_content["content_values"],
            },
        )
    )

    checks.append(
        HarnessCheck(
            name="default_compact_markers_present",
            ok=no_panther_source_present or all(count > 0 for count in marker_counts.values()),
            detail=(
                "Default JSON must contain Panther/setup compaction markers when readable "
                "Panther/setup diagnostics exist. Markers are not required when no Panther "
                "source is present."
            ),
            data={
                **marker_counts,
                "required": not no_panther_source_present,
                "no_panther_source_present": no_panther_source_present,
            },
        )
    )
    checks.append(
        HarnessCheck(
            name="default_compact_marker_objects_valid",
            ok=no_panther_source_present or valid_marker_count > 0,
            detail=(
                "Default JSON must contain at least one structured compaction marker object "
                "with content_omitted=true and numeric content size fields when readable "
                "Panther/setup diagnostics exist."
            ),
            data={
                "valid_compaction_marker_objects": valid_marker_count,
                "required": not no_panther_source_present,
                "no_panther_source_present": no_panther_source_present,
            },
        )
    )

    checks.append(
        HarnessCheck(
            name="raw_opt_in_panther_content_present",
            ok=(not default_compacted_source_present) or raw_panther_source_present,
            detail=(
                "Raw opt-in JSON must contain Panther/setup diagnostic content when default "
                "JSON proved such content existed through compaction markers. Known marker "
                "strings are counted as leak signatures but are not required because live "
                "Panther logs differ by machine and setup path."
            ),
            data={
                **raw_panther_content,
                "known_marker_counts": raw_counts,
                "required": default_compacted_source_present,
                "no_panther_source_present": no_panther_source_present,
            },
        )
    )
    checks.append(
        HarnessCheck(
            name="raw_strings_only_in_opt_in",
            ok=all(default_raw_counts[item] == 0 for item in RAW_PANTHER_STRINGS),
            detail=(
                "Known Panther/setup marker strings must not appear in default JSON. "
                "Their presence in raw opt-in output is useful evidence but not mandatory."
            ),
            data={
                "default_counts": default_raw_counts,
                "raw_counts": raw_counts,
            },
        )
    )

    verdict = _verdict_summary(default_payload)
    verdict_ok = (
        isinstance(verdict["status"], str)
        and bool(verdict["status"])
        and verdict["source_status"] == "REMOTE_POLICY_OK"
        and verdict["policy_signature_status"] == "valid"
        and verdict["strict_production"] is True
        and isinstance(verdict["installed_release"], str)
        and bool(verdict["installed_release"])
        and isinstance(verdict["target.version"], str)
        and bool(verdict["target.version"])
        and isinstance(verdict["target.build_family"], int)
    )
    checks.append(
        HarnessCheck(
            name="verdict_fields_sane",
            ok=verdict_ok,
            detail="Strict-production verdict fields must remain populated and meaningful.",
            data=verdict,
        )
    )

    raw_verdict = _verdict_summary(raw_payload)
    checks.append(
        HarnessCheck(
            name="raw_opt_in_verdict_matches_default",
            ok=raw_verdict == verdict,
            detail="Raw diagnostic opt-in must not change verdict/status fields.",
            data={
                "default": verdict,
                "raw": raw_verdict,
            },
        )
    )
    return checks


def run_harness(*, output_dir: Path, python_executable: str, root: Path) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "error": "Live Panther JSON regression requires Windows because it validates local Panther/setup diagnostics.",
        }

    output_dir = output_dir.resolve()
    root = root.resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "error": "Could not create live Panther JSON output directory.",
            "exception": f"{type(exc).__name__}: {exc}",
        }
    default_path = output_dir / "out.json"
    raw_path = output_dir / "out.raw.json"
    output_paths = {
        "default_json": default_path,
        "raw_json": raw_path,
    }
    stale_output_errors = {
        label: error
        for label, path in output_paths.items()
        if (error := _remove_stale_output(path)) is not None
    }
    if stale_output_errors:
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "default_json": str(default_path),
            "raw_json": str(raw_path),
            "files": {label: _file_status(path) for label, path in output_paths.items()},
            "error": "Could not remove stale generated output before the live run.",
            "stale_output_errors": stale_output_errors,
        }

    default_command, default_proc = _run_cmd_redirection(
        root=root,
        python_executable=python_executable,
        output_path=default_path,
        include_raw_local_diagnostics=False,
    )
    raw_command, raw_proc = _run_cmd_redirection(
        root=root,
        python_executable=python_executable,
        output_path=raw_path,
        include_raw_local_diagnostics=True,
    )

    command_results = {
        "default_json": {
            "command": f"cmd.exe /d /c {default_command}",
            "environment": {"WIN11_RELEASE_GUARD_STRICT_PRODUCTION": "1"},
            "returncode": default_proc.returncode,
            "stdout": default_proc.stdout,
            "stderr": default_proc.stderr,
        },
        "raw_json": {
            "command": f"cmd.exe /d /c {raw_command}",
            "environment": {"WIN11_RELEASE_GUARD_STRICT_PRODUCTION": "1"},
            "returncode": raw_proc.returncode,
            "stdout": raw_proc.stdout,
            "stderr": raw_proc.stderr,
        },
    }
    file_results = {label: _file_status(path) for label, path in output_paths.items()}

    if default_proc.returncode != 0 or raw_proc.returncode != 0:
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "default_json": str(default_path),
            "raw_json": str(raw_path),
            "commands": command_results,
            "files": file_results,
            "error": "One or more win11_release_guard JSON commands failed.",
        }
    missing_outputs = {
        label: status
        for label, status in file_results.items()
        if status.get("exists") is not True or status.get("is_file") is not True
    }
    if missing_outputs:
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "default_json": str(default_path),
            "raw_json": str(raw_path),
            "commands": command_results,
            "files": file_results,
            "error": "One or more JSON output files were not created by the live run.",
            "missing_outputs": missing_outputs,
        }

    default_json_tool = _validate_json_tool(python_executable=python_executable, path=default_path)
    raw_json_tool = _validate_json_tool(python_executable=python_executable, path=raw_path)
    json_tool_results = {
        "default_json": {
            "returncode": default_json_tool.returncode,
            "stderr": default_json_tool.stderr,
        },
        "raw_json": {
            "returncode": raw_json_tool.returncode,
            "stderr": raw_json_tool.stderr,
        },
    }
    if default_json_tool.returncode != 0 or raw_json_tool.returncode != 0:
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "default_json": str(default_path),
            "raw_json": str(raw_path),
            "commands": command_results,
            "files": file_results,
            "json_tool": json_tool_results,
            "error": "python -m json.tool validation failed.",
        }

    try:
        default_text, default_payload = _read_json(default_path)
        raw_text, raw_payload = _read_json(raw_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "output_dir": str(output_dir),
            "default_json": str(default_path),
            "raw_json": str(raw_path),
            "commands": command_results,
            "files": file_results,
            "json_tool": json_tool_results,
            "error": "JSON output could not be loaded as a UTF-8 JSON object.",
            "exception": f"{type(exc).__name__}: {exc}",
        }
    checks = validate_live_outputs(
        default_text=default_text,
        default_payload=default_payload,
        raw_text=raw_text,
        raw_payload=raw_payload,
    )
    ok = all(check.ok for check in checks)
    panther_source_status = next(
        (dict(check.data) for check in checks if check.name == "panther_source_status"),
        None,
    )
    return {
        "ok": ok,
        "output_dir": str(output_dir),
        "default_json": str(default_path),
        "raw_json": str(raw_path),
        "commands": command_results,
        "files": file_results,
        "json_tool": json_tool_results,
        "checks": [check.to_dict() for check in checks],
        "panther_source_status": panther_source_status,
        "verdict": _verdict_summary(default_payload),
        "powershell_5_note": (
            "Windows PowerShell 5 native-command redirection can write UTF-16LE output that "
            "python -m json.tool rejects as non-UTF-8. This harness uses cmd.exe redirection. "
            "PowerShell users should prefer cmd.exe redirection or Out-File -Encoding utf8."
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the live Windows Panther JSON regression harness.",
        epilog=(
            "This is output validation only. It runs strict-production JSON twice through cmd.exe "
            "redirection, validates both files with python -m json.tool, and compares compact vs raw "
            "local Panther/setup diagnostics. PowerShell 5 users should avoid plain > redirection for "
            "JSON validation because it can produce UTF-16LE files."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_repo_root() / ".tmp" / "live-panther-json-regression",
        help="Directory for out.json, out.raw.json, and report.json.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to run win11_release_guard and json.tool.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = _repo_root()
    try:
        report = run_harness(
            output_dir=args.output_dir,
            python_executable=str(args.python),
            root=root,
        )
    except Exception as exc:  # pragma: no cover - last-resort structured failure path
        report = {
            "ok": False,
            "output_dir": str(args.output_dir),
            "error": "Unhandled live Panther JSON harness failure.",
            "exception": f"{type(exc).__name__}: {exc}",
        }
    report_output_dir = Path(str(report.get("output_dir", args.output_dir)))
    report_path = report_output_dir / "report.json"
    try:
        report_output_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        report = {
            **report,
            "ok": False,
            "report_path": str(report_path),
            "report_write_error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

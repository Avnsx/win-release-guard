from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_SNIPPET_CHARS = 96

PANTHER_LEAK_MARKERS: tuple[tuple[str, str], ...] = (
    ("windows_bt", "$WINDOWS.~BT"),
    ("setup_platform", "SetupPlatform.exe"),
    ("serialize_verbose", "SERIALIZEVERBOSE"),
    ("set_boot_command", "Set boot command"),
    ("update_boot_sector", "Update Boot Sector"),
    ("set_newos_boot_entry", "Set NewOS boot entry"),
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONTROL_WHITESPACE_RE = re.compile(r"[\r\n\t]+")


@dataclass(frozen=True)
class PantherLeakFinding:
    path: str
    value_kind: str
    value_chars: int
    value_bytes_utf8: int
    matched_markers: tuple[str, ...]
    snippet: str
    fix_strategy: str
    fix_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "value_kind": self.value_kind,
            "value_chars": self.value_chars,
            "value_bytes_utf8": self.value_bytes_utf8,
            "matched_markers": list(self.matched_markers),
            "snippet": self.snippet,
            "fix_strategy": self.fix_strategy,
            "fix_hint": self.fix_hint,
        }


def _format_json_path(parts: Sequence[str | int]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif _IDENTIFIER_RE.fullmatch(part):
            path += f".{part}"
        else:
            path += f"[{json.dumps(part)}]"
    return path


def _matched_marker_names(value: str) -> tuple[str, ...]:
    lower_value = value.lower()
    return tuple(
        name for name, marker in PANTHER_LEAK_MARKERS if marker.lower() in lower_value
    )


def _sanitized_snippet(value: str, *, markers: Sequence[str], snippet_chars: int) -> str:
    text = _CONTROL_WHITESPACE_RE.sub(" ", value)
    max_chars = max(16, snippet_chars)
    lower_text = text.lower()
    marker_indexes = [
        lower_text.find(marker.lower())
        for marker in markers
        if lower_text.find(marker.lower()) >= 0
    ]
    first_match = min(marker_indexes) if marker_indexes else 0
    start = max(0, first_match - max_chars // 3)
    end = min(len(text), start + max_chars)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."
    return snippet


def _known_path_strategy(parts: Sequence[str | int], *, source_panther_ancestor: bool) -> tuple[str, str]:
    if len(parts) >= 3 and parts[:3] == ["local", "raw", "panther_logs"]:
        return (
            "repair_known_path_hook",
            "Repair the local.raw.panther_logs branch in _compact_local_diagnostics().",
        )
    if parts and parts[0] == "local_consensus":
        return (
            "repair_known_path_hook",
            "Repair the top-level local_consensus panther signal hook in _compact_local_diagnostics().",
        )
    if len(parts) >= 2 and parts[0] == "details" and parts[1] == "local_consensus":
        return (
            "repair_known_path_hook",
            "Repair the details.local_consensus hook in _compact_local_diagnostics().",
        )
    if len(parts) >= 2 and parts[0] == "metadata" and parts[1] == "local_consensus":
        return (
            "repair_known_path_hook",
            "Repair the metadata.local_consensus hook in _compact_local_diagnostics().",
        )
    if (
        len(parts) >= 4
        and parts[0] == "details"
        and parts[2] == "audit_diagnostics"
        and parts[3] == "panther_logs"
    ):
        return (
            "repair_known_path_hook",
            "Repair the details.*.audit_diagnostics.panther_logs hook in _compact_local_diagnostics().",
        )
    if "local_consensus" in parts or source_panther_ancestor:
        return (
            "generic_recursive_source_panther_compaction",
            (
                "Add a generic recursive output-only pass that compacts values under "
                "local_consensus signals where source == 'panther'."
            ),
        )
    if "panther_logs" in parts:
        return (
            "add_known_path_hook",
            "Add a narrow _compact_local_diagnostics() hook for this new panther_logs JSON path.",
        )
    return (
        "inspect_new_output_path",
        "Inspect this new JSON path and add the narrowest output-only compaction hook that covers it.",
    )


def _record_finding(
    findings: list[PantherLeakFinding],
    *,
    parts: Sequence[str | int],
    value: str,
    value_kind: str,
    source_panther_ancestor: bool,
    snippet_chars: int,
) -> None:
    marker_names = _matched_marker_names(value)
    if not marker_names:
        return
    strategy, hint = _known_path_strategy(parts, source_panther_ancestor=source_panther_ancestor)
    marker_literals = [
        marker
        for name, marker in PANTHER_LEAK_MARKERS
        if name in set(marker_names)
    ]
    findings.append(
        PantherLeakFinding(
            path=_format_json_path(parts),
            value_kind=value_kind,
            value_chars=len(value),
            value_bytes_utf8=len(value.encode("utf-8", errors="replace")),
            matched_markers=marker_names,
            snippet=_sanitized_snippet(value, markers=marker_literals, snippet_chars=snippet_chars),
            fix_strategy=strategy,
            fix_hint=hint,
        )
    )


def _walk_json(
    value: object,
    *,
    parts: Sequence[str | int],
    source_panther_ancestor: bool,
    findings: list[PantherLeakFinding],
    snippet_chars: int,
) -> None:
    if isinstance(value, Mapping):
        current_source_panther = source_panther_ancestor or value.get("source") == "panther"
        for key, item in value.items():
            key_text = str(key)
            key_parts = [*parts, key_text]
            _record_finding(
                findings,
                parts=key_parts,
                value=key_text,
                value_kind="key",
                source_panther_ancestor=current_source_panther,
                snippet_chars=snippet_chars,
            )
            _walk_json(
                item,
                parts=key_parts,
                source_panther_ancestor=current_source_panther,
                findings=findings,
                snippet_chars=snippet_chars,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_json(
                item,
                parts=[*parts, index],
                source_panther_ancestor=source_panther_ancestor,
                findings=findings,
                snippet_chars=snippet_chars,
            )
        return
    if isinstance(value, str):
        _record_finding(
            findings,
            parts=parts,
            value=value,
            value_kind="value",
            source_panther_ancestor=source_panther_ancestor,
            snippet_chars=snippet_chars,
        )


def _recommendation(findings: Sequence[PantherLeakFinding], *, output_mode: str) -> dict[str, Any]:
    if output_mode == "raw_opt_in":
        return {
            "strategy": "none_raw_opt_in_expected",
            "minimal_fix": "No default-output compaction fix is indicated when scanning --include-raw-local-diagnostics output.",
        }
    if not findings:
        return {
            "strategy": "none",
            "minimal_fix": "No raw Panther/setup leak markers were found.",
        }
    strategies = {finding.fix_strategy for finding in findings}
    if "generic_recursive_source_panther_compaction" in strategies:
        return {
            "strategy": "generic_recursive_source_panther_compaction",
            "minimal_fix": (
                "Add an output-only recursive compaction pass for any local_consensus "
                "signal where source == 'panther'; keep signed policy and evaluator verdict logic unchanged."
            ),
        }
    if "add_known_path_hook" in strategies or "inspect_new_output_path" in strategies:
        return {
            "strategy": "add_known_path_hook",
            "minimal_fix": (
                "Add the narrowest _compact_local_diagnostics() hook for the reported JSON path, "
                "then add a regression test for that path."
            ),
        }
    return {
        "strategy": "repair_known_path_hooks",
        "minimal_fix": (
            "Repair the existing _compact_local_diagnostics() Panther hooks for the reported known paths, "
            "then keep the current path-specific regression tests."
        ),
    }


def _finding_report(finding: PantherLeakFinding, *, output_mode: str) -> dict[str, Any]:
    report = finding.to_dict()
    if output_mode == "raw_opt_in":
        report["default_output_fix_strategy"] = report["fix_strategy"]
        report["default_output_fix_hint"] = report["fix_hint"]
        report["fix_strategy"] = "raw_opt_in_expected"
        report["fix_hint"] = (
            "No fix is needed for --include-raw-local-diagnostics output. "
            "Use default_output_fix_strategy only if this same path leaks in default JSON."
        )
    return report


def analyze_panther_json(
    payload: object,
    *,
    output_mode: str = "default",
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
) -> dict[str, Any]:
    if output_mode not in {"default", "raw_opt_in"}:
        raise ValueError("output_mode must be 'default' or 'raw_opt_in'.")
    findings: list[PantherLeakFinding] = []
    _walk_json(
        payload,
        parts=[],
        source_panther_ancestor=False,
        findings=findings,
        snippet_chars=snippet_chars,
    )
    leak_dicts = [_finding_report(finding, output_mode=output_mode) for finding in findings]
    return {
        "ok": output_mode == "raw_opt_in" or not findings,
        "output_mode": output_mode,
        "leak_count": len(findings),
        "leaks": leak_dicts,
        "recommendation": _recommendation(findings, output_mode=output_mode),
        "note": (
            "Panther/setup strings are administrator troubleshooting evidence only. "
            "They must not become verdict authority."
        ),
    }


def load_json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Developer-only debugger for raw Panther/setup strings in win11_release_guard JSON output."
    )
    parser.add_argument("json_file", type=Path, help="JSON file to scan.")
    parser.add_argument(
        "--mode",
        choices=("default", "raw-opt-in"),
        default="default",
        help="Whether the JSON came from default output or --include-raw-local-diagnostics output.",
    )
    parser.add_argument(
        "--snippet-chars",
        type=int,
        default=DEFAULT_SNIPPET_CHARS,
        help="Maximum characters to include in each sanitized snippet.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output_mode = "raw_opt_in" if args.mode == "raw-opt-in" else "default"
    try:
        payload = load_json_file(args.json_file)
        report = analyze_panther_json(
            payload,
            output_mode=output_mode,
            snippet_chars=args.snippet_chars,
        )
        report = {"input": str(args.json_file), **report}
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {
            "ok": False,
            "input": str(args.json_file),
            "output_mode": output_mode,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

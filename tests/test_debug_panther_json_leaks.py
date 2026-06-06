from __future__ import annotations

import json
from pathlib import Path

from tools import debug_panther_json_leaks as debugger


def _panther_consensus(raw_text: str) -> dict[str, object]:
    return {
        "signal_set": {
            "signals": [
                {
                    "source": "panther",
                    "name": "logs",
                    "value": {
                        r"C:\Windows\Panther\setupact.log": raw_text,
                    },
                    "kind": "audit",
                    "trust": "audit",
                }
            ]
        }
    }


def _raw_log_text() -> str:
    return (
        "2026-06-06 Info SetupPlatform.exe SERIALIZEVERBOSE "
        "Set boot command for $WINDOWS.~BT\n"
        "Update Boot Sector completed\n"
    ) * 20


def _single_leak(report: dict[str, object]) -> dict[str, object]:
    leaks = report["leaks"]
    assert isinstance(leaks, list)
    assert len(leaks) == 1
    leak = leaks[0]
    assert isinstance(leak, dict)
    return leak


def test_debugger_reports_details_local_consensus_leak_with_known_hook() -> None:
    payload = {
        "status": "COMPLIANT",
        "details": {
            "local_consensus": _panther_consensus(_raw_log_text()),
        },
    }

    report = debugger.analyze_panther_json(payload, output_mode="default", snippet_chars=64)
    leak = _single_leak(report)

    assert report["ok"] is False
    assert leak["path"] == (
        '$.details.local_consensus.signal_set.signals[0].value["C:\\\\Windows\\\\Panther\\\\setupact.log"]'
    )
    assert leak["value_kind"] == "value"
    assert leak["value_chars"] == len(_raw_log_text())
    assert leak["value_bytes_utf8"] == len(_raw_log_text().encode("utf-8"))
    assert set(leak["matched_markers"]) >= {
        "windows_bt",
        "setup_platform",
        "serialize_verbose",
        "set_boot_command",
        "update_boot_sector",
    }
    assert leak["fix_strategy"] == "repair_known_path_hook"
    assert "details.local_consensus" in leak["fix_hint"]
    assert report["recommendation"]["strategy"] == "repair_known_path_hooks"


def test_debugger_reports_metadata_local_consensus_leak_with_known_hook() -> None:
    payload = {
        "status": "COMPLIANT",
        "metadata": {
            "local_consensus": _panther_consensus(_raw_log_text()),
        },
    }

    report = debugger.analyze_panther_json(payload, output_mode="default")
    leak = _single_leak(report)

    assert report["ok"] is False
    assert leak["path"].startswith("$.metadata.local_consensus.signal_set.signals[0].value")
    assert leak["fix_strategy"] == "repair_known_path_hook"
    assert "metadata.local_consensus" in leak["fix_hint"]


def test_debugger_recommends_generic_pass_for_unknown_nested_local_consensus_copy() -> None:
    payload = {
        "status": "COMPLIANT",
        "future_debug": {
            "copied_payload": {
                "local_consensus": _panther_consensus(_raw_log_text()),
            }
        },
    }

    report = debugger.analyze_panther_json(payload, output_mode="default")
    leak = _single_leak(report)

    assert report["ok"] is False
    assert leak["path"].startswith(
        "$.future_debug.copied_payload.local_consensus.signal_set.signals[0].value"
    )
    assert leak["fix_strategy"] == "generic_recursive_source_panther_compaction"
    assert report["recommendation"]["strategy"] == "generic_recursive_source_panther_compaction"
    assert "source == 'panther'" in report["recommendation"]["minimal_fix"]


def test_debugger_distinguishes_raw_opt_in_output() -> None:
    payload = {
        "status": "COMPLIANT",
        "details": {
            "local_consensus": _panther_consensus(_raw_log_text()),
        },
    }

    report = debugger.analyze_panther_json(payload, output_mode="raw_opt_in")
    leak = _single_leak(report)

    assert report["ok"] is True
    assert report["output_mode"] == "raw_opt_in"
    assert report["leak_count"] == 1
    assert leak["fix_strategy"] == "raw_opt_in_expected"
    assert leak["default_output_fix_strategy"] == "repair_known_path_hook"
    assert report["recommendation"]["strategy"] == "none_raw_opt_in_expected"


def test_debugger_prints_bounded_sanitized_snippets_only(tmp_path: Path, capsys) -> None:
    huge_raw = "prefix\n" + ("SetupPlatform.exe SERIALIZEVERBOSE " * 200) + "suffix"
    payload = {"details": {"local_consensus": _panther_consensus(huge_raw)}}
    path = tmp_path / "out.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    code = debugger.main([str(path), "--snippet-chars", "48"])
    output = capsys.readouterr().out
    report = json.loads(output)
    leak = report["leaks"][0]

    assert code == 1
    assert leak["value_chars"] == len(huge_raw)
    assert "\n" not in leak["snippet"]
    assert len(leak["snippet"]) <= 54
    assert huge_raw not in output


def test_debugger_has_no_default_leak_when_markers_are_absent() -> None:
    report = debugger.analyze_panther_json(
        {"details": {"local_consensus": _panther_consensus("bounded metadata only")}},
        output_mode="default",
    )

    assert report["ok"] is True
    assert report["leak_count"] == 0
    assert report["recommendation"]["strategy"] == "none"

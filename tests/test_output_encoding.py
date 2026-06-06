from __future__ import annotations

import json

from win11_release_guard import __main__ as cli
from win11_release_guard.diagnostic_tail import PANTHER_PRIVACY_NOTICE
from win11_release_guard.models import EvaluationResult, EvaluationStatus, LocalConsensus, LocalSignal, LocalSignalSet, LocalWindowsState


GERMAN_SUMMARY = "für Vorschauupdate bösartiger"


def _result_with_german_wua_history() -> EvaluationResult:
    history = [
        {
            "title": f"2026-05 Vorschauupdate für Windows 11 Version 25H2 (KB50895{i:02d}) bösartiger",
            "classification": "quality_preview" if i < 5 else "defender_definition",
            "kb_ids": [f"KB50895{i:02d}"],
            "result_code": 2,
        }
        for i in range(50)
    ]
    return EvaluationResult(
        status=EvaluationStatus.COMPLIANT,
        summary=GERMAN_SUMMARY,
        action="No action required.",
        wua_secondary={
            "available": True,
            "service_enabled": True,
            "target_feature_update_offered": False,
            "target_release_in_history": False,
            "available_updates": [
                {
                    "title": "Security Intelligence-Update für bösartiger Software - KB2267602",
                    "classification": "defender_definition",
                }
            ],
            "relevant_os_updates": [
                {
                    "title": "Feature Update to Windows 11, version 25H2",
                    "classification": "feature_update",
                }
            ],
            "history": history,
            "noise_counts": {"defender_definition": 45},
            "warnings": ["Vorschauupdate für Test"],
            "errors": [],
        },
        target_feature_update_offer_expected=True,
        target_feature_update_offered=False,
    )


def test_cli_stdout_json_parses_and_is_ascii_safe_by_default(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_german_wua_history())

    code = cli.main(["--json"])

    text = capsys.readouterr().out
    payload = json.loads(text)
    assert code == 0
    assert payload["summary"] == GERMAN_SUMMARY
    assert "\\u00fc" in text
    assert "für" not in text


def test_cli_unicode_stdout_is_readable_utf8(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_german_wua_history())

    code = cli.main(["--json", "--unicode"])

    text = capsys.readouterr().out
    payload = json.loads(text)
    assert code == 0
    assert payload["summary"] == GERMAN_SUMMARY
    assert "für" in text
    assert "Vorschauupdate" in text
    assert "bösartiger" in text


def test_cli_output_file_writes_utf8_and_round_trips_german(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_german_wua_history())
    output = tmp_path / "release-check.json"

    code = cli.main(["--json", "--unicode", "--output", str(output)])

    raw = output.read_bytes()
    text = raw.decode("utf-8")
    payload = json.loads(text)
    assert code == 0
    assert payload["summary"] == GERMAN_SUMMARY
    assert b"f\xc3\xbcr" in raw
    assert text.endswith("\n")


def test_json_pretty_is_valid_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_german_wua_history())

    code = cli.main(["--json-pretty"])

    text = capsys.readouterr().out
    assert code == 0
    assert json.loads(text)["status"] == EvaluationStatus.COMPLIANT.value
    assert "\n  " in text


def test_default_output_compacts_wua_history(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_german_wua_history())

    code = cli.main(["--json"])

    payload = json.loads(capsys.readouterr().out)
    wua = payload["wua_secondary"]
    assert code == 0
    assert "history" not in wua
    assert len(wua["latest_relevant_history"]) == 3
    assert wua["counts_by_category"]["history_total"] == 50
    assert wua["raw_output_truncated"] is True


def test_include_raw_wua_history_keeps_full_bounded_history(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_german_wua_history())

    code = cli.main(["--json", "--include-raw-wua-history"])

    payload = json.loads(capsys.readouterr().out)
    wua = payload["wua_secondary"]
    assert code == 0
    assert len(wua["history"]) == 50
    assert wua["raw_output_truncated"] is False


def _result_with_panther_log_tail() -> EvaluationResult:
    panther_text = "2026-05-12 Info Set NewOS boot entry as the default boot entry\n" * 20
    panther_consensus = LocalConsensus(
        display_os_name="Windows 11 Pro",
        signal_set=LocalSignalSet(
            signals=(
                LocalSignal(
                    source="panther",
                    name="logs",
                    value={r"C:\Windows\Panther\setupact.log": panther_text},
                    kind="audit",
                ),
            )
        ),
    )
    return EvaluationResult(
        status=EvaluationStatus.COMPLIANT,
        summary="Compliant",
        action="No action required.",
        local=LocalWindowsState(
            current_build=26200,
            full_build="26200.8524",
            raw={"panther_logs": {r"C:\Windows\Panther\setupact.log": panther_text}},
        ),
        local_consensus=panther_consensus,
        details={
            "local_consensus": panther_consensus.to_dict(),
            "silent_feature_update_missing": {
                "audit_diagnostics": {
                    "panther_logs": {
                        "errors": ["Panther log read failed: access denied"],
                        "logs": [
                            {
                                "path": r"C:\$Windows.~BT\Sources\Panther\setupact.log",
                                "tail_bytes": len(panther_text),
                                "content": panther_text,
                                "evidence": [
                                    {
                                        "kind": "setup_failure",
                                        "line_number": 7,
                                        "line": "2026-05-12 Error SetupPlatform.exe failed",
                                        "source_path": r"C:\$Windows.~BT\Sources\Panther\setupact.log",
                                    }
                                ],
                            }
                        ]
                    }
                }
            }
        },
        metadata={"local_consensus": panther_consensus.to_dict()},
    )


def _result_with_panther_privacy_marker() -> EvaluationResult:
    path = r"C:\Windows\Panther\setupact.log"
    sensitive_text = "Password: never-print-this\nSetupPlatform.exe failed\n"
    privacy_findings = [
        {
            "category": "credential",
            "marker": "password",
            "line_number": 1,
        }
    ]
    privacy_summary = {
        "privacy_scan_completed": True,
        "privacy_findings_count": 1,
        "notice": PANTHER_PRIVACY_NOTICE,
        "privacy_findings": [
            {
                "category": "credential",
                "marker": "password",
                "line_number": 1,
                "path": path,
            }
        ],
    }
    panther_entry = {
        "content": sensitive_text,
        "file_size_bytes": len(sensitive_text),
        "tail_start_offset": 0,
        "tail_truncated": False,
        "tail_bytes": len(sensitive_text),
        "encoding_detected": "utf-8",
        "decode_errors_replaced": False,
        "privacy_scan_completed": True,
        "privacy_findings_count": 1,
        "privacy_findings": privacy_findings,
    }
    panther_consensus = LocalConsensus(
        display_os_name="Windows 11 Pro",
        signal_set=LocalSignalSet(
            signals=(
                LocalSignal(
                    source="panther",
                    name="logs",
                    value={path: panther_entry},
                    kind="audit",
                ),
            )
        ),
    )
    return EvaluationResult(
        status=EvaluationStatus.COMPLIANT,
        summary="Compliant",
        action="No action required.",
        local=LocalWindowsState(
            current_build=26200,
            full_build="26200.8524",
            raw={
                "panther_logs": {path: panther_entry},
                "panther_privacy_findings": privacy_summary,
            },
        ),
        local_consensus=panther_consensus,
        details={
            "silent_feature_update_missing": {
                "audit_diagnostics": {
                    "panther_logs": {
                        "logs": [
                            {
                                "path": path,
                                "content": sensitive_text,
                                "privacy_scan_completed": True,
                                "privacy_findings_count": 1,
                                "privacy_findings": privacy_findings,
                            }
                        ],
                        "privacy_findings": privacy_summary,
                        "errors": [],
                    }
                }
            }
        },
    )


def test_default_json_compacts_local_panther_log_tails(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_panther_log_tail())

    code = cli.main(["--json-pretty"])

    text = capsys.readouterr().out
    payload = json.loads(text)
    assert code == 0
    assert "Set NewOS boot entry" not in text
    local_log = payload["local"]["raw"]["panther_logs"][r"C:\Windows\Panther\setupact.log"]
    assert local_log["content_omitted"] is True
    assert local_log["content_chars"] > 0
    signal_value = payload["local_consensus"]["signal_set"]["signals"][0]["value"]
    assert signal_value[r"C:\Windows\Panther\setupact.log"]["content_omitted"] is True
    details_signal_value = payload["details"]["local_consensus"]["signal_set"]["signals"][0]["value"]
    assert details_signal_value[r"C:\Windows\Panther\setupact.log"]["content_omitted"] is True
    metadata_signal_value = payload["metadata"]["local_consensus"]["signal_set"]["signals"][0]["value"]
    assert metadata_signal_value[r"C:\Windows\Panther\setupact.log"]["content_omitted"] is True
    audit_panther = payload["details"]["silent_feature_update_missing"]["audit_diagnostics"]["panther_logs"]
    assert audit_panther["errors"] == ["Panther log read failed: access denied"]
    audit_log = audit_panther["logs"][0]
    assert "path" not in audit_log
    assert audit_log["path_omitted"] is True
    assert "content" not in audit_log
    assert audit_log["content_omitted"] is True
    evidence = audit_log["evidence"][0]
    assert evidence["kind"] == "setup_failure"
    assert evidence["line_number"] == 7
    assert "line" not in evidence
    assert evidence["line_omitted"] is True
    assert "source_path" not in evidence
    assert evidence["source_path_omitted"] is True


def test_default_json_keeps_panther_privacy_metadata_without_values(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_panther_privacy_marker())

    code = cli.main(["--json-pretty"])

    text = capsys.readouterr().out
    payload = json.loads(text)
    local_log = payload["local"]["raw"]["panther_logs"][r"C:\Windows\Panther\setupact.log"]
    local_privacy_summary = payload["local"]["raw"]["panther_privacy_findings"]
    audit_log = payload["details"]["silent_feature_update_missing"]["audit_diagnostics"]["panther_logs"]["logs"][0]
    audit_privacy_summary = payload["details"]["silent_feature_update_missing"]["audit_diagnostics"]["panther_logs"]["privacy_findings"]
    assert code == 0
    assert "never-print-this" not in text
    assert local_log["content_omitted"] is True
    assert local_log["privacy_scan_completed"] is True
    assert local_log["privacy_findings_count"] == 1
    assert local_log["privacy_findings"][0]["marker"] == "password"
    assert audit_log["content_omitted"] is True
    assert audit_log["privacy_scan_completed"] is True
    assert audit_log["privacy_findings"][0]["category"] == "credential"
    assert local_privacy_summary["notice"] == PANTHER_PRIVACY_NOTICE
    assert local_privacy_summary["privacy_findings"][0]["path"] == r"C:\Windows\Panther\setupact.log"
    assert audit_privacy_summary["notice"] == PANTHER_PRIVACY_NOTICE


def test_include_raw_local_diagnostics_keeps_panther_log_tails(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_panther_log_tail())

    code = cli.main(["--json", "--include-raw-local-diagnostics"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "Set NewOS boot entry" in payload["local"]["raw"]["panther_logs"][r"C:\Windows\Panther\setupact.log"]
    assert "Set NewOS boot entry" in payload["details"]["local_consensus"]["signal_set"]["signals"][0]["value"][r"C:\Windows\Panther\setupact.log"]
    assert "Set NewOS boot entry" in payload["metadata"]["local_consensus"]["signal_set"]["signals"][0]["value"][r"C:\Windows\Panther\setupact.log"]
    audit_panther = payload["details"]["silent_feature_update_missing"]["audit_diagnostics"]["panther_logs"]
    audit_log = audit_panther["logs"][0]
    assert audit_panther["errors"] == ["Panther log read failed: access denied"]
    assert audit_log["path"] == r"C:\$Windows.~BT\Sources\Panther\setupact.log"
    assert "Set NewOS boot entry" in audit_log["content"]
    assert "SetupPlatform.exe failed" in audit_log["evidence"][0]["line"]
    assert audit_log["evidence"][0]["source_path"] == r"C:\$Windows.~BT\Sources\Panther\setupact.log"


def test_include_raw_local_diagnostics_keeps_panther_privacy_raw_values(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: _result_with_panther_privacy_marker())

    code = cli.main(["--json", "--include-raw-local-diagnostics"])

    payload = json.loads(capsys.readouterr().out)
    local_log = payload["local"]["raw"]["panther_logs"][r"C:\Windows\Panther\setupact.log"]
    audit_log = payload["details"]["silent_feature_update_missing"]["audit_diagnostics"]["panther_logs"]["logs"][0]
    assert code == 0
    assert "never-print-this" in local_log["content"]
    assert "never-print-this" in audit_log["content"]
    assert local_log["privacy_findings"][0]["marker"] == "password"


def test_local_diagnostic_compaction_does_not_mutate_result():
    result = _result_with_panther_log_tail()

    compact_payload = cli._output_payload(
        result,
        include_raw_wua_history=False,
        include_raw_local_diagnostics=False,
    )
    raw_payload = cli._output_payload(
        result,
        include_raw_wua_history=False,
        include_raw_local_diagnostics=True,
    )

    raw_log = raw_payload["local"]["raw"]["panther_logs"][r"C:\Windows\Panther\setupact.log"]
    result_log = result.details["silent_feature_update_missing"]["audit_diagnostics"]["panther_logs"]["logs"][0]
    assert compact_payload["local"]["raw"]["panther_logs"][r"C:\Windows\Panther\setupact.log"]["content_omitted"] is True
    assert "Set NewOS boot entry" in raw_log
    assert "Set NewOS boot entry" in result_log["content"]


def test_default_json_compaction_keeps_non_panther_local_signals(monkeypatch, capsys):
    def result_with_non_panther_signal() -> EvaluationResult:
        return EvaluationResult(
            status=EvaluationStatus.COMPLIANT,
            summary="Compliant",
            action="No action required.",
            local_consensus=LocalConsensus(
                display_os_name="Windows 11 Pro",
                signal_set=LocalSignalSet(
                    signals=(
                        LocalSignal(
                            source="registry",
                            name="DiagnosticPath",
                            value=r"C:\Windows\Panther\setupact.log",
                            kind="audit",
                        ),
                    )
                ),
            ),
        )

    monkeypatch.setattr(cli, "check_current_system", lambda config: result_with_non_panther_signal())

    code = cli.main(["--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    signal_value = payload["local_consensus"]["signal_set"]["signals"][0]["value"]
    assert signal_value == r"C:\Windows\Panther\setupact.log"


def test_default_json_compacts_future_nested_panther_local_consensus_copy():
    result = _result_with_panther_log_tail()
    result.details["future_payload"] = {
        "nested": {
            "local_consensus": result.local_consensus.to_dict(),
        }
    }

    payload = cli._output_payload(
        result,
        include_raw_wua_history=False,
        include_raw_local_diagnostics=False,
    )
    text = json.dumps(payload)

    assert "Set NewOS boot entry" not in text
    signal_value = payload["details"]["future_payload"]["nested"]["local_consensus"]["signal_set"]["signals"][0]["value"]
    assert signal_value[r"C:\Windows\Panther\setupact.log"]["content_omitted"] is True


def test_recursive_panther_compaction_keeps_non_panther_future_signal_value():
    raw_value = r"C:\Windows\Panther\setupact.log SetupPlatform.exe $WINDOWS.~BT"
    result = EvaluationResult(
        status=EvaluationStatus.COMPLIANT,
        summary="Compliant",
        action="No action required.",
        details={
            "future_payload": {
                "nested": {
                    "local_consensus": {
                        "signal_set": {
                            "signals": [
                                {
                                    "source": "registry",
                                    "name": "DiagnosticPath",
                                    "value": raw_value,
                                    "kind": "audit",
                                }
                            ]
                        }
                    }
                }
            }
        },
    )

    payload = cli._output_payload(
        result,
        include_raw_wua_history=False,
        include_raw_local_diagnostics=False,
    )

    signal_value = payload["details"]["future_payload"]["nested"]["local_consensus"]["signal_set"]["signals"][0]["value"]
    assert signal_value == raw_value

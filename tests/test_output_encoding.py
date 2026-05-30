from __future__ import annotations

import json

from win11_release_guard import __main__ as cli
from win11_release_guard.models import EvaluationResult, EvaluationStatus


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

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

from tools import live_panther_json_regression as harness


def _sane_payload() -> dict[str, object]:
    return {
        "status": "COMPLIANT",
        "source_status": "REMOTE_POLICY_OK",
        "policy_signature_status": "valid",
        "strict_production": True,
        "installed_release": "25H2",
        "target": {
            "version": "25H2",
            "build_family": 26200,
        },
    }


def _sane_payload_with_compaction() -> dict[str, object]:
    payload = _sane_payload()
    payload["local"] = {
        "raw": {
            "panther_logs": {
                r"C:\Windows\Panther\setupact.log": {
                    "content_omitted": True,
                    "content_chars": 123,
                    "content_bytes_utf8": 123,
                }
            }
        }
    }
    return payload


def _sane_payload_with_raw_panther_content(
    content: str = "Generic Windows Setup diagnostic tail.",
    *,
    base: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = deepcopy(base if base is not None else _sane_payload())
    payload["local"] = {
        "raw": {
            "panther_logs": {
                r"C:\Windows\Panther\setupact.log": {
                    "content": content,
                    "tail_bytes": len(content.encode("utf-8")),
                }
            }
        }
    }
    return payload


def _check_map(checks: list[harness.HarnessCheck]) -> dict[str, harness.HarnessCheck]:
    return {check.name: check for check in checks}


def test_validate_live_outputs_accepts_compact_default_and_raw_opt_in() -> None:
    default_text = '"content_omitted": true, "content_chars": 12, "content_bytes_utf8": 12'
    raw_text = " ".join(harness.RAW_PANTHER_STRINGS)

    checks = harness.validate_live_outputs(
        default_text=default_text,
        default_payload=_sane_payload_with_compaction(),
        raw_text=raw_text,
        raw_payload=_sane_payload_with_raw_panther_content(raw_text),
    )

    assert all(check.ok for check in checks)


def test_validate_live_outputs_accepts_raw_opt_in_without_exact_marker_strings() -> None:
    default_text = '"content_omitted": true, "content_chars": 12, "content_bytes_utf8": 12'
    raw_text = "Generic Windows Setup diagnostic tail without known marker strings."

    checks = _check_map(
        harness.validate_live_outputs(
            default_text=default_text,
            default_payload=_sane_payload_with_compaction(),
            raw_text=raw_text,
            raw_payload=_sane_payload_with_raw_panther_content(raw_text),
        )
    )

    assert all(check.ok for check in checks.values())
    assert checks["raw_opt_in_panther_content_present"].data["known_marker_counts"] == {
        marker: 0 for marker in harness.RAW_PANTHER_STRINGS
    }


def test_validate_live_outputs_accepts_no_panther_source_by_default() -> None:
    default_payload = _sane_payload()
    raw_payload = _sane_payload()

    checks = _check_map(
        harness.validate_live_outputs(
            default_text=json.dumps(default_payload),
            default_payload=default_payload,
            raw_text=json.dumps(raw_payload),
            raw_payload=raw_payload,
        )
    )

    assert all(check.ok for check in checks.values())
    assert checks["panther_source_status"].data["status"] == "no_panther_source_present"
    assert checks["panther_source_status"].data["no_panther_source_present"] is True
    assert checks["default_compact_markers_present"].data["required"] is False
    assert checks["default_compact_marker_objects_valid"].data["required"] is False
    assert checks["raw_opt_in_panther_content_present"].data["required"] is False


def test_validate_live_outputs_ignores_non_panther_compaction_markers_for_source_detection() -> None:
    default_payload = _sane_payload()
    default_payload["other_diagnostics"] = {
        "content_omitted": True,
        "content_chars": 123,
        "content_bytes_utf8": 123,
    }
    raw_payload = _sane_payload()

    checks = _check_map(
        harness.validate_live_outputs(
            default_text=json.dumps(default_payload),
            default_payload=default_payload,
            raw_text=json.dumps(raw_payload),
            raw_payload=raw_payload,
        )
    )

    assert all(check.ok for check in checks.values())
    assert checks["panther_source_status"].data["status"] == "no_panther_source_present"
    assert checks["panther_source_status"].data["default_compaction_marker_objects"] == 0
    assert checks["raw_opt_in_panther_content_present"].data["required"] is False


def test_validate_live_outputs_rejects_raw_setup_string_in_default_json() -> None:
    default_text = (
        '"content_omitted": true, "content_chars": 12, "content_bytes_utf8": 12 '
        "SetupPlatform.exe"
    )
    raw_text = " ".join(harness.RAW_PANTHER_STRINGS)

    checks = _check_map(
        harness.validate_live_outputs(
            default_text=default_text,
            default_payload=_sane_payload_with_compaction(),
            raw_text=raw_text,
            raw_payload=_sane_payload_with_raw_panther_content(raw_text),
        )
    )

    assert checks["default_raw_strings_absent"].ok is False
    assert checks["raw_strings_only_in_opt_in"].ok is False


def test_validate_live_outputs_rejects_missing_raw_opt_in_when_default_was_compacted() -> None:
    default_text = '"content_omitted": true, "content_chars": 12, "content_bytes_utf8": 12'
    raw_payload = _sane_payload()

    checks = _check_map(
        harness.validate_live_outputs(
            default_text=default_text,
            default_payload=_sane_payload_with_compaction(),
            raw_text=json.dumps(raw_payload),
            raw_payload=raw_payload,
        )
    )

    assert checks["panther_source_status"].data["status"] == "default_compaction_without_raw_opt_in"
    assert checks["raw_opt_in_panther_content_present"].ok is False
    assert checks["raw_opt_in_panther_content_present"].data["required"] is True


def test_validate_live_outputs_rejects_structural_panther_content_in_default_json() -> None:
    payload = _sane_payload_with_compaction()
    payload["metadata"] = {
        "local_consensus": {
            "signal_set": {
                "signals": [
                    {
                        "source": "panther",
                        "value": {
                            "content": "Raw setup diagnostic content without known marker strings."
                        },
                    }
                ]
            }
        }
    }

    checks = _check_map(
        harness.validate_live_outputs(
            default_text=json.dumps(payload),
            default_payload=payload,
            raw_text="Generic Windows Setup diagnostic tail.",
            raw_payload=_sane_payload_with_raw_panther_content(),
        )
    )

    assert checks["default_raw_panther_content_absent"].ok is False
    assert checks["default_raw_strings_absent"].ok is True


def test_validate_live_outputs_rejects_missing_compact_markers() -> None:
    checks = _check_map(
        harness.validate_live_outputs(
            default_text="{}",
            default_payload=_sane_payload(),
            raw_text=" ".join(harness.RAW_PANTHER_STRINGS),
            raw_payload=_sane_payload_with_raw_panther_content(" ".join(harness.RAW_PANTHER_STRINGS)),
        )
    )

    assert checks["default_compact_markers_present"].ok is False
    assert checks["default_compact_marker_objects_valid"].ok is False


def test_validate_live_outputs_rejects_text_only_compact_markers() -> None:
    checks = _check_map(
        harness.validate_live_outputs(
            default_text='"content_omitted": true, "content_chars": 12, "content_bytes_utf8": 12',
            default_payload=_sane_payload(),
            raw_text=" ".join(harness.RAW_PANTHER_STRINGS),
            raw_payload=_sane_payload_with_raw_panther_content(" ".join(harness.RAW_PANTHER_STRINGS)),
        )
    )

    assert checks["default_compact_markers_present"].ok is True
    assert checks["default_compact_marker_objects_valid"].ok is False


def test_validate_live_outputs_rejects_malformed_compact_marker_object() -> None:
    payload = _sane_payload()
    payload["local"] = {
        "raw": {
            "panther_logs": {
                r"C:\Windows\Panther\setupact.log": {
                    "content_omitted": True,
                    "content_chars": "123",
                    "content_bytes_utf8": True,
                }
            }
        }
    }

    checks = _check_map(
        harness.validate_live_outputs(
            default_text='"content_omitted": true, "content_chars": "123", "content_bytes_utf8": true',
            default_payload=payload,
            raw_text=" ".join(harness.RAW_PANTHER_STRINGS),
            raw_payload=_sane_payload_with_raw_panther_content(" ".join(harness.RAW_PANTHER_STRINGS)),
        )
    )

    assert checks["default_compact_marker_objects_valid"].ok is False


def test_validate_live_outputs_rejects_degraded_verdict_fields() -> None:
    payload = _sane_payload()
    payload["source_status"] = "USING_BUNDLED_POLICY"
    payload["strict_production"] = False
    payload["target"] = {"version": None, "build_family": None}

    checks = _check_map(
        harness.validate_live_outputs(
            default_text='"content_omitted": true, "content_chars": 12, "content_bytes_utf8": 12',
            default_payload={**payload, "local": _sane_payload_with_compaction()["local"]},
            raw_text=" ".join(harness.RAW_PANTHER_STRINGS),
            raw_payload=_sane_payload_with_raw_panther_content(
                " ".join(harness.RAW_PANTHER_STRINGS),
                base=payload,
            ),
        )
    )

    assert checks["verdict_fields_sane"].ok is False


def test_cmd_redirection_command_uses_strict_production_env_and_raw_flag(tmp_path: Path) -> None:
    default_command = harness._cmd_redirection_command(
        python_executable="python.exe",
        output_path=tmp_path / "out.json",
        include_raw_local_diagnostics=False,
    )
    raw_command = harness._cmd_redirection_command(
        python_executable="python.exe",
        output_path=tmp_path / "out.raw.json",
        include_raw_local_diagnostics=True,
    )

    assert "--json-pretty" in default_command
    assert "--include-raw-local-diagnostics" not in default_command
    assert "--include-raw-local-diagnostics" in raw_command
    assert ">" in default_command
    assert default_command.startswith('call "python.exe"')


def test_run_cmd_redirection_sets_strict_production_env_and_uses_cmd(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return harness.subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)

    command, proc = harness._run_cmd_redirection(
        root=tmp_path,
        python_executable="C:\\Program Files\\Python\\python.exe",
        output_path=tmp_path / "out.json",
        include_raw_local_diagnostics=False,
    )

    assert proc.returncode == 0
    assert calls[0][0] == f"cmd.exe /d /c {command}"
    assert calls[0][1]["env"]["WIN11_RELEASE_GUARD_STRICT_PRODUCTION"] == "1"
    assert ">" in command
    assert command.startswith('call "C:\\Program Files\\Python\\python.exe"')


def test_run_cmd_redirection_reports_timeout(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"], output="partial")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)

    command, proc = harness._run_cmd_redirection(
        root=tmp_path,
        python_executable="python.exe",
        output_path=tmp_path / "out.json",
        include_raw_local_diagnostics=False,
        timeout_seconds=3,
    )

    assert command.startswith('call "python.exe"')
    assert proc.returncode == harness.PROCESS_TIMEOUT_RETURNCODE
    assert "Timed out after 3 seconds." in proc.stderr
    assert proc.stdout == "partial"


def test_validate_json_tool_reports_start_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("missing-python")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)

    proc = harness._validate_json_tool(python_executable="missing-python.exe", path=tmp_path / "out.json")

    assert proc.returncode == harness.PROCESS_START_RETURNCODE
    assert "FileNotFoundError" in proc.stderr


def test_run_harness_removes_stale_outputs_before_running(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness.os, "name", "nt")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "out.json").write_text(json.dumps(_sane_payload_with_compaction()), encoding="utf-8")
    (output_dir / "out.raw.json").write_text(json.dumps(_sane_payload()), encoding="utf-8")

    def fake_run_cmd_redirection(**kwargs):
        return "cmd", subprocess.CompletedProcess(args="cmd", returncode=0, stdout="", stderr="")

    monkeypatch.setattr(harness, "_run_cmd_redirection", fake_run_cmd_redirection)

    report = harness.run_harness(output_dir=output_dir, python_executable="python", root=tmp_path)

    assert report["ok"] is False
    assert report["error"] == "One or more JSON output files were not created by the live run."
    assert report["files"]["default_json"]["exists"] is False
    assert report["files"]["raw_json"]["exists"] is False


def test_run_harness_reports_json_object_load_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness.os, "name", "nt")
    output_dir = tmp_path / "output"

    def fake_run_cmd_redirection(**kwargs):
        path = kwargs["output_path"]
        path.write_text("[]", encoding="utf-8")
        return "cmd", subprocess.CompletedProcess(args="cmd", returncode=0, stdout="", stderr="")

    def fake_validate_json_tool(**kwargs):
        return subprocess.CompletedProcess(args="json.tool", returncode=0, stdout="", stderr="")

    monkeypatch.setattr(harness, "_run_cmd_redirection", fake_run_cmd_redirection)
    monkeypatch.setattr(harness, "_validate_json_tool", fake_validate_json_tool)

    report = harness.run_harness(output_dir=output_dir, python_executable="python", root=tmp_path)

    assert report["ok"] is False
    assert report["error"] == "JSON output could not be loaded as a UTF-8 JSON object."
    assert "did not contain a JSON object" in report["exception"]


def test_run_harness_reports_no_panther_source_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness.os, "name", "nt")
    output_dir = tmp_path / "output"

    def fake_run_cmd_redirection(**kwargs):
        path = kwargs["output_path"]
        path.write_text(json.dumps(_sane_payload()), encoding="utf-8")
        return "cmd", subprocess.CompletedProcess(args="cmd", returncode=0, stdout="", stderr="")

    def fake_validate_json_tool(**kwargs):
        return subprocess.CompletedProcess(args="json.tool", returncode=0, stdout="", stderr="")

    monkeypatch.setattr(harness, "_run_cmd_redirection", fake_run_cmd_redirection)
    monkeypatch.setattr(harness, "_validate_json_tool", fake_validate_json_tool)

    report = harness.run_harness(output_dir=output_dir, python_executable="python", root=tmp_path)

    assert report["ok"] is True
    assert report["panther_source_status"]["status"] == "no_panther_source_present"


def test_run_harness_reports_stale_output_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness.os, "name", "nt")
    output_dir = tmp_path / "output"
    (output_dir / "out.json").mkdir(parents=True)

    report = harness.run_harness(output_dir=output_dir, python_executable="python", root=tmp_path)

    assert report["ok"] is False
    assert report["error"] == "Could not remove stale generated output before the live run."
    assert "default_json" in report["stale_output_errors"]


def test_run_harness_reports_non_windows_without_running(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness.os, "name", "posix")

    report = harness.run_harness(
        output_dir=tmp_path,
        python_executable="python",
        root=tmp_path,
    )

    assert report["ok"] is False
    assert "requires Windows" in str(report["error"])


def test_main_reports_report_write_failure(monkeypatch, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "output-file"
    output_path.write_text("", encoding="utf-8")

    def fake_run_harness(**kwargs):
        return {
            "ok": False,
            "output_dir": str(output_path),
            "error": "forced failure",
        }

    monkeypatch.setattr(harness, "run_harness", fake_run_harness)

    code = harness.main(["--output-dir", str(output_path)])

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert code == 1
    assert report["ok"] is False
    assert "report_write_error" in report

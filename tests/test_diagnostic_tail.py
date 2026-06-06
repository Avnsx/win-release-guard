import json

from win11_release_guard.diagnostic_tail import (
    read_diagnostic_tail,
    summarize_privacy_marker_entries,
    summarize_privacy_markers,
)


def test_read_diagnostic_tail_decodes_utf16le_bom(tmp_path):
    log = tmp_path / "setupact.log"
    text = "SetupPlatform.exe Set boot command\r\n"
    log.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))

    tail = read_diagnostic_tail(log, max_bytes=4096)

    assert tail.content == text
    assert tail.encoding_detected == "utf-16le-bom"
    assert tail.decode_errors_replaced is False
    assert tail.file_size_bytes == log.stat().st_size
    assert tail.tail_start_offset == 0
    assert tail.tail_truncated is False


def test_read_diagnostic_tail_decodes_utf8_bom(tmp_path):
    log = tmp_path / "setupact.log"
    text = "SetupPlatform.exe UTF-8 BOM\n"
    log.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

    tail = read_diagnostic_tail(log, max_bytes=4096)

    assert tail.content == text
    assert tail.encoding_detected == "utf-8-bom"
    assert tail.decode_errors_replaced is False


def test_read_diagnostic_tail_decodes_utf16be_bom(tmp_path):
    log = tmp_path / "setupact.log"
    text = "SetupPlatform.exe UTF-16BE BOM\n"
    log.write_bytes(b"\xfe\xff" + text.encode("utf-16-be"))

    tail = read_diagnostic_tail(log, max_bytes=4096)

    assert tail.content == text
    assert tail.encoding_detected == "utf-16be-bom"
    assert tail.decode_errors_replaced is False


def test_read_diagnostic_tail_uses_utf16le_nul_heuristic(tmp_path):
    log = tmp_path / "setupact.log"
    text = "SetupPlatform.exe heuristic\n"
    log.write_bytes(text.encode("utf-16-le"))

    tail = read_diagnostic_tail(log, max_bytes=4096)

    assert tail.content == text
    assert tail.encoding_detected == "utf-16le-heuristic"
    assert tail.decode_errors_replaced is False


def test_read_diagnostic_tail_aligns_bomless_utf16le_mid_file_tail(tmp_path):
    log = tmp_path / "setupact.log"
    prefix = "A" * 40
    text = "SetupPlatform.exe tail \u00fc\n"
    encoded_text = text.encode("utf-16-le")
    log.write_bytes(prefix.encode("utf-16-le") + encoded_text)

    tail = read_diagnostic_tail(log, max_bytes=len(encoded_text) - 1)

    assert tail.content == text
    assert tail.tail_start_offset == len(prefix.encode("utf-16-le"))
    assert tail.tail_start_offset % 2 == 0
    assert tail.tail_bytes == len(encoded_text)
    assert tail.tail_truncated is True
    assert tail.encoding_detected == "utf-16le-heuristic"
    assert tail.decode_errors_replaced is False


def test_read_diagnostic_tail_aligns_bomless_utf16be_mid_file_tail(tmp_path):
    log = tmp_path / "setuperr.log"
    prefix = "B" * 40
    text = "SetupPlatform.exe BE tail \u00fc\n"
    encoded_text = text.encode("utf-16-be")
    log.write_bytes(prefix.encode("utf-16-be") + encoded_text)

    tail = read_diagnostic_tail(log, max_bytes=len(encoded_text) - 1)

    assert tail.content == text
    assert tail.tail_start_offset == len(prefix.encode("utf-16-be"))
    assert tail.tail_start_offset % 2 == 0
    assert tail.tail_bytes == len(encoded_text)
    assert tail.tail_truncated is True
    assert tail.encoding_detected == "utf-16be-heuristic"
    assert tail.decode_errors_replaced is False


def test_read_diagnostic_tail_records_bomless_utf16le_decode_replacement(tmp_path):
    log = tmp_path / "setuperr.log"
    text = "SetupPlatform.exe after invalid surrogate\n"
    log.write_bytes(
        "prefix\n".encode("utf-16-le")
        + b"\x00\xd8"
        + text.encode("utf-16-le")
    )

    tail = read_diagnostic_tail(log, max_bytes=4096)

    assert "SetupPlatform.exe" in tail.content
    assert "\ufffd" in tail.content
    assert tail.encoding_detected == "utf-16le-heuristic"
    assert tail.decode_errors_replaced is True


def test_read_diagnostic_tail_records_invalid_byte_replacement(tmp_path):
    log = tmp_path / "setuperr.log"
    log.write_bytes(b"SetupPlatform.exe invalid byte: \xff\n")

    tail = read_diagnostic_tail(log, max_bytes=4096)

    assert "SetupPlatform.exe" in tail.content
    assert "\ufffd" in tail.content
    assert tail.encoding_detected == "utf-8"
    assert tail.decode_errors_replaced is True


def test_read_diagnostic_tail_records_huge_tail_metadata(tmp_path):
    log = tmp_path / "setupact.log"
    log.write_bytes(b"a" * 128 + b"TAIL")

    tail = read_diagnostic_tail(log, max_bytes=16)

    assert tail.content.endswith("TAIL")
    assert tail.file_size_bytes == 132
    assert tail.tail_start_offset == 116
    assert tail.tail_truncated is True
    assert tail.tail_bytes == 16


def test_panther_privacy_summary_counts_truncated_findings_without_values():
    text = "\n".join("Password: never-print-this" for _ in range(25))

    summary = summarize_privacy_markers(text, max_findings=3)
    entry_summary = summarize_privacy_marker_entries(
        (("setupact.log", summary),),
        max_findings=2,
    )

    serialized_findings = json.dumps(summary["privacy_findings"], sort_keys=True)
    serialized_entry_summary = json.dumps(entry_summary, sort_keys=True)
    assert summary["privacy_scan_completed"] is True
    assert summary["privacy_findings_count"] == 25
    assert len(summary["privacy_findings"]) == 3
    assert summary["privacy_findings_truncated"] is True
    assert "never-print-this" not in serialized_findings
    assert entry_summary["privacy_scan_completed"] is True
    assert entry_summary["privacy_findings_count"] == 25
    assert len(entry_summary["privacy_findings"]) == 2
    assert entry_summary["privacy_findings_truncated"] is True
    assert "uploading or sharing" in str(entry_summary["notice"])
    assert "never-print-this" not in serialized_entry_summary


def test_panther_privacy_summary_ignores_harmless_setup_pass_and_windows_paths():
    text = (
        "2026-06-06 Info Pass: specialize\n"
        r"C:\Windows\Panther\setupact.log" "\n"
        r"Path=C:\$Windows.~BT\Sources\Panther\setupact.log" "\n"
    )

    summary = summarize_privacy_markers(text)

    assert summary["privacy_scan_completed"] is True
    assert summary["privacy_findings_count"] == 0
    assert "privacy_findings" not in summary


def test_panther_privacy_summary_reports_safe_metadata_without_values():
    first_label = "api" + "_key"
    second_label = "access" + "_token"
    third_label = "Product" + "Key"
    omitted_value = "placeholder-value-not-in-findings"
    text = (
        f"{first_label}: {omitted_value}\n"
        f"{second_label}: {omitted_value}\n"
        f"{third_label}: {omitted_value}\n"
    )

    summary = summarize_privacy_markers(text)
    entry_summary = summarize_privacy_marker_entries(
        ((r"C:\Windows\Panther\setupact.log", summary),)
    )
    findings = summary["privacy_findings"]
    entry_findings = entry_summary["privacy_findings"]
    serialized_summary = json.dumps(summary, sort_keys=True)
    serialized_entry_summary = json.dumps(entry_summary, sort_keys=True)

    assert summary["privacy_findings_count"] == 3
    assert {finding["marker"] for finding in findings} == {"token_assignment", "product_key"}
    assert {finding["finding_type"] for finding in findings} == {
        "token:token_assignment",
        "license_key:product_key",
    }
    assert all(isinstance(finding["line_chars"], int) and finding["line_chars"] > 0 for finding in findings)
    assert all(isinstance(finding["line_bytes_utf8"], int) and finding["line_bytes_utf8"] > 0 for finding in findings)
    assert all("omitted" in str(finding["safe_hint"]) for finding in findings)
    assert entry_findings[0]["path"] == r"C:\Windows\Panther\setupact.log"
    assert entry_findings[0]["line_chars"] == findings[0]["line_chars"]
    assert omitted_value not in serialized_summary
    assert omitted_value not in serialized_entry_summary

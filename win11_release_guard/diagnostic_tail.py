from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


PANTHER_PRIVACY_NOTICE = (
    "Panther/setup logs matched privacy-sensitive markers. Default JSON omits raw log content; "
    "review --include-raw-local-diagnostics output before uploading or sharing it."
)

_PRIVACY_MARKER_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("credential", "password", re.compile(r"\b(?:password|passwd|pwd)\b\s*[:=]", re.IGNORECASE)),
    ("credential", "authorization_header", re.compile(r"\bauthorization\s*[:=]\s*(?:bearer|basic|digest)\b", re.IGNORECASE)),
    (
        "secret",
        "secret_assignment",
        re.compile(r"\b(?:client[_ -]?secret|shared[_ -]?secret|secret)\b\s*[:=]", re.IGNORECASE),
    ),
    (
        "token",
        "token_assignment",
        re.compile(
            r"\b(?:access[_ -]?token|refresh[_ -]?token|auth[_ -]?token|bearer[_ -]?token|api[_ -]?key|token)\b\s*[:=]",
            re.IGNORECASE,
        ),
    ),
    (
        "credential",
        "connection_string",
        re.compile(
            r"\b(?:connection[_ -]?string|user id|uid)\s*=.*\b(?:password|pwd)\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "secret",
        "sas_signature",
        re.compile(r"\bsv=\d{4}-\d{2}-\d{2}\S*\bsig=", re.IGNORECASE),
    ),
    (
        "license_key",
        "product_key",
        re.compile(r"\b(?:product[_ -]?key|genericvolumelicensekey|gvlk)\b\s*[:=]", re.IGNORECASE),
    ),
    (
        "private_key",
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    ),
)

_PRIVACY_MARKER_HINTS: Mapping[str, str] = {
    "authorization_header": "Review before sharing raw diagnostics; authorization header value is omitted.",
    "connection_string": "Review before sharing raw diagnostics; connection string secret value is omitted.",
    "password": "Review before sharing raw diagnostics; password-like value is omitted.",
    "private_key_block": "Review before sharing raw diagnostics; private key block content is omitted.",
    "product_key": "Review before sharing raw diagnostics; product key value is omitted.",
    "sas_signature": "Review before sharing raw diagnostics; signed URL/query value is omitted.",
    "secret_assignment": "Review before sharing raw diagnostics; secret-like value is omitted.",
    "token_assignment": "Review before sharing raw diagnostics; token/key-like value is omitted.",
}


@dataclass(frozen=True)
class DiagnosticTail:
    content: str
    file_size_bytes: int
    tail_start_offset: int
    tail_truncated: bool
    tail_bytes: int
    encoding_detected: str
    decode_errors_replaced: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "file_size_bytes": self.file_size_bytes,
            "tail_start_offset": self.tail_start_offset,
            "tail_truncated": self.tail_truncated,
            "tail_bytes": self.tail_bytes,
            "encoding_detected": self.encoding_detected,
            "decode_errors_replaced": self.decode_errors_replaced,
        }


def summarize_privacy_markers(text: str, *, max_findings: int = 20) -> dict[str, object]:
    """Return Panther-safe privacy metadata without copying secret values."""

    finding_limit = max(0, int(max_findings))
    findings: list[dict[str, object]] = []
    finding_count = 0

    for line_number, line in enumerate(str(text).splitlines(), start=1):
        for category, marker, pattern in _PRIVACY_MARKER_PATTERNS:
            if not pattern.search(line):
                continue
            finding_count += 1
            if len(findings) < finding_limit:
                findings.append(
                    {
                        "category": category,
                        "finding_type": f"{category}:{marker}",
                        "marker": marker,
                        "line_number": line_number,
                        "line_chars": len(line),
                        "line_bytes_utf8": len(line.encode("utf-8", errors="replace")),
                        "safe_hint": _PRIVACY_MARKER_HINTS.get(
                            marker,
                            "Review before sharing raw diagnostics; matched value is omitted.",
                        ),
                    }
                )

    summary: dict[str, object] = {
        "privacy_scan_completed": True,
        "privacy_findings_count": finding_count,
    }
    if findings:
        summary["privacy_findings"] = findings
    if finding_count > len(findings):
        summary["privacy_findings_truncated"] = True
    return summary


def summarize_privacy_marker_entries(
    entries: Iterable[tuple[str | None, Mapping[str, object]]],
    *,
    max_findings: int = 50,
) -> dict[str, object]:
    finding_limit = max(0, int(max_findings))
    findings: list[dict[str, object]] = []
    finding_count = 0
    truncated = False

    for source_path, entry in entries:
        entry_count = entry.get("privacy_findings_count", 0)
        try:
            finding_count += int(entry_count)
        except (TypeError, ValueError):
            truncated = True

        if bool(entry.get("privacy_findings_truncated")):
            truncated = True

        entry_findings = entry.get("privacy_findings")
        if not isinstance(entry_findings, list):
            continue
        for finding in entry_findings:
            if not isinstance(finding, Mapping):
                continue
            if len(findings) >= finding_limit:
                truncated = True
                continue
            item = {
                "category": finding.get("category"),
                "finding_type": finding.get("finding_type"),
                "marker": finding.get("marker"),
                "line_number": finding.get("line_number"),
                "line_chars": finding.get("line_chars"),
                "line_bytes_utf8": finding.get("line_bytes_utf8"),
                "safe_hint": finding.get("safe_hint"),
            }
            if source_path:
                item["path"] = str(source_path)
            findings.append(item)

    summary: dict[str, object] = {
        "privacy_scan_completed": True,
        "privacy_findings_count": finding_count,
    }
    if finding_count:
        summary["notice"] = PANTHER_PRIVACY_NOTICE
    if findings:
        summary["privacy_findings"] = findings
    if truncated or finding_count > len(findings):
        summary["privacy_findings_truncated"] = True
    return summary


def _encoding_from_bom(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-bom", "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return "utf-16le-bom", "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16be-bom", "utf-16-be"
    return None


def _detect_tail_encoding(data: bytes, *, file_prefix: bytes = b"") -> tuple[str, str]:
    prefix_bom = _encoding_from_bom(file_prefix)
    if prefix_bom:
        return prefix_bom
    data_bom = _encoding_from_bom(data)
    if data_bom:
        return data_bom

    sample = data[: min(len(data), 4096)]
    if sample:
        even_nuls = sum(1 for index in range(0, len(sample), 2) if sample[index] == 0)
        odd_nuls = sum(1 for index in range(1, len(sample), 2) if sample[index] == 0)
        nul_threshold = max(2, len(sample) // 16)
        if odd_nuls >= nul_threshold and odd_nuls >= even_nuls * 2:
            return "utf-16le-heuristic", "utf-16-le"
        if even_nuls >= nul_threshold and even_nuls >= odd_nuls * 2:
            return "utf-16be-heuristic", "utf-16-be"

    return "utf-8", "utf-8"


def _is_utf16_codec(codec: str) -> bool:
    return codec in {"utf-16-le", "utf-16-be"}


def _align_tail_start_for_utf16(
    *,
    tail_start_offset: int,
    bytes_to_read: int,
    file_size_bytes: int,
    file_prefix: bytes,
    codec: str,
) -> tuple[int, int]:
    if bytes_to_read <= 0 or not _is_utf16_codec(codec):
        return tail_start_offset, bytes_to_read

    prefix_bom = _encoding_from_bom(file_prefix)
    base_offset = 2 if prefix_bom and _is_utf16_codec(prefix_bom[1]) else 0
    if 0 < tail_start_offset < base_offset:
        bytes_to_read = min(file_size_bytes, bytes_to_read + tail_start_offset)
        return 0, bytes_to_read

    if tail_start_offset > base_offset and (tail_start_offset - base_offset) % 2:
        tail_start_offset -= 1
        bytes_to_read = min(file_size_bytes - tail_start_offset, bytes_to_read + 1)
    return tail_start_offset, bytes_to_read


def _decode_tail(data: bytes, *, file_prefix: bytes = b"") -> tuple[str, str, bool]:
    encoding_detected, codec = _detect_tail_encoding(data, file_prefix=file_prefix)
    try:
        text = data.decode(codec, errors="strict")
        return text.removeprefix("\ufeff"), encoding_detected, False
    except UnicodeDecodeError:
        return data.decode(codec, errors="replace").removeprefix("\ufeff"), encoding_detected, True


def read_diagnostic_tail(path: str | Path, max_bytes: int) -> DiagnosticTail:
    log_path = Path(path)
    size = log_path.stat().st_size
    bytes_to_read = max(0, min(int(max_bytes), int(size)))
    tail_start_offset = max(0, size - bytes_to_read)

    with log_path.open("rb") as handle:
        file_prefix = handle.read(min(size, 4))
        if bytes_to_read == 0:
            tail_start_offset = size if size else 0
            handle.seek(size, os.SEEK_SET)
        elif size > bytes_to_read:
            handle.seek(tail_start_offset, os.SEEK_SET)
            probe = handle.read(min(bytes_to_read, 4096))
            _encoding_detected, codec = _detect_tail_encoding(probe, file_prefix=file_prefix)
            tail_start_offset, bytes_to_read = _align_tail_start_for_utf16(
                tail_start_offset=tail_start_offset,
                bytes_to_read=bytes_to_read,
                file_size_bytes=size,
                file_prefix=file_prefix,
                codec=codec,
            )
            handle.seek(tail_start_offset, os.SEEK_SET)
        else:
            handle.seek(0, os.SEEK_SET)
            tail_start_offset = 0
        data = handle.read(bytes_to_read)

    content, encoding_detected, decode_errors_replaced = _decode_tail(data, file_prefix=file_prefix)
    return DiagnosticTail(
        content=content,
        file_size_bytes=size,
        tail_start_offset=tail_start_offset,
        tail_truncated=tail_start_offset > 0,
        tail_bytes=len(data),
        encoding_detected=encoding_detected,
        decode_errors_replaced=decode_errors_replaced,
    )

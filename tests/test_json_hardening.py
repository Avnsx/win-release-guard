from __future__ import annotations


import base64
import json

import pytest

from win11_release_guard import __main__ as cli
from win11_release_guard.cache import load_policy_cache
from win11_release_guard.exceptions import PolicyParseError, PolicyTrustError
from win11_release_guard.json_utils import (
    DEFAULT_MAX_MANIFEST_BYTES,
    DEFAULT_MAX_POLICY_BYTES,
    DEFAULT_MAX_SIGNATURE_BYTES,
)
from win11_release_guard.policy_schema import GENERATOR_VERSION
from win11_release_guard.remote_policy import fetch_policy_bytes, load_policy_bytes, load_policy_text
from win11_release_guard.signing import decode_policy_signature_metadata


def _valid_policy_json(*, padding_bytes: int = 0) -> dict:
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-28T00:00:00Z",
        "generator_version": GENERATOR_VERSION,
        "source_urls": [("https://example" + ".invalid/windows-release-policy.json")],
        "published_urls": {
            "landing": "https://example" + ".invalid/win11_release_guard/",
            "policy": "https://example" + ".invalid/win11_release_guard/windows-release-policy.json",
            "signature": "https://example" + ".invalid/win11_release_guard/windows-release-policy.json.sig",
            "manifest": "https://example" + ".invalid/win11_release_guard/policy-manifest.json",
            "api_policy": "https://example" + ".invalid/win11_release_guard/api/v1/policy.json",
            "api_signature": "https://example" + ".invalid/win11_release_guard/api/v1/policy.sig",
            "api_manifest": "https://example" + ".invalid/win11_release_guard/api/v1/manifest.json",
        },
        "source_fetch_status": {"release_health_html": {"status": "ok"}},
        "current_versions": [
            {
                "version": "25H2",
                "build_family": 26200,
                "latest_build": "26200.8457",
                "baseline_build": "26200.8457",
                "servicing_option": "General Availability Channel",
            }
        ],
        "supported_build_families": {"26200": "25H2"},
        "broad_target_existing_devices": {
            "version": "25H2",
            "build_family": 26200,
            "latest_build": "26200.8457",
            "baseline_build": "26200.8457",
            "servicing_option": "General Availability Channel",
        },
        "release_history": [
            {
                "release": "25H2",
                "build_family": 26200,
                "build": "26200.8457",
                "update_type_letter": "B",
                "preview": False,
                "out_of_band": False,
            }
        ],
        "excluded_for_existing_devices": [],
        "special_releases": [],
        "quality_baselines": {
            "25H2": {
                "b_release_only": {
                    "release": "25H2",
                    "build_family": 26200,
                    "build": "26200.8457",
                    "update_type_letter": "B",
                    "preview": False,
                    "out_of_band": False,
                }
            }
        },
        "preview_builds": [],
        "out_of_band_builds": [],
        "known_notes": [],
        "validation_warnings": [],
        "x_padding": "A" * padding_bytes,
    }


def _valid_policy_bytes(*, padding_bytes: int = 0) -> bytes:
    return (json.dumps(_valid_policy_json(padding_bytes=padding_bytes), sort_keys=True) + "\n").encode("utf-8")


def test_remote_policy_json_rejects_duplicate_top_level_keys() -> None:
    payload = '{"schema_version": 1, "schema_version": 2}'
    with pytest.raises(PolicyParseError, match="Duplicate JSON object key"):
        load_policy_text(payload)


def test_remote_policy_json_rejects_non_finite_numbers() -> None:
    payload = '{"schema_version": NaN}'
    with pytest.raises(PolicyParseError, match="Non-finite JSON numeric value"):
        load_policy_text(payload)


def test_remote_policy_json_rejects_non_object_top_level() -> None:
    with pytest.raises(PolicyParseError, match="top-level value must be an object"):
        load_policy_text("[]")


def test_remote_policy_invalid_utf8_error_is_policy_parse_error() -> None:
    with pytest.raises(PolicyParseError, match="not valid UTF-8") as error:
        load_policy_bytes(b"\xffnot-json", content_type="application/json")
    assert "codec can't decode" not in str(error.value)


def test_public_manifest_json_rejects_duplicate_keys() -> None:
    with pytest.raises(PolicyParseError, match="Duplicate JSON object key"):
        cli._decode_json_bytes(b'{"policy_sha256":"a", "policy_sha256":"b"}', label="Policy manifest")


def test_public_manifest_json_rejects_non_object_top_level() -> None:
    with pytest.raises(PolicyParseError, match="top-level value must be an object"):
        cli._decode_json_bytes(b'[]', label="Policy manifest")


def test_large_valid_policy_json_below_cap_loads() -> None:
    payload = _valid_policy_bytes(padding_bytes=64 * 1024)

    policy = load_policy_bytes(payload, content_type="application/json", max_bytes=len(payload) + 1)

    assert policy.broad_target_existing_devices is not None
    assert policy.broad_target_existing_devices.version == "25H2"
    assert DEFAULT_MAX_POLICY_BYTES >= 128 * 1024 * 1024


def test_oversized_policy_json_above_cap_is_rejected() -> None:
    payload = _valid_policy_bytes(padding_bytes=1024)

    with pytest.raises(PolicyParseError, match="too large"):
        load_policy_bytes(payload, content_type="application/json", max_bytes=len(payload) - 1)


def test_large_valid_manifest_json_below_manifest_cap_loads() -> None:
    payload = json.dumps({"policy_sha256": "a" * 64, "x_padding": "A" * (64 * 1024)}).encode("utf-8")

    manifest = cli._decode_json_bytes(payload, label="Policy manifest", max_bytes=len(payload) + 1)

    assert manifest["policy_sha256"] == "a" * 64
    assert DEFAULT_MAX_MANIFEST_BYTES >= 1024 * 1024


def test_signature_json_rejects_duplicate_keys() -> None:
    with pytest.raises(PolicyTrustError):
        decode_policy_signature_metadata(
            b'{"algorithm":"ed25519", "signature":"AA==", "signature":"BB=="}'
        )


def test_legacy_raw_base64_and_hex_signatures_still_decode() -> None:
    raw = bytes(range(64))

    assert decode_policy_signature_metadata(raw).signature == raw
    assert decode_policy_signature_metadata(base64.b64encode(raw)).signature == raw
    assert decode_policy_signature_metadata(raw.hex().encode("ascii")).signature == raw


def test_oversized_signature_is_rejected() -> None:
    with pytest.raises(PolicyTrustError, match="too large"):
        decode_policy_signature_metadata(b"A" * (DEFAULT_MAX_SIGNATURE_BYTES + 1))


def test_cache_json_rejects_duplicate_keys(tmp_path) -> None:
    cache_file = tmp_path / "windows-release-policy.json"
    cache_file.write_text('{"schema_version": 1, "schema_version": 2}', encoding="utf-8")
    with pytest.raises(PolicyParseError, match="Duplicate JSON object key"):
        load_policy_cache(cache_file)


def test_cache_json_rejects_oversized_file_before_parse(tmp_path, monkeypatch) -> None:
    import win11_release_guard.cache as cache

    monkeypatch.setattr(cache, "DEFAULT_MAX_POLICY_BYTES", 4)
    cache_file = tmp_path / "windows-release-policy.json"
    cache_file.write_text("{}   ", encoding="utf-8")

    with pytest.raises(PolicyParseError, match="too large"):
        load_policy_cache(cache_file)


def test_local_policy_fetch_rejects_oversized_file(tmp_path, monkeypatch) -> None:
    policy_file = tmp_path / "windows-release-policy.json"
    policy_file.write_text("{}   ", encoding="utf-8")

    with pytest.raises(Exception, match="too large"):
        fetch_policy_bytes(str(policy_file), max_bytes=4)


def test_remote_policy_fetch_rejects_declared_content_length_above_cap() -> None:
    class Response:
        headers = {"Content-Length": "5"}
        read_called = False

        def read(self, amount):
            self.read_called = True
            return b"{}"

    response = Response()

    with pytest.raises(Exception, match="safety cap"):
        fetch_policy_bytes(
            "https://example" + ".invalid/policy.json",
            http_get=lambda *args, **kwargs: response,
            max_bytes=4,
        )
    assert response.read_called is False


def test_remote_policy_fetch_reads_only_cap_plus_one_without_content_length() -> None:
    class Response:
        headers = {}
        requested_amount = None

        def read(self, amount):
            self.requested_amount = amount
            return b"{}   "

    response = Response()

    with pytest.raises(Exception, match="safety cap"):
        fetch_policy_bytes(
            "https://example" + ".invalid/policy.json",
            http_get=lambda *args, **kwargs: response,
            max_bytes=4,
        )
    assert response.requested_amount == 5


def test_signature_invalid_utf8_error_is_policy_trust_error() -> None:
    with pytest.raises(PolicyTrustError, match="Policy signature is not valid UTF-8") as error:
        decode_policy_signature_metadata(b"\xffnot-json")
    assert "codec can't decode" not in str(error.value)

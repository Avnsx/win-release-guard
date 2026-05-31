from __future__ import annotations

import json
import hashlib
from pathlib import Path

from win11_release_guard import __main__ as cli
from win11_release_guard.config import DEFAULT_POLICY_URL, DEFAULT_PUBLISHED_POLICY_URLS, DEFAULT_RELEASE_HEALTH_URL
from win11_release_guard.exceptions import PolicyFetchError
from win11_release_guard.signing import sign_policy_bytes


TEST_PRIVATE_KEY = "krtF2muLgucP7JDVNKk2g+YQfz92c7xM49dzszxHxjs="
TEST_PUBLIC_KEY = "45dOpVuYqoPkldNrzORHM5ZZUxs6ILVcvpKxRFxsu3s="


def _policy_json() -> dict:
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-28T00:00:00Z",
        "generator_version": "win-release-guard/0.2",
        "source_urls": [
            DEFAULT_RELEASE_HEALTH_URL,
        ],
        "published_urls": dict(DEFAULT_PUBLISHED_POLICY_URLS),
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
                "availability_date": "2026-05-12",
                "servicing_option": "General Availability Channel",
                "update_type": "2026-05 B",
                "update_type_letter": "B",
                "kb_article": "KB5089549",
            }
        ],
        "excluded_for_existing_devices": [
            {
                "version": "26H1",
                "build_family": 28000,
                "reason": "new devices only",
                "servicing_option": "General Availability Channel",
            }
        ],
        "special_releases": [
            {
                "version": "26H1",
                "build_family": 28000,
                "reason": "new devices only",
                "servicing_option": "General Availability Channel",
            }
        ],
        "quality_baselines": {
            "25H2": {
                "b_release_only": {
                    "release": "25H2",
                    "build_family": 26200,
                    "build": "26200.8457",
                    "availability_date": "2026-05-12",
                    "servicing_option": "General Availability Channel",
                    "update_type": "2026-05 B",
                    "update_type_letter": "B",
                    "preview": False,
                    "out_of_band": False,
                    "kb_article": "KB5089549",
                }
            }
        },
        "preview_builds": [],
        "out_of_band_builds": [],
        "known_notes": [],
        "validation_warnings": [],
    }


def _write_policy_and_signature(path: Path, policy_bytes: bytes, *, valid_signature: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(policy_bytes)
    if valid_signature:
        signature = sign_policy_bytes(policy_bytes, TEST_PRIVATE_KEY)
        path.with_name(path.name + ".sig").write_bytes(
            (json.dumps(signature, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    else:
        path.with_name(path.name + ".sig").write_bytes(
            b'{"algorithm":"ed25519","signature":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="}'
        )


def _policy_bytes() -> bytes:
    return (json.dumps(_policy_json(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _signature_bytes(policy_bytes: bytes) -> bytes:
    signature = sign_policy_bytes(policy_bytes, TEST_PRIVATE_KEY)
    return (json.dumps(signature, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _manifest_bytes(policy_bytes: bytes) -> bytes:
    return (
        json.dumps(
            {
                "schema_version": 1,
                "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
                "published_urls": dict(DEFAULT_PUBLISHED_POLICY_URLS),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _fake_source_fetch(policy_bytes: bytes, signature_bytes: bytes, manifest_bytes: bytes):
    def fake_fetch(url, *args, **kwargs):
        url = str(url)
        if url == DEFAULT_POLICY_URL:
            return policy_bytes, "application/json"
        if url == f"{DEFAULT_POLICY_URL}.sig":
            return signature_bytes, "application/json"
        if url == DEFAULT_PUBLISHED_POLICY_URLS["manifest"]:
            return manifest_bytes, "application/json"
        raise PolicyFetchError(f"unexpected URL {url}")

    return fake_fetch


def test_check_policy_source_local_signed_file_ok(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: (_ for _ in ()).throw(AssertionError("local probe ran")))
    policy_file = tmp_path / "windows-release-policy.json"
    _write_policy_and_signature(
        policy_file,
        _policy_bytes(),
    )

    code = cli.main([
        "--check-policy-source",
        "--policy-url",
        str(policy_file),
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert "Policy source: OK" in output
    assert "Signature: valid" in output
    assert "Generated at UTC: 2026-05-28T00:00:00Z" in output
    assert f"- {DEFAULT_RELEASE_HEALTH_URL}" in output
    assert f"- policy: {DEFAULT_POLICY_URL}" in output
    assert f"- api_policy: {DEFAULT_PUBLISHED_POLICY_URLS['api_policy']}" in output
    assert "Broad target: 25H2 / 26200 / 26200.8457" in output
    assert "Baseline: 26200.8457" in output
    assert "- 26H1 / 28000 / new devices only" in output


def test_check_policy_source_invalid_signature_fails(tmp_path, capsys):
    policy_file = tmp_path / "windows-release-policy.json"
    _write_policy_and_signature(
        policy_file,
        _policy_bytes(),
        valid_signature=False,
    )

    code = cli.main([
        "--check-policy-source",
        "--policy-url",
        str(policy_file),
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == cli.EXIT_UNKNOWN_OR_POLICY_ERROR
    assert "Policy source: SIGNATURE_FAILED" in output
    assert "Policy signature invalid:" in output


def test_check_policy_source_malformed_policy_fails(tmp_path, capsys):
    policy_file = tmp_path / "windows-release-policy.json"
    _write_policy_and_signature(policy_file, b"{not-json")

    code = cli.main([
        "--check-policy-source",
        "--policy-url",
        str(policy_file),
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == cli.EXIT_UNKNOWN_OR_POLICY_ERROR
    assert "Policy source: INVALID" in output
    assert "Malformed JSON policy" in output


def test_check_policy_source_network_unavailable_is_explicit(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "fetch_policy_bytes",
        lambda *args, **kwargs: (_ for _ in ()).throw(PolicyFetchError("network unavailable")),
    )

    code = cli.main([
        "--check-policy-source",
        "--policy-url",
        ("https://example" + ".invalid/windows-release-policy.json"),
    ])

    output = capsys.readouterr().out
    assert code == cli.EXIT_UNKNOWN_OR_POLICY_ERROR
    assert "Policy source: UNAVAILABLE" in output
    assert "Policy source unavailable:" in output
    assert "network unavailable" in output


def test_check_policy_source_default_url_checks_manifest_without_local_probes(monkeypatch, capsys):
    monkeypatch.setattr(cli, "check_current_system", lambda config: (_ for _ in ()).throw(AssertionError("local probe ran")))
    policy_bytes = _policy_bytes()
    signature_bytes = _signature_bytes(policy_bytes)
    manifest_bytes = _manifest_bytes(policy_bytes)
    calls: list[str] = []

    def fake_fetch(url, *args, **kwargs):
        calls.append(str(url))
        return _fake_source_fetch(policy_bytes, signature_bytes, manifest_bytes)(url, *args, **kwargs)

    monkeypatch.setattr(cli, "fetch_policy_bytes", fake_fetch)

    code = cli.main([
        "--check-policy-source",
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert calls == [
        DEFAULT_POLICY_URL,
        f"{DEFAULT_POLICY_URL}.sig",
        DEFAULT_PUBLISHED_POLICY_URLS["manifest"],
    ]
    assert f"Policy URL: {DEFAULT_POLICY_URL}" in output
    assert f"Signature URL: {DEFAULT_POLICY_URL}.sig" in output
    assert f"Manifest URL: {DEFAULT_PUBLISHED_POLICY_URLS['manifest']}" in output
    assert "Manifest: ok" in output
    assert "Broad target: 25H2 / 26200 / 26200.8457" in output
    assert "Baseline: 26200.8457" in output
    assert "Published URLs:" in output


def test_check_policy_source_manifest_hash_mismatch_fails(monkeypatch, capsys):
    policy_bytes = _policy_bytes()
    signature_bytes = _signature_bytes(policy_bytes)
    bad_manifest = b'{"policy_sha256":"bad"}\n'
    monkeypatch.setattr(cli, "fetch_policy_bytes", _fake_source_fetch(policy_bytes, signature_bytes, bad_manifest))

    code = cli.main([
        "--check-policy-source",
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == cli.EXIT_UNKNOWN_OR_POLICY_ERROR
    assert "Policy source: INVALID" in output
    assert "Manifest: sha256_mismatch" in output
    assert "policy_sha256 does not match" in output


class PublicResponse:
    def __init__(self, url: str, status_code: int, content: bytes, headers: dict[str, str] | None = None):
        self.url = url
        self.status_code = status_code
        self.content = content
        self.content_type = headers.get("Content-Type") if headers else None
        self.headers = headers or {}

    @property
    def auth_challenge(self) -> bool:
        return self.status_code == 401 or any(key.lower() == "www-authenticate" for key in self.headers)


def test_check_public_pages_validates_pages_and_aliases(monkeypatch, capsys):
    policy_bytes = _policy_bytes()
    signature_bytes = _signature_bytes(policy_bytes)
    manifest_bytes = _manifest_bytes(policy_bytes)
    monkeypatch.setattr(cli, "fetch_policy_bytes", _fake_source_fetch(policy_bytes, signature_bytes, manifest_bytes))

    page_bytes = {
        DEFAULT_PUBLISHED_POLICY_URLS["landing"]: b"<html><title>win-release-guard</title></html>",
        DEFAULT_POLICY_URL: policy_bytes,
        f"{DEFAULT_POLICY_URL}.sig": signature_bytes,
        DEFAULT_PUBLISHED_POLICY_URLS["manifest"]: manifest_bytes,
        DEFAULT_PUBLISHED_POLICY_URLS["api_policy"]: policy_bytes,
        DEFAULT_PUBLISHED_POLICY_URLS["api_signature"]: signature_bytes,
        DEFAULT_PUBLISHED_POLICY_URLS["api_manifest"]: manifest_bytes,
        "https://avnsx.github.io/win-release-guard/robots.txt": b"User-agent: *\nAllow: /\n",
        "https://avnsx.github.io/win-release-guard/sitemap.xml": b"<?xml version=\"1.0\"?><urlset></urlset>",
    }

    def fake_public_url(url, *, timeout):
        return PublicResponse(str(url), 200, page_bytes[str(url)], {"Content-Type": "application/json"})

    monkeypatch.setattr(cli, "_fetch_public_url", fake_public_url)

    code = cli.main([
        "--check-public-pages",
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert "Public Pages: OK" in output
    assert "- landing: OK HTTP 200" in output
    assert "- api_policy: OK HTTP 200" in output
    assert "- api_signature: OK HTTP 200" in output
    assert "- robots: OK HTTP 200" in output


def test_check_public_pages_auth_challenge_fails(monkeypatch, capsys):
    policy_bytes = _policy_bytes()
    signature_bytes = _signature_bytes(policy_bytes)
    manifest_bytes = _manifest_bytes(policy_bytes)
    monkeypatch.setattr(cli, "fetch_policy_bytes", _fake_source_fetch(policy_bytes, signature_bytes, manifest_bytes))

    def fake_public_url(url, *, timeout):
        if str(url) == DEFAULT_PUBLISHED_POLICY_URLS["landing"]:
            return PublicResponse(str(url), 401, b"", {"WWW-Authenticate": "Basic"})
        return PublicResponse(str(url), 200, b"{}", {"Content-Type": "application/json"})

    monkeypatch.setattr(cli, "_fetch_public_url", fake_public_url)

    code = cli.main([
        "--check-public-pages",
        "--trusted-policy-public-key",
        TEST_PUBLIC_KEY,
    ])

    output = capsys.readouterr().out
    assert code == cli.EXIT_UNKNOWN_OR_POLICY_ERROR
    assert "Policy source: PUBLIC_PAGES_FAILED" in output
    assert "Public Pages: FAILED" in output
    assert "auth challenge present" in output

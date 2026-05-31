from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools import generate_signing_key
from win11_release_guard.bundled_policy import load_bundled_policy
from win11_release_guard.signing import (
    decode_policy_signature_metadata,
    load_trusted_policy_keys,
    sign_policy_bytes,
    verify_policy_signature,
)


TEST_PRIVATE_KEY = "krtF2muLgucP7JDVNKk2g+YQfz92c7xM49dzszxHxjs="
TEST_PUBLIC_KEY = "45dOpVuYqoPkldNrzORHM5ZZUxs6ILVcvpKxRFxsu3s="


def _public_key_b64(private_key_b64: str) -> str:
    private_key = Ed25519PrivateKey.from_private_bytes(
        base64.b64decode(private_key_b64)
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(public_key).decode("ascii")


def test_generated_key_signs_and_verifies(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    code = generate_signing_key.main([
        "--out-dir",
        ".tmp/signing-key",
        "--key-id",
        "test-policy-key",
        "--created-at-utc",
        "2026-05-31T00:00:00+00:00",
    ])

    output = capsys.readouterr().out
    out_dir = Path(".tmp/signing-key")
    private_key_b64 = (out_dir / "private-key.b64").read_text(encoding="utf-8").strip()
    public_key_b64 = (out_dir / "public-key.b64").read_text(encoding="utf-8").strip()
    trusted_keys = json.loads((out_dir / "trusted_policy_keys.json").read_text(encoding="utf-8"))
    policy_bytes = b'{"schema_version":1}\n'
    signature = sign_policy_bytes(policy_bytes, private_key_b64, key_id="test-policy-key")
    signature_bytes = json.dumps(signature).encode("utf-8")

    assert code == 0
    assert generate_signing_key.PRIVATE_KEY_SECRET_NAME in output
    assert public_key_b64 == _public_key_b64(private_key_b64)
    assert trusted_keys["trusted_policy_keys"][0]["key_id"] == "test-policy-key"
    assert trusted_keys["trusted_policy_keys"][0]["public_key_b64"] == public_key_b64
    assert verify_policy_signature(policy_bytes, signature_bytes, public_key_b64)


def test_generate_signing_key_refuses_private_key_outside_tmp(tmp_path, capsys):
    code = generate_signing_key.main(["--out-dir", str(tmp_path / "signing-key")])

    captured = capsys.readouterr()
    assert code == 2
    assert "Refusing to write private-key.b64 outside .tmp/" in captured.err


def test_wrong_key_corrupted_policy_and_corrupted_signature_fail():
    policy_bytes = b'{"schema_version":1}\n'
    signature = sign_policy_bytes(policy_bytes, TEST_PRIVATE_KEY, key_id="test-key")
    signature_bytes = json.dumps(signature).encode("utf-8")
    wrong_private_key = Ed25519PrivateKey.generate()
    wrong_public_key = wrong_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    wrong_public_key_b64 = base64.b64encode(wrong_public_key).decode("ascii")

    assert not verify_policy_signature(policy_bytes, signature_bytes, wrong_public_key_b64)
    assert not verify_policy_signature(b'{"schema_version":2}\n', signature_bytes, TEST_PUBLIC_KEY)

    corrupted = dict(signature)
    corrupted["signature"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
    assert not verify_policy_signature(policy_bytes, json.dumps(corrupted).encode("utf-8"), TEST_PUBLIC_KEY)


def test_unknown_key_id_fails_without_public_key_override():
    policy_bytes = b'{"schema_version":1}\n'
    signature = sign_policy_bytes(policy_bytes, TEST_PRIVATE_KEY, key_id="unknown-policy-key")

    assert decode_policy_signature_metadata(json.dumps(signature).encode("utf-8")).key_id == "unknown-policy-key"
    assert not verify_policy_signature(policy_bytes, json.dumps(signature).encode("utf-8"))


def test_committed_public_key_file_contains_no_private_key_material():
    key_file = Path("win11_release_guard/data/trusted_policy_keys.json")
    data = json.loads(key_file.read_text(encoding="utf-8"))
    text = key_file.read_text(encoding="utf-8").lower()

    assert "private_key" not in text
    assert "private-key" not in text
    assert "seed" not in text
    assert data["trusted_policy_keys"]
    assert all("public_key_b64" in record for record in data["trusted_policy_keys"])
    assert all("private_key_b64" not in record for record in data["trusted_policy_keys"])


def test_runtime_can_verify_policy_with_committed_trusted_key():
    trusted = load_bundled_policy()
    trusted_keys = load_trusted_policy_keys()

    assert trusted.signature_status == "valid"
    assert trusted.policy.broad_target_existing_devices is not None
    assert any(key.key_id == "win-release-guard-policy-2026-01" for key in trusted_keys)

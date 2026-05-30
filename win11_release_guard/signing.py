from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import DEFAULT_TRUSTED_POLICY_PUBLIC_KEY
from .exceptions import PolicyTrustError
from .models import ReleasePolicy
from .remote_policy import load_policy_bytes


SIGNATURE_ALGORITHM = "ed25519"


@dataclass(frozen=True)
class TrustedPolicy:
    policy: ReleasePolicy
    policy_bytes: bytes
    signature_bytes: bytes | None
    signature_status: str
    source_url: str | None = None


def _bytes_from_text(value: str) -> bytes:
    return value.encode("utf-8")


def _decode_key_material(value: str | bytes) -> bytes:
    raw = value if isinstance(value, bytes) else _bytes_from_text(value.strip())
    if raw.startswith(b"-----BEGIN"):
        return raw
    try:
        return base64.b64decode(raw, validate=True)
    except binascii.Error:
        return raw


def load_public_key(public_key: str | bytes | None = None) -> Ed25519PublicKey:
    key_material = _decode_key_material(public_key or DEFAULT_TRUSTED_POLICY_PUBLIC_KEY)
    if key_material.startswith(b"-----BEGIN"):
        loaded = serialization.load_pem_public_key(key_material)
        if not isinstance(loaded, Ed25519PublicKey):
            raise PolicyTrustError("Trusted policy public key is not an Ed25519 public key.")
        return loaded
    if len(key_material) != 32:
        raise PolicyTrustError("Trusted policy public key must be 32 raw Ed25519 bytes or PEM.")
    return Ed25519PublicKey.from_public_bytes(key_material)


def load_private_key(private_key: str | bytes) -> Ed25519PrivateKey:
    key_material = _decode_key_material(private_key)
    if key_material.startswith(b"-----BEGIN"):
        loaded = serialization.load_pem_private_key(key_material, password=None)
        if not isinstance(loaded, Ed25519PrivateKey):
            raise PolicyTrustError("Signing key is not an Ed25519 private key.")
        return loaded
    if len(key_material) != 32:
        raise PolicyTrustError("Signing key must be a 32-byte raw Ed25519 seed or PEM.")
    return Ed25519PrivateKey.from_private_bytes(key_material)


def _decode_signature_value(value: str) -> bytes:
    normalized = value.strip()
    try:
        return base64.b64decode(normalized, validate=True)
    except binascii.Error:
        try:
            return bytes.fromhex(normalized)
        except ValueError as exc:
            raise PolicyTrustError("Policy signature is not valid base64 or hex.") from exc


def decode_policy_signature(signature_bytes: bytes) -> bytes:
    stripped = signature_bytes.strip()
    if not stripped:
        raise PolicyTrustError("Policy signature is empty.")

    try:
        parsed: Any = json.loads(stripped.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        if len(stripped) == 64:
            return bytes(stripped)
        return _decode_signature_value(stripped.decode("utf-8"))

    if isinstance(parsed, dict):
        algorithm = str(parsed.get("algorithm") or "").lower()
        if algorithm and algorithm != SIGNATURE_ALGORITHM:
            raise PolicyTrustError(f"Unsupported policy signature algorithm {algorithm!r}.")
        signature = parsed.get("signature")
        if not isinstance(signature, str):
            raise PolicyTrustError("Policy signature JSON is missing string field 'signature'.")
        return _decode_signature_value(signature)
    if isinstance(parsed, str):
        return _decode_signature_value(parsed)
    raise PolicyTrustError("Policy signature must be raw bytes, text, or a JSON object.")


def sign_policy_bytes(policy_bytes: bytes, private_key: str | bytes) -> dict[str, str]:
    signer = load_private_key(private_key)
    signature = signer.sign(policy_bytes)
    return {
        "algorithm": SIGNATURE_ALGORITHM,
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def verify_policy_signature(
    policy_bytes: bytes,
    signature_bytes: bytes,
    public_key: str | bytes | None = None,
) -> bool:
    verifier = load_public_key(public_key)
    try:
        verifier.verify(decode_policy_signature(signature_bytes), policy_bytes)
    except (InvalidSignature, PolicyTrustError):
        return False
    return True


def load_trusted_policy(
    policy_bytes: bytes,
    *,
    signature_bytes: bytes | None = None,
    public_key: str | bytes | None = None,
    require_signature: bool = True,
    allow_unsigned: bool = False,
    content_type: str | None = "application/json",
    source_url: str | None = None,
    allow_html_fallback: bool = False,
) -> TrustedPolicy:
    if signature_bytes is None:
        if require_signature and not allow_unsigned:
            raise PolicyTrustError("Policy signature is required but missing.")
        policy = load_policy_bytes(
            policy_bytes,
            content_type=content_type,
            source_url=source_url,
            allow_html_fallback=allow_html_fallback,
        )
        return TrustedPolicy(
            policy=policy,
            policy_bytes=policy_bytes,
            signature_bytes=None,
            signature_status="unsigned_allowed" if allow_unsigned else "unsigned",
            source_url=source_url,
        )

    if not verify_policy_signature(policy_bytes, signature_bytes, public_key):
        raise PolicyTrustError("Policy signature verification failed.")

    policy = load_policy_bytes(
        policy_bytes,
        content_type=content_type,
        source_url=source_url,
        allow_html_fallback=allow_html_fallback,
    )
    return TrustedPolicy(
        policy=policy,
        policy_bytes=policy_bytes,
        signature_bytes=signature_bytes,
        signature_status="valid",
        source_url=source_url,
    )


__all__ = [
    "SIGNATURE_ALGORITHM",
    "TrustedPolicy",
    "decode_policy_signature",
    "load_private_key",
    "load_public_key",
    "load_trusted_policy",
    "sign_policy_bytes",
    "verify_policy_signature",
]

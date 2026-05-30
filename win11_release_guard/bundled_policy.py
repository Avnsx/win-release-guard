from __future__ import annotations

from importlib import resources

from .config import DEFAULT_TRUSTED_POLICY_PUBLIC_KEY
from .signing import TrustedPolicy, load_trusted_policy


BUNDLED_POLICY_PACKAGE = "win11_release_guard.data"
BUNDLED_POLICY_FILE = "windows-release-policy.json"
BUNDLED_POLICY_SIGNATURE_FILE = "windows-release-policy.json.sig"


def load_bundled_policy(
    *,
    public_key: str | bytes | None = DEFAULT_TRUSTED_POLICY_PUBLIC_KEY,
    allow_unsigned: bool = False,
) -> TrustedPolicy:
    package_files = resources.files(BUNDLED_POLICY_PACKAGE)
    policy_bytes = package_files.joinpath(BUNDLED_POLICY_FILE).read_bytes()
    signature_path = package_files.joinpath(BUNDLED_POLICY_SIGNATURE_FILE)
    signature_bytes = signature_path.read_bytes() if signature_path.is_file() else None
    return load_trusted_policy(
        policy_bytes,
        signature_bytes=signature_bytes,
        public_key=public_key,
        require_signature=not allow_unsigned,
        allow_unsigned=allow_unsigned,
        content_type="application/json",
        source_url=None,
    )


__all__ = [
    "BUNDLED_POLICY_FILE",
    "BUNDLED_POLICY_PACKAGE",
    "BUNDLED_POLICY_SIGNATURE_FILE",
    "load_bundled_policy",
]

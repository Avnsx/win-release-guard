from __future__ import annotations

import json
from pathlib import Path

from tools import scan_for_secret_material


REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_TARGETS = (
    "site",
    "win11_release_guard",
    "tests",
    "tools",
    "docs",
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    ".github",
)


def _scan(*paths: Path) -> list[scan_for_secret_material.Finding]:
    return scan_for_secret_material.scan_paths(paths, root=paths[0].parent if paths else REPO_ROOT)


def test_secret_material_scanner_passes_current_repo() -> None:
    findings = scan_for_secret_material.scan_paths(SCAN_TARGETS, root=REPO_ROOT)

    assert findings == []


def test_secret_material_scanner_fails_private_key_pem(tmp_path: Path) -> None:
    private_key_marker = "BEGIN " + "PRIVATE KEY"
    fixture = tmp_path / "leaked.pem"
    fixture.write_text(f"-----{private_key_marker}-----\nnot-real\n", encoding="utf-8")

    findings = _scan(fixture)

    assert any(finding.kind == "private_key_file" for finding in findings)
    assert any(finding.kind == "private_key_block" for finding in findings)


def test_secret_material_scanner_fails_private_key_file_name_in_site(tmp_path: Path) -> None:
    private_key_name = "private-" + "key.b64"
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    fixture = site_dir / private_key_name
    fixture.write_text("not-real\n", encoding="utf-8")

    findings = _scan(site_dir)

    assert any(finding.kind == "private_key_file" for finding in findings)


def test_secret_material_scanner_fails_classic_pat_like_token(tmp_path: Path) -> None:
    fixture = tmp_path / "config.txt"
    token = ("gh" + "p_") + ("A" * 36)
    fixture.write_text(f"token = {token}\n", encoding="utf-8")

    findings = _scan(fixture)

    assert any(finding.kind == "github_pat" for finding in findings)


def test_secret_material_scanner_fails_secret_env_assignment_with_value(tmp_path: Path) -> None:
    fixture = tmp_path / "env.txt"
    fixture.write_text(
        f"{scan_for_secret_material.SECRET_ENV_VAR}=not-a-real-secret-but-still-a-value\n",
        encoding="utf-8",
    )

    findings = _scan(fixture)

    assert any(finding.kind == "signing_secret_value" for finding in findings)


def test_secret_material_scanner_allows_public_key_json(tmp_path: Path) -> None:
    fixture = tmp_path / "trusted_policy_keys.json"
    fixture.write_text(
        json.dumps(
            {
                "trusted_policy_keys": [
                    {
                        "key_id": "test-policy-key",
                        "algorithm": "ed25519",
                        "public_key_b64": "5OoJIhKvOGLJ72+/EZiQHX51m0gEczh5CctQjW7wPHk=",
                        "created_at_utc": "2026-01-01T00:00:00Z",
                        "status": "active",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _scan(fixture) == []


def test_secret_material_scanner_allows_signature_json(tmp_path: Path) -> None:
    fixture = tmp_path / "windows-release-policy.json.sig"
    fixture.write_text(
        json.dumps(
            {
                "algorithm": "ed25519",
                "key_id": "test-policy-key",
                "signature": "GEleMWTQFz608+/sjJ2O1A/ZrW3fDUfFepw8M6OvDs9yd/hKaYsaI6IED7pplWs6AyZoBDdH1wTioeaxi60SAQ==",
            }
        ),
        encoding="utf-8",
    )

    assert _scan(fixture) == []

from __future__ import annotations

from pathlib import Path


def _agents_text() -> str:
    return (Path(__file__).resolve().parents[1] / "AGENTS.md").read_text(encoding="utf-8")


def test_agents_contract_exists() -> None:
    assert (Path(__file__).resolve().parents[1] / "AGENTS.md").is_file()


def test_agents_contract_locks_public_and_import_names() -> None:
    text = _agents_text()

    assert "win-release-guard" in text
    assert "win11_release_guard" in text
    assert "must not revert naming" in text


def test_agents_contract_locks_secret_and_token_rules() -> None:
    text = _agents_text()
    lower_text = text.lower()

    assert "WIN_RELEASE_GUARD_POLICY_SIGNING_KEY_B64" in text
    assert "clients must not contain github tokens" in lower_text
    assert "private signing keys must not be committed" in lower_text


def test_agents_contract_requires_descriptive_commit_messages() -> None:
    text = _agents_text()
    lower_text = text.lower()

    assert "commit message rules" in lower_text
    assert "do not include prompt numbers" in lower_text
    assert "mention the actual change" in lower_text
    assert "harden signed policy feed deployment" in lower_text
    assert "checkpoint after prompt 12" in lower_text

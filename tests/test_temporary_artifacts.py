from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORRUPT_GIT_SKIP_REASON = (
    "local .git metadata is unavailable/corrupt; clean archive validation covers exported artifacts"
)


def _git_metadata_is_corrupt(result: subprocess.CompletedProcess[str]) -> bool:
    stderr = (result.stderr or "").lower()
    return result.returncode != 0 and "index file corrupt" in stderr


def test_local_hand_off_notes_are_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "*handover*.md" in gitignore


def test_local_hand_off_notes_are_not_tracked_when_git_metadata_exists() -> None:
    if not (ROOT / ".git").exists():
        return

    result = subprocess.run(
        ["git", "-c", "safe.directory=*", "ls-files", "*handover*.md"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    if _git_metadata_is_corrupt(result):
        pytest.skip(CORRUPT_GIT_SKIP_REASON)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_corrupt_git_metadata_is_treated_as_unavailable_context() -> None:
    result = subprocess.CompletedProcess(
        args=["git", "ls-files"],
        returncode=128,
        stdout="",
        stderr="fatal: index file corrupt\n",
    )

    assert _git_metadata_is_corrupt(result)


def test_other_git_failures_are_not_hidden() -> None:
    result = subprocess.CompletedProcess(
        args=["git", "ls-files"],
        returncode=128,
        stdout="",
        stderr="fatal: not a git repository\n",
    )

    assert not _git_metadata_is_corrupt(result)

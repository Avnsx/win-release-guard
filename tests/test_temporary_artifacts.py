from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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

    assert result.returncode == 0
    assert result.stdout.strip() == ""

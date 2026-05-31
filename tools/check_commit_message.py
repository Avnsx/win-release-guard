from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence


MAX_SUBJECT_LENGTH = 72

BAD_EXACT_SUBJECTS = {
    "fix",
    "stuff",
    "changes",
    "change",
    "update",
    "updates",
    "misc",
    "wip",
    "checkpoint",
    "ai changes",
    "final final",
}

BAD_PATTERNS = (
    (re.compile(r"\bcheckpoint\b", re.IGNORECASE), "avoid checkpoint-style commit subjects"),
    (re.compile(r"\bprompt\s*#?\s*\d+\b", re.IGNORECASE), "do not include prompt numbers"),
    (re.compile(r"\bprompt\s+(?:done|fix|changes?|complete|completed)\b", re.IGNORECASE), "avoid prompt-style commit subjects"),
    (re.compile(r"\bai\s+(?:changes?|slop)\b", re.IGNORECASE), "avoid AI-style generic labels"),
    (re.compile(r"\bfinal\s+final\b", re.IGNORECASE), "avoid final-final labels"),
    (re.compile(r"^\s*fix\s+(?:stuff|things?|changes?)\s*$", re.IGNORECASE), "describe the actual fix"),
)


def subject_from_message(message: str) -> str:
    for line in message.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip():
            return line
    return ""


def validate_commit_message(message: str) -> list[str]:
    subject = subject_from_message(message)
    failures: list[str] = []

    if not subject:
        return ["commit subject is empty"]

    if subject != subject.strip():
        failures.append("commit subject has leading or trailing whitespace")

    clean_subject = subject.strip()
    if len(clean_subject) > MAX_SUBJECT_LENGTH:
        failures.append(f"commit subject is longer than {MAX_SUBJECT_LENGTH} characters")

    if clean_subject.lower() in BAD_EXACT_SUBJECTS:
        failures.append("commit subject is too generic")

    for pattern, message_text in BAD_PATTERNS:
        if pattern.search(clean_subject):
            failures.append(message_text)

    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", clean_subject)
    if len(words) < 3:
        failures.append("commit subject should mention the actual change")

    return failures


def read_latest_commit_message(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-c", "safe.directory=*", "log", "-1", "--pretty=%B"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "git log failed"
        raise RuntimeError(stderr)
    return result.stdout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate win-release-guard commit message hygiene.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--message", help="Commit message text to validate.")
    source.add_argument("--message-file", type=Path, help="File containing a commit message to validate.")
    args = parser.parse_args(argv)

    try:
        if args.message is not None:
            message = args.message
        elif args.message_file is not None:
            message = args.message_file.read_text(encoding="utf-8")
        else:
            message = read_latest_commit_message(Path.cwd())
    except Exception as exc:
        print(f"Commit message check failed: {exc}", file=sys.stderr)
        return 1

    failures = validate_commit_message(message)
    if failures:
        print("Commit message check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Commit message check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

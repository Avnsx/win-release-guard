from __future__ import annotations

from pathlib import Path

from tools import check_commit_message


def test_good_commit_messages_pass() -> None:
    good_messages = [
        "Harden signed policy feed deployment",
        "Polish Pages policy dashboard",
        "Validate public policy API endpoints",
        "Enforce secret scanning for policy artifacts",
        "Document final Pages feed verification",
        "Fix published URL metadata validation",
        "Preserve robots contract in generator",
    ]

    for message in good_messages:
        assert check_commit_message.validate_commit_message(message) == []


def test_bad_commit_messages_fail() -> None:
    bad_messages = [
        "checkpoint after prompt 12",
        "prompt 8 done",
        "fix",
        "stuff",
        "AI changes",
        "final final",
        "fix stuff",
    ]

    for message in bad_messages:
        assert check_commit_message.validate_commit_message(message), message


def test_commit_message_file_cli_passes(tmp_path: Path, capsys) -> None:
    message_file = tmp_path / "message.txt"
    message_file.write_text("Enforce secret scanning for policy artifacts\n", encoding="utf-8")

    assert check_commit_message.main(["--message-file", str(message_file)]) == 0
    captured = capsys.readouterr()
    assert "passed" in captured.out.lower()


def test_commit_message_cli_fails_for_prompt_number(capsys) -> None:
    assert check_commit_message.main(["--message", "prompt 13 done"]) == 1
    captured = capsys.readouterr()
    assert "prompt numbers" in captured.err.lower()

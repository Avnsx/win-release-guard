from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from tools import sync_source_diagnostics_issues as sync_tool


class FakeGitHubClient:
    def __init__(
        self,
        search_results: dict[str, list[dict[str, Any]]] | None = None,
        *,
        open_managed_issues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.search_results = search_results or {}
        self.open_managed_issues = open_managed_issues or []
        self.searches: list[tuple[str, str]] = []
        self.listed: list[tuple[str, tuple[str, ...]]] = []
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.updated: list[tuple[str, int, dict[str, Any]]] = []
        self.comments: list[tuple[str, int, str]] = []
        self.closed: list[tuple[str, int, str]] = []

    def search_issues(self, repository: str, diagnostic_id: str) -> list[dict[str, Any]]:
        self.searches.append((repository, diagnostic_id))
        return [dict(item) for item in self.search_results.get(diagnostic_id, [])]

    def list_open_managed_issues(self, repository: str, labels: list[str]) -> list[dict[str, Any]]:
        self.listed.append((repository, tuple(labels)))
        return [dict(item) for item in self.open_managed_issues]

    def create_issue(self, repository: str, *, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        self.created.append((repository, {"title": title, "body": body, "labels": labels}))
        return {"number": len(self.created), "state": "open"}

    def update_issue(
        self,
        repository: str,
        issue_number: int,
        *,
        title: str,
        body: str,
        labels: list[str],
        state: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title, "body": body, "labels": labels}
        if state is not None:
            payload["state"] = state
        self.updated.append((repository, issue_number, payload))
        return {"number": issue_number, "state": "open"}

    def comment_issue(self, repository: str, issue_number: int, *, body: str) -> dict[str, Any]:
        self.comments.append((repository, issue_number, body))
        return {"id": len(self.comments)}

    def close_issue(self, repository: str, issue_number: int, *, state_reason: str = "completed") -> dict[str, Any]:
        self.closed.append((repository, issue_number, state_reason))
        return {"number": issue_number, "state": "closed"}


def _event(
    diagnostic_id: str,
    *,
    severity: str = "warning",
    kind: str = "atom_newer_than_release_history",
    message: str = "Atom feed reports a newer baseline build.",
) -> dict[str, Any]:
    return {
        "id": diagnostic_id,
        "severity": severity,
        "kind": kind,
        "release": "25H2",
        "build_family": 26200,
        "build": "26200.8461",
        "kb_article": "KB5089600",
        "affects_broad_target": True,
        "affects_required_baseline": severity == "warning",
        "message": message,
    }


def _policy(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {"source_diagnostics": {"events": events}}


def test_issue_sync_deduplicates_by_diagnostic_id_before_creating() -> None:
    diagnostic_id = "wrg-source-diagnostic-v1:1111111111111111"
    diagnostics = sync_tool.diagnostics_from_policy(
        _policy([_event(diagnostic_id), _event(diagnostic_id)])
    )
    client = FakeGitHubClient()

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        request_delay_seconds=0,
    )

    assert summary.created == 1
    assert len(client.created) == 1
    repository, payload = client.created[0]
    assert repository == "Avnsx/win11_release_guard"
    assert payload["labels"] == ["internals: warning"]
    assert f"<!-- wrg-source-diagnostic-id: {diagnostic_id} -->" in payload["body"]
    assert f"Source diagnostic ID: `{diagnostic_id}`" in payload["body"]


def test_issue_sync_maps_exact_labels_for_all_enabled_severities() -> None:
    events = [
        _event("wrg-source-diagnostic-v1:1111111111111111", severity="notice"),
        _event("wrg-source-diagnostic-v1:2222222222222222", severity="warning"),
        _event("wrg-source-diagnostic-v1:3333333333333333", severity="error"),
    ]
    diagnostics = sync_tool.diagnostics_from_policy(_policy(events))
    client = FakeGitHubClient()

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        create_limit=10,
        request_delay_seconds=0,
    )

    assert summary.created == 3
    assert [payload["labels"] for _, payload in client.created] == [
        ["internals: notices"],
        ["internals: warning"],
        ["internals: error"],
    ]


def test_issue_sync_updates_and_comments_when_open_issue_matches() -> None:
    diagnostic_id = "wrg-source-diagnostic-v1:4444444444444444"
    client = FakeGitHubClient({diagnostic_id: [{"number": 42, "state": "open"}]})
    diagnostics = sync_tool.diagnostics_from_policy(_policy([_event(diagnostic_id)]))

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        request_delay_seconds=0,
    )

    assert summary.created == 0
    assert summary.updated == 1
    assert summary.commented == 1
    assert client.created == []
    assert client.updated[0][1] == 42
    assert client.updated[0][2]["labels"] == ["internals: warning"]
    assert diagnostic_id in client.updated[0][2]["body"]
    assert diagnostic_id in client.comments[0][2]


def test_issue_sync_reopens_matching_closed_issue_by_default() -> None:
    diagnostic_id = "wrg-source-diagnostic-v1:5555555555555555"
    client = FakeGitHubClient({diagnostic_id: [{"number": 51, "state": "closed"}]})
    diagnostics = sync_tool.diagnostics_from_policy(_policy([_event(diagnostic_id)]))

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        request_delay_seconds=0,
    )

    assert summary.reopened == 1
    assert summary.commented == 1
    assert client.created == []
    assert client.updated[0][1] == 51
    assert client.updated[0][2]["state"] == "open"
    assert diagnostic_id in client.comments[0][2]
    assert summary.issue_status[diagnostic_id] == {
        "number": 51,
        "state": "open",
        "url": "https://github.com/Avnsx/win11_release_guard/issues/51",
    }


def test_issue_sync_can_skip_matching_closed_issue_when_reopen_disabled() -> None:
    diagnostic_id = "wrg-source-diagnostic-v1:5555555555555555"
    client = FakeGitHubClient({diagnostic_id: [{"number": 51, "state": "closed"}]})
    diagnostics = sync_tool.diagnostics_from_policy(_policy([_event(diagnostic_id)]))

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        request_delay_seconds=0,
        reopen_closed=False,
    )

    assert summary.skipped_closed == 1
    assert client.created == []
    assert client.updated == []
    assert client.comments == []


def test_issue_sync_caps_new_issue_creation_per_run() -> None:
    diagnostics = sync_tool.diagnostics_from_policy(
        _policy(
            [
                _event("wrg-source-diagnostic-v1:6666666666666666"),
                _event("wrg-source-diagnostic-v1:7777777777777777"),
                _event("wrg-source-diagnostic-v1:8888888888888888"),
            ]
        )
    )
    client = FakeGitHubClient()

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        create_limit=2,
        request_delay_seconds=0,
    )

    assert summary.created == 2
    assert summary.skipped_cap == 1
    assert len(client.created) == 2


def test_notice_diagnostics_sync_by_default_with_explicit_opt_out() -> None:
    notice = _event("wrg-source-diagnostic-v1:9999999999999999", severity="notice")

    assert [diagnostic.diagnostic_id for diagnostic in sync_tool.diagnostics_from_policy(_policy([notice]))] == [
        "wrg-source-diagnostic-v1:9999999999999999"
    ]
    assert sync_tool.diagnostics_from_policy(_policy([notice]), include_notices=False) == []


def test_issue_sync_closes_stale_open_managed_issue() -> None:
    active_id = "wrg-source-diagnostic-v1:1212121212121212"
    stale_id = "wrg-source-diagnostic-v1:3434343434343434"
    client = FakeGitHubClient(
        open_managed_issues=[
            {
                "number": 77,
                "state": "open",
                "body": f"<!-- wrg-source-diagnostic-id: {stale_id} -->",
                "labels": [{"name": "internals: notices"}],
            },
            {
                "number": 78,
                "state": "open",
                "body": f"<!-- wrg-source-diagnostic-id: {active_id} -->",
                "labels": [{"name": "internals: warning"}],
            },
        ]
    )
    diagnostics = sync_tool.diagnostics_from_policy(_policy([_event(active_id)]))

    summary = sync_tool.sync_diagnostics(
        diagnostics,
        repository="Avnsx/win11_release_guard",
        client=client,
        create_limit=0,
        request_delay_seconds=0,
    )

    assert summary.closed == 1
    assert client.closed == [("Avnsx/win11_release_guard", 77, "completed")]
    assert stale_id in client.comments[0][2]
    assert client.listed == [("Avnsx/win11_release_guard", tuple(sync_tool.MANAGED_LABELS))]


def test_issue_sync_writes_static_issue_status_output(tmp_path: Path) -> None:
    diagnostic_id = "wrg-source-diagnostic-v1:abababababababab"
    client = FakeGitHubClient({diagnostic_id: [{"number": 42, "state": "open"}]})
    policy_path = tmp_path / "policy.json"
    status_path = tmp_path / "issue-status.json"
    policy_path.write_text(json.dumps(_policy([_event(diagnostic_id)])) + "\n", encoding="utf-8")
    stdout = io.StringIO()

    code = sync_tool.main(
        [
            "--policy-file",
            str(policy_path),
            "--repository",
            "Avnsx/win11_release_guard",
            "--issue-status-output",
            str(status_path),
            "--request-delay-seconds",
            "0",
            "--no-close-stale",
        ],
        client=client,
        environ={"GITHUB_TOKEN": "safe-test-token-value-that-must-not-print"},
        stdout=stdout,
    )

    assert code == 0
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload == {
        "issue_status": {
            diagnostic_id: {
                "number": 42,
                "state": "open",
                "url": "https://github.com/Avnsx/win11_release_guard/issues/42",
            }
        }
    }


def test_dry_run_does_not_mutate_or_print_token(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(_policy([_event("wrg-source-diagnostic-v1:aaaaaaaaaaaaaaaa")])) + "\n",
        encoding="utf-8",
    )
    client = FakeGitHubClient()
    stdout = io.StringIO()
    stderr = io.StringIO()
    secret_token = "safe-test-token-value-that-must-not-print"

    code = sync_tool.main(
        [
            "--policy-file",
            str(policy_path),
            "--repository",
            "Avnsx/win11_release_guard",
            "--dry-run",
            "--request-delay-seconds",
            "0",
        ],
        client=client,
        environ={"GITHUB_TOKEN": secret_token, "GITHUB_REPOSITORY": "Avnsx/win11_release_guard"},
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 0
    assert client.created == []
    assert client.updated == []
    assert client.comments == []
    output = stdout.getvalue() + stderr.getvalue()
    assert "Would create issue for wrg-source-diagnostic-v1:aaaaaaaaaaaaaaaa." in output
    assert secret_token not in output
    assert "GITHUB_TOKEN" not in output

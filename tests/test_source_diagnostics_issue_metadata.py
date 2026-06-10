from __future__ import annotations

from html.parser import HTMLParser

from win11_release_guard.models import ReleasePolicy, ReleasePolicyEntry
import win11_release_guard.policy_generator as policy_generator_module
from win11_release_guard.policy_generator import render_policy_index


def _assert_no_external_or_client_auth(index: str) -> None:
    lower = index.lower()
    assert "script src" not in lower
    assert 'rel="stylesheet"' not in lower
    assert "@import" not in lower
    assert "api.github.com" not in lower
    assert "github_token" not in lower
    assert "gh_token" not in lower
    assert "authorization:" not in lower
    assert "bearer " not in lower
    assert "fetch(" not in lower
    assert "xmlhttprequest" not in lower


def _diagnostic_event() -> dict[str, object]:
    return {
        "severity": "warning",
        "kind": "atom_newer_than_release_history",
        "release": "25H2",
        "build_family": 26200,
        "build": "26200.8461",
        "kb_article": "KB5089600",
        "affects_broad_target": True,
        "affects_required_baseline": True,
        "updated": "2026-06-09T18:00:00Z",
        "message": "Atom feed reports a newer baseline build.",
    }


def _diagnostic_id() -> str:
    return policy_generator_module._source_diagnostic_id_for_event(_diagnostic_event())


def _policy_with_issue_status(issue_status: object | None = None) -> ReleasePolicy:
    source_diagnostics: dict[str, object] = {
        "event_counts": {"notice": 0, "warning": 1, "error": 0},
        "events": [_diagnostic_event()],
    }
    if issue_status is not None:
        source_diagnostics["issue_status"] = issue_status
    return ReleasePolicy(source_diagnostics=source_diagnostics)


def test_source_diagnostic_rows_without_issue_metadata_render_normally() -> None:
    index = render_policy_index(_policy_with_issue_status(), policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert '<article class="diag-row warning" data-diagnostic-severity="warning" data-diagnostic-id="' in index
    assert "Atom feed reports a newer baseline build." in index
    assert '<a class="diag-ticket-link"' not in index
    assert "#Ticket 42" not in index
    assert "data-diagnostic-filter" in index
    assert "guard('source diagnostics filter'" in index
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_rows_with_issue_metadata_render_safe_link_and_status() -> None:
    diagnostic_id = _diagnostic_id()
    index = render_policy_index(
        _policy_with_issue_status(
            {
                diagnostic_id: {
                    "number": 42,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/42",
                }
            }
        ),
        policy_bytes=None,
        signature=None,
    )
    HTMLParser().feed(index)

    assert f'data-diagnostic-id="{diagnostic_id}"' in index
    assert (
        '<a class="diag-ticket-link" '
        'href="https://github.com/Avnsx/win11_release_guard/issues/42" '
        'aria-label="GitHub issue 42 status open">'
    ) in index
    assert "#Ticket 42" in index
    assert "diag-ticket-link-icon" in index
    assert '<svg class="github-icon"' in index
    assert ".diag-row:hover .diag-ticket-link,.diag-row:focus-within .diag-ticket-link" in index
    assert "opacity:0;pointer-events:none" in index
    assert "data-diagnostic-filter-root" in index
    assert "row.hidden=!match" in index
    assert '<article class="diag-row warning" data-diagnostic-severity="warning" hidden' not in index
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_ticket_link_is_public_issue_anchor_without_auth_parameters() -> None:
    diagnostic_id = _diagnostic_id()
    index = render_policy_index(
        _policy_with_issue_status(
            {
                diagnostic_id: {
                    "number": 42,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/42",
                }
            }
        ),
        policy_bytes=None,
        signature=None,
    )
    HTMLParser().feed(index)

    assert 'href="https://github.com/Avnsx/win11_release_guard/issues/42"' in index
    assert "https://api.github.com" not in index
    assert "issues/42?" not in index
    assert "issues/42#" not in index
    assert "token=" not in index.lower()
    assert "authorization" not in index.lower()
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_issue_metadata_ignores_invalid_issue_urls() -> None:
    diagnostic_id = _diagnostic_id()
    index = render_policy_index(
        _policy_with_issue_status(
            {
                diagnostic_id: {
                    "number": 42,
                    "state": "open",
                    "url": "https://github.com/Avnsx/not-the-repo/issues/42",
                }
            }
        ),
        policy_bytes=None,
        signature=None,
    )
    HTMLParser().feed(index)

    assert f'data-diagnostic-id="{diagnostic_id}"' in index
    assert '<a class="diag-ticket-link"' not in index
    assert "#Ticket 42" not in index
    assert "not-the-repo" not in index
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_issue_metadata_builds_canonical_link_from_issue_number() -> None:
    diagnostic_id = _diagnostic_id()
    index = render_policy_index(
        _policy_with_issue_status({diagnostic_id: {"number": "43", "state": "open"}}),
        policy_bytes=None,
        signature=None,
    )
    HTMLParser().feed(index)

    assert 'href="https://github.com/Avnsx/win11_release_guard/issues/43"' in index
    assert 'aria-label="GitHub issue 43 status open"' in index
    assert "#Ticket 43" in index
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_issue_metadata_suppresses_closed_issue_rows() -> None:
    diagnostic_id = _diagnostic_id()
    index = render_policy_index(
        _policy_with_issue_status({diagnostic_id: {"number": "43", "state": "closed"}}),
        policy_bytes=None,
        signature=None,
    )
    HTMLParser().feed(index)

    assert f'data-diagnostic-id="{diagnostic_id}"' not in index
    assert "Atom feed reports a newer baseline build." not in index
    assert 'href="https://github.com/Avnsx/win11_release_guard/issues/43"' not in index
    assert "#Ticket 43" not in index
    assert "warning diagnostic entry reported without structured row details" not in index
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_issue_metadata_is_ignored_for_derived_rows() -> None:
    excluded_entry = ReleasePolicyEntry(
        version="26H1",
        build_family=26200,
        latest_build="26200.1000",
        reason="new devices only",
    )
    preview_policy = ReleasePolicy(
        excluded_for_existing_devices=(excluded_entry,),
        source_diagnostics={"event_counts": {"notice": 0, "warning": 0, "error": 0}},
    )
    clear_id = policy_generator_module._source_diagnostic_row_id(
        policy_generator_module._clear_source_diagnostic_row()
    )
    excluded_id = policy_generator_module._source_diagnostic_row_id(
        policy_generator_module._excluded_release_diagnostic_rows(preview_policy)[0]
    )
    policy = ReleasePolicy(
        excluded_for_existing_devices=(excluded_entry,),
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 0, "error": 0},
            "issue_status": {
                clear_id: {
                    "number": 44,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/44",
                },
                excluded_id: {
                    "number": 45,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/45",
                }
            },
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert f'data-diagnostic-id="{clear_id}"' in index
    assert f'data-diagnostic-id="{excluded_id}"' in index
    assert "No source issues reported" in index
    assert "26H1 excluded for existing devices" in index
    assert "#Ticket 44" not in index
    assert "#Ticket 45" not in index
    assert '<a class="diag-ticket-link"' not in index
    _assert_no_external_or_client_auth(index)


def test_source_diagnostic_ticket_links_render_only_for_warning_and_error_events() -> None:
    events = [
        {
            "severity": "notice",
            "kind": "notice_probe",
            "message": "Notice diagnostic still exists.",
        },
        {
            "severity": "warning",
            "kind": "warning_probe",
            "message": "Warning diagnostic still exists.",
        },
        {
            "severity": "error",
            "kind": "error_probe",
            "message": "Error diagnostic still exists.",
        },
    ]
    base_policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 1, "warning": 1, "error": 1},
            "events": events,
        }
    )
    rows = policy_generator_module._source_diagnostic_rows(base_policy, generated_age_days=0)
    issue_status = {
        policy_generator_module._source_diagnostic_row_id(row): {
            "number": index,
            "state": "open",
            "url": f"https://github.com/Avnsx/win11_release_guard/issues/{index}",
        }
        for index, row in enumerate(rows, start=50)
    }
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 1, "warning": 1, "error": 1},
            "events": events,
            "issue_status": issue_status,
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert index.count('class="diag-ticket-link"') == 2
    for severity in ("notice", "warning", "error"):
        assert f'<article class="diag-row {severity}" data-diagnostic-severity="{severity}"' in index
    assert "Notice diagnostic still exists." in index
    assert "#Ticket 50" not in index
    assert "https://github.com/Avnsx/win11_release_guard/issues/50" not in index
    for number in (51, 52):
        assert f"#Ticket {number}" in index
        assert f"https://github.com/Avnsx/win11_release_guard/issues/{number}" in index
    _assert_no_external_or_client_auth(index)

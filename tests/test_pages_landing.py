from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from html.parser import HTMLParser
import re
from pathlib import Path

from win11_release_guard.models import ReleasePolicy, ReleasePolicyEntry
import win11_release_guard.policy_generator as policy_generator_module
from win11_release_guard.policy_generator import generate_policy, render_policy_index, write_policy_outputs


FIXTURES = Path("tests/fixtures")
CURATED_26H1_SUMMARY = (
    "26H1 is excluded for existing devices because Microsoft scopes it to new devices and does not offer "
    "it as an in-place update from 24H2/25H2."
)
REMOVED_SCHEMA_PANEL_LABELS = (
    "API " + "and schema",
    "Policy " + "schema",
    "Reader " + "range",
)
FRESHNESS_SCRIPT_RE = re.compile(
    r'<script type="application/json" id="policy-freshness-data">(.*?)</script>',
    re.DOTALL,
)


def _render_landing(tmp_path: Path) -> str:
    policy = generate_policy(
        release_health_html=(FIXTURES / "windows11-release-health.html").read_text(encoding="utf-8"),
        atom_feed_xml=(FIXTURES / "windows11-atom.xml").read_text(encoding="utf-8"),
        generated_at_utc="2026-05-31T14:11:50+00:00",
        signature_status="valid",
    )
    write_policy_outputs(policy, output_dir=tmp_path, write_index=True)
    return (tmp_path / "index.html").read_text(encoding="utf-8")


def _freshness_data(index: str) -> dict:
    match = FRESHNESS_SCRIPT_RE.search(index)
    assert match is not None
    return json.loads(match.group(1))


def test_excluded_release_summary_uses_curated_26h1_copy(tmp_path: Path) -> None:
    index = _render_landing(tmp_path)

    assert "existing devi." not in index
    assert "26H1 excluded for existing devices" in index
    assert CURATED_26H1_SUMMARY in index
    assert "Release policy notes" not in index
    assert "release-note" not in index
    assert "Release policy" in index


def test_pages_index_shows_generated_age_and_source_diagnostics_summary(tmp_path: Path) -> None:
    index = _render_landing(tmp_path)

    assert "<title>Windows 11 Release Guard</title>" in index
    assert "<h1>Windows 11 Release Guard</h1>" in index
    assert 'id="policy-status-pill"' not in index
    assert "Generated age" not in index
    assert "Policy Feed Currency" in index
    assert "Published feed age" in index
    assert "days at render-time fallback" in index
    assert "Browser recalculates published policy feed age from the GitHub Actions generated timestamp" in index
    assert "Date.now" in index
    assert "Published policy feed currency: Unknown" in index
    assert ".freshness-state.current{color:var(--ok)" in index
    assert ".freshness-state.refresh-due{color:var(--warn)" in index
    assert ".freshness-state.stale{color:var(--err)" in index
    assert ".freshness-state.unknown{color:var(--unknown)" in index
    assert "navigator.clipboard.writeText" in index
    assert "document.execCommand('copy')" in index
    assert "reportUiError" in index
    assert "data-ui-last-error" in index
    assert "shutdownUi" in index
    assert "pagehide" in index
    assert "beforeunload" in index
    assert "safeSetTimeout" in index
    assert "safeSetInterval" in index
    assert "safeRequestFrame" in index
    assert "safeCancelFrame" in index
    assert "button.isConnected" in index
    assert "nav.isConnected" in index
    assert "passive:true" in index
    assert "header nav pointer" in index
    assert "freshness update" in index
    assert "epoch-copy" in index
    assert 'aria-label="Copy policy generated UTC epoch millisecond timestamp 1780236710000"' in index
    assert 'data-epoch="1780236710000"' in index
    assert "Sunday, 31 May 2026, 14:11:50 UTC" in index
    assert "<dt>UTC</dt>" not in index
    assert "<dt>Time (UTC):</dt>" in index
    assert "<dt>Published feed age:</dt>" in index
    assert "<dt>Workflow refresh:</dt>" in index
    assert "<dt>Fetched:</dt>" in index
    assert "<dt>Bytes:</dt>" in index
    assert "<dt>Algorithm</dt>" in index
    assert "<dt>key_id</dt>" in index
    assert "<dt>Policy SHA-256</dt>" in index
    assert "<dt>Signature status</dt>" in index
    assert "Refresh Due" in index
    assert "Stale" in index
    assert "Current" in index
    assert "Published policy feed is within the 14-day maintenance threshold." in index
    assert "Published policy feed refresh is due. Verify automation health before treating this data as production-current." in index
    assert "Published policy feed is stale. Do not treat this data as production-current until automation refresh succeeds." in index
    assert "Workflow refresh" in index
    assert "GitHub workflow static feed generation" in index
    assert "Release Health fetched" not in index
    assert "Atom feed fetched" not in index
    assert "Berlin, Germany" in index
    assert "Program versioning" not in index
    assert "Program Version" in index
    assert 'class="header-actions"' in index
    assert 'class="header-nav"' in index
    assert 'class="nav-hover-label"' in index
    assert "nav-binoculars" not in index
    assert 'aria-label="Header navigation"' in index
    assert 'id="policy-summary"' in index
    assert 'href="https://avnsx.github.io/win11_release_guard/"' in index
    assert "--item-size:38px" in index
    assert "@media(max-width:900px)" in index
    assert ".nav-hover-label{display:none}" in index
    assert 'data-nav-label="Dashboard"' in index
    assert "Dashboard" in index
    assert 'data-nav-label="Write a Issue Ticket"' in index
    assert "Write a Issue Ticket" in index
    assert "https://github.com/Avnsx/win11_release_guard/issues/new" in index
    assert 'data-nav-label="Wiki"' in index
    assert "Wiki" in index
    assert "https://github.com/Avnsx/win11_release_guard/wiki" in index
    assert "initHeaderNav" in index
    assert "requestAnimationFrame" in index
    assert "pointermove" in index
    assert "--label-x" in index
    assert "Bookmarks" not in index
    assert "Blogs" not in index
    assert "E-books" not in index
    assert "Account" not in index
    assert "Menu" not in index
    program_version = policy_generator_module.GENERATOR_VERSION.rsplit("/", 1)[-1]
    assert f"https://github.com/Avnsx/win11_release_guard/releases/tag/v{program_version}" in index
    assert "GitHub release tag" not in index
    assert "Logic ID" not in index
    assert "Policy generated by" not in index
    assert "public /api/v1 lane" not in index
    assert "signed policy document schema" not in index
    assert "API version" not in index
    assert "Policy Schema Version" not in index
    for removed_label in REMOVED_SCHEMA_PANEL_LABELS:
        assert removed_label not in index
    assert "Source diagnostics" in index
    assert "diag-feed" in index
    assert 'aria-label="Source diagnostic event feed"' in index
    assert "Notices" in index
    assert "Warnings" in index
    assert "Errors" in index
    assert ".diag-tile.notice{border-color:#bfdbfe" in index
    assert ".diag-tile.notice strong{color:var(--blue)}" in index
    assert ".severity-badge.notice{color:var(--blue-strong)" in index
    assert ".diag-tile.warning{border-color:#f6d493" in index
    assert ".diag-tile.warning span{color:var(--warn);font-weight:650}" in index
    assert ".diag-tile.error{border-color:#f6b7ad" in index
    assert ".diag-tile.error span{color:var(--err);font-weight:650}" in index
    assert ".diag-row.warning{border-color:#f6d493" in index
    assert ".diag-row.error{border-color:#f6b7ad" in index
    assert ".diag-feed{margin-top:2px;height:340px;min-height:340px;max-height:340px;overflow-y:scroll" in index
    assert "scrollbar-gutter:stable" in index
    assert "background:linear-gradient(180deg,#f6f7f9,#eef1f5)" in index
    assert "scrollbar-color:#a8b0bc #eef1f5" in index
    assert ".diag-feed::-webkit-scrollbar-thumb" in index
    assert ".diag-events{display:grid;gap:10px;padding:2px 2px 24px}" in index
    assert "Signature" in index
    assert "Signature metadata" in index
    assert "Signature status" in index
    assert "signature-head" in index
    assert "signature-status-card" in index
    assert "Document trust state" in index
    assert "Detached signature metadata for the published policy artifact." in index
    assert "signature-kv" in index
    assert ".signature-panel{position:relative;overflow:hidden;display:flex;flex-direction:column" in index
    assert ".signature-panel:before{content:'';position:absolute;inset:0 0 auto;height:3px" in index
    assert ".signature-kv div{display:grid;grid-template-columns:minmax(104px,30%) minmax(0,1fr)" in index
    assert "<h2>Sources</h2>" not in index
    assert "Programmatic JSON endpoint for automation and fleet dashboards." not in index
    assert "Independent Windows release-policy dashboard. Not affiliated with Microsoft." in index
    assert "&copy; 2026 Mikail (&quot;Avnsx&quot;) C. Maintained as an open-source project." in index
    assert "Source code and documentation are available on" in index
    assert "provided under the" in index
    assert "footer-legal" not in index
    assert "footer-repo-line" not in index
    assert "footer-symbol" not in index
    assert "</span></a>.</span></p>" not in index
    assert 'class="footer-github" href="https://github.com/Avnsx/win11_release_guard"' in index
    assert "<span>GitHub</span>" in index
    assert (
        'class="footer-license-basic" href="https://github.com/Avnsx/win11_release_guard/blob/main/LICENSE.txt"'
        in index
    )
    assert "GPL-3.0 license" in index
    assert "GPL-3.0 license</a>.</p>" not in index
    assert 'class="footer-license"' not in index
    assert "github-icon" in index
    assert ">LICENSE.txt<" not in index
    assert "sources-panel" not in index
    assert "source-health" in index
    assert "source-tile" in index
    assert "source-status" in index
    assert "endpoint-pill" not in index
    assert "api-endpoints" in index
    assert "api-endpoint-row" in index
    assert "Signed policy JSON" in index
    assert "Primary signed policy document used by automation and fleet dashboards." in index
    assert "Detached signature" in index
    assert "Ed25519 signature that lets clients verify the policy before trusting it." in index
    assert "Policy manifest" in index
    assert "Compact metadata for hashes, freshness thresholds, source state, and API aliases." in index
    assert "API v1 policy alias" in index
    assert "Backward-compatible policy endpoint for stable reader integrations." in index
    assert "API v1 manifest alias" in index
    assert "Backward-compatible manifest endpoint for stable reader integrations." in index
    assert '<section class="panel span-5 signature-panel">' in index
    assert '<section class="panel span-7 programmatic-api">' in index
    assert ".programmatic-api{grid-column:6/span 7;grid-row:3}" in index
    assert ".signature-panel{grid-column:1/span 5;grid-row:3}" in index
    assert ".api-endpoint-row{grid-template-columns:1fr}" in index
    assert ".signature-panel,.programmatic-api{grid-column:1/-1}" in index
    assert "Programmatic API" in index
    assert "script src" not in index.lower()
    freshness = _freshness_data(index)
    assert freshness["generated_at_utc"] == "2026-05-31T14:11:50+00:00"
    assert freshness["generated_at_epoch_s"] == 1780236710
    assert freshness["warn_after_epoch_s"] == 1781446310
    assert freshness["stale_after_epoch_s"] == 1784124710
    assert freshness["max_ok_age_seconds"] == 14 * 24 * 60 * 60
    assert freshness["warning_age_seconds"] == 14 * 24 * 60 * 60
    assert freshness["strict_stale_age_seconds"] == 45 * 24 * 60 * 60
    assert freshness["freshness_policy"]["client_recomputes_age"] is True


def test_pages_index_signature_trust_pulse_is_lightweight_and_can_render_red() -> None:
    policy = ReleasePolicy(metadata={"signature_status": "invalid"})

    index = render_policy_index(
        policy,
        policy_bytes=b'{"policy":"demo"}',
        signature={"algorithm": "ed25519", "key_id": "test-key", "signature": "bad"},
    )
    HTMLParser().feed(index)

    assert "html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}" in index
    assert 'class="trust-indicator error">Signed policy trust</span>' in index
    assert '<section class="panel span-5 signature-panel error">' in index
    assert 'class="signature-status-card error"' in index
    assert "font-size:12px;font-weight:650;white-space:nowrap" in index
    assert (
        ".trust-indicator.error{color:var(--err);background:linear-gradient(180deg,var(--err-soft),#fff8f6);"
        "border-color:#f6b7ad"
        in index
    )
    assert "--trust-ring:rgba(180,35,24,.2)" in index
    assert ".signature-panel.error{border-color:#f6b7ad;background:linear-gradient(180deg,#fff7f5,#fffdfc)}" in index
    assert ".signature-panel.error:before{background:linear-gradient(90deg,var(--err),rgba(180,35,24,.22))}" in index
    assert ".signature-status-card.error{border-color:#f6b7ad;background:linear-gradient(135deg,var(--err-soft),#fff8f6)}" in index
    assert "box-shadow:0 0 0 5px var(--trust-ring)" in index
    assert "width:9px;height:9px" in index
    assert "animation:trustPulse 2.2s cubic-bezier(.4,0,.2,1) infinite" in index
    assert "will-change:transform" in index
    keyframes = index.split("@keyframes trustPulse", 1)[1].split(".trust-indicator.warning", 1)[0]
    assert "transform:scale(1.7)" in keyframes
    assert "transform:scale(1.18)" in keyframes
    assert "box-shadow" not in keyframes
    assert "animation:none!important" in index


def test_pages_index_signature_boxes_hover_without_double_animating_api_rows() -> None:
    index = render_policy_index(ReleasePolicy(), policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert (
        ".signature-kv div{display:grid;grid-template-columns:minmax(104px,30%) minmax(0,1fr);"
        "gap:12px;align-items:center;border:1px solid #d5e2f0;border-radius:8px;"
        "background:linear-gradient(180deg,#fbfdff,#f5f8fc);padding:10px 12px;"
        "box-shadow:inset 0 1px 0 rgba(255,255,255,.7);"
        "transition:transform .16s ease,border-color .16s ease,background-color .16s ease}"
        in index
    )
    assert ".signature-kv dd{margin:0;color:#172033;font-weight:560;line-height:1.25;overflow-wrap:anywhere}" in index
    assert ".signature-kv .mono{font-size:13px;font-weight:560}" in index
    assert (
        ".signature-kv div:hover{border-color:#b8c9dd;background:#fff;"
        "box-shadow:0 7px 16px rgba(31,79,143,.07);transform:translateY(-1px)}"
        in index
    )
    assert (
        ".api-endpoint-row{display:grid;grid-template-columns:minmax(0,1fr) auto;"
        "gap:10px;align-items:center;border:1px solid var(--line);border-radius:8px;"
        "background:linear-gradient(180deg,#f8fafc,#f3f6fa);padding:10px 11px;"
        "color:inherit;text-decoration:none}"
        in index
    )
    assert ".api-endpoint-row:hover{border-color:#b8c9dd;background:#ffffff;text-decoration:none}" in index
    api_base_rule = index.split(".api-endpoint-row{", 1)[1].split("}", 1)[0]
    api_hover_rule = index.split(".api-endpoint-row:hover{", 1)[1].split("}", 1)[0]
    assert "transition:" not in api_base_rule
    assert "transform:" not in api_hover_rule
    assert "box-shadow:" not in api_hover_rule
    assert ".api-endpoint-row:focus-visible{outline:3px solid rgba(0,120,212,.28)" in index
    assert ".signature-kv div:hover{transform:none!important}" in index


def test_pages_index_source_diagnostics_empty_state_is_compact() -> None:
    policy = ReleasePolicy(
        source_diagnostics={"event_counts": {"notice": 0, "warning": 0, "error": 0}},
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "No source issues reported" in index
    assert "Release Health, Atom feed, parser, and freshness checks have no warning or error events." in index
    assert "0</strong><span>Notices" in index
    assert "0</strong><span>Warnings" in index
    assert "0</strong><span>Errors" in index
    assert '<article class="diag-row notice">' in index
    assert "diag-feed" in index
    assert "diag-events-empty" in index
    assert "No warnings" in index
    assert "No errors" in index
    assert "26H1 excluded for existing devices" not in index
    assert "diag-empty" not in index


def test_pages_index_excluded_release_notice_is_data_driven() -> None:
    policy = ReleasePolicy(
        excluded_for_existing_devices=(
            ReleasePolicyEntry(
                version="26H1",
                build_family=26200,
                latest_build="26200.1000",
                reason="new devices only",
            ),
        ),
        source_diagnostics={"event_counts": {"notice": 0, "warning": 0, "error": 0}},
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "Release policy notes" not in index
    assert "release-note" not in index
    assert "1</strong><span>Notices" in index
    assert "0</strong><span>Warnings" in index
    assert "0</strong><span>Errors" in index
    assert "No source issues reported" in index
    assert "26H1 excluded for existing devices" in index
    assert "Release policy" in index
    assert "Notice" in index
    assert "Release 26H1" in index
    assert "Existing devices" in index
    assert index.find("No source issues reported") < index.find("26H1 excluded for existing devices")


def test_pages_index_source_diagnostics_render_structured_warning_event() -> None:
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 1, "error": 0},
            "events": [
                {
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
            ],
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert '<article class="diag-row warning">' in index
    assert "Atom Newer Than Release History" in index
    assert "Atom feed" in index
    assert "Warning" in index
    assert "Release 25H2" in index
    assert "Build 26200.8461" in index
    assert "KB5089600" in index
    assert "Required baseline" in index
    assert "Atom feed reports a newer baseline build." in index
    assert '<div class="diag-tile warning"><strong>1</strong><span>Warnings</span></div>' in index
    assert '<span class="severity-badge warning">Warning</span>' in index


def test_pages_index_source_diagnostics_render_warning_and_error_color_states() -> None:
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 1, "error": 1},
            "events": [
                {
                    "severity": "warning",
                    "kind": "current_versions_lag_release_history",
                    "release": "25H2",
                    "build": "26200.8461",
                    "message": "Current Versions is behind Release History.",
                },
                {
                    "severity": "error",
                    "kind": "missing_broad_target_baseline",
                    "release": "25H2",
                    "build_family": 26200,
                    "message": "Required baseline cannot be derived.",
                },
            ],
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert '<div class="diag-tile warning"><strong>1</strong><span>Warnings</span></div>' in index
    assert '<div class="diag-tile error"><strong>1</strong><span>Errors</span></div>' in index
    assert '<article class="diag-row warning">' in index
    assert '<article class="diag-row error">' in index
    assert '<span class="severity-badge warning">Warning</span>' in index
    assert '<span class="severity-badge error">Error</span>' in index
    assert "Current Versions Lag Release History" in index
    assert "Missing Broad Target Baseline" in index
    assert "Current Versions is behind Release History." in index
    assert "Required baseline cannot be derived." in index


def test_pages_index_renderer_tolerates_sparse_legacy_policy() -> None:
    policy = ReleasePolicy(
        generated_at_utc=None,
        source_urls=("https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information?probe=<unsafe>",),
        generator_version=None,
        source_diagnostics={
            "event_counts": {"notice": "3", "warning": "not-a-number", "error": -1},
            "release_health_html": {"bytes": "not-a-number"},
        },
        validation_warnings=("Rendered warning <without raw html>",),
        min_reader_schema_version=None,
        max_reader_schema_version=None,
        api_version=None,
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "Windows 11 Release Guard" in index
    assert "unknown" in index
    assert "unavailable" in index
    assert "not attached" in index
    assert "API version" not in index
    assert "<h2>Sources</h2>" not in index
    assert "sources-panel" not in index
    assert "source-health" in index
    assert "source-tile unknown" in index
    for removed_label in REMOVED_SCHEMA_PANEL_LABELS:
        assert removed_label not in index
    assert "No existing-device exclusions" not in index
    assert "3</strong><span>Notices" in index
    assert "1</strong><span>Warnings" in index
    assert "0</strong><span>Errors" in index
    assert "3 notice diagnostic entries reported without structured row details." in index
    assert "Rendered warning &lt;without raw html&gt;" in index
    assert "&lt;unsafe&gt;" in index
    assert FRESHNESS_SCRIPT_RE.search(index) is not None
    assert "script src" not in index.lower()


def test_pages_index_source_health_tiles_are_integrated_and_status_colored() -> None:
    release_health_url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
    atom_url = "https://support.microsoft.com/en-us/feed/atom/4ec863cc-2ecd-e187-6cb3-b50c6545db92"
    policy = ReleasePolicy(
        source_urls=(release_health_url, atom_url),
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 0, "error": 0},
            "release_health_html": {
                "status": "ok",
                "fetched_at_utc": "2026-06-04T12:00:00+00:00",
                "bytes": 4096,
            },
            "atom_feed": {
                "status": "error",
                "fetched_at_utc": "2026-06-04T12:01:00+00:00",
                "bytes": 0,
            },
        },
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "<h2>Sources</h2>" not in index
    assert "sources-panel" not in index
    assert "Source health" in index
    assert index.find("Source diagnostics") < index.find("Source health")
    assert 'class="source-tile ok"' in index
    assert 'class="source-status ok">ok</span>' in index
    assert 'class="source-tile error"' in index
    assert 'class="source-status error">error</span>' in index
    assert "Microsoft Release Health" in index
    assert "Microsoft Atom feed" in index
    assert "4.0 KiB" in index
    assert "Thursday, 4 June 2026, 12:00:00 UTC" in index
    assert "Thursday, 4 June 2026, 12:01:00 UTC" in index
    assert 'data-epoch="1780574400000"' in index
    assert 'data-epoch="1780574460000"' in index
    assert 'aria-label="Copy Microsoft Release Health UTC epoch millisecond timestamp 1780574400000"' in index
    assert 'aria-label="Copy Microsoft Atom feed UTC epoch millisecond timestamp 1780574460000"' in index


def test_pages_index_source_health_tiles_support_warning_status() -> None:
    atom_url = "https://support.microsoft.com/en-us/feed/atom/4ec863cc-2ecd-e187-6cb3-b50c6545db92"
    policy = ReleasePolicy(
        source_urls=(atom_url,),
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 0, "error": 0},
            "atom_feed": {
                "status": "warning",
                "fetched_at_utc": "2026-06-04T12:01:00+00:00",
                "bytes": 2048,
            },
        },
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert 'class="source-tile warning"' in index
    assert 'class="source-status warning">warning</span>' in index
    assert "2.0 KiB" in index


def test_pages_index_epoch_copy_buttons_preserve_milliseconds() -> None:
    release_health_url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
    atom_url = "https://support.microsoft.com/en-us/feed/atom/4ec863cc-2ecd-e187-6cb3-b50c6545db92"
    policy = ReleasePolicy(
        generated_at_utc="2026-06-04T12:00:00.123+00:00",
        source_urls=(release_health_url, atom_url),
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 0, "error": 0},
            "release_health_html": {
                "status": "ok",
                "fetched_at_utc": "2026-06-04T12:00:00.321+00:00",
                "bytes": 4096,
            },
            "atom_feed": {
                "status": "ok",
                "fetched_at_utc": "2026-06-04T12:00:00.654+00:00",
                "bytes": 2048,
            },
        },
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert 'data-epoch="1780574400123"' in index
    assert 'data-epoch="1780574400321"' in index
    assert 'data-epoch="1780574400654"' in index
    assert "epoch millisecond timestamp" in index
    assert "Thursday, 4 June 2026, 12:00:00 UTC" in index


def test_pages_index_does_not_emit_release_link_for_invalid_program_version(monkeypatch) -> None:
    monkeypatch.setattr(
        policy_generator_module,
        "GENERATOR_VERSION",
        "win11_release_guard/not-a-version<script>",
    )

    index = render_policy_index(ReleasePolicy(), policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "Program Version" in index
    assert "releases/tag/vnot-a-version" not in index
    assert "not-a-version&lt;script&gt;" in index
    assert index.lower().count("<script") == 2
    assert "script src" not in index.lower()


def test_pages_index_escapes_freshness_json_script_payload() -> None:
    policy = ReleasePolicy(
        generated_at_utc='2026-05-31T14:11:50+00:00</script><script src="https://cdn.example/x.js">',
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert index.lower().count("<script") == 2
    assert "<script src" not in index.lower()
    freshness = _freshness_data(index)
    assert freshness["generated_at_utc"].startswith("2026-05-31T14:11:50+00:00</script>")
    assert freshness["generated_at_epoch_s"] is None


def test_pages_index_source_diagnostics_escape_event_message_without_script_injection() -> None:
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"warning": 1},
            "events": [
                {
                    "severity": "warning",
                    "kind": "parser_warning",
                    "message": 'Parser saw <script src="https://cdn.example/x.js"> bad markup.',
                }
            ],
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "Parser Warning" in index
    assert "Parser saw &lt;script src=&quot;https://cdn.example/x.js&quot;&gt; bad markup." in index
    assert "<script src" not in index.lower()
    assert index.lower().count("<script") == 2


def test_pages_index_source_diagnostics_collapses_overflow_events() -> None:
    events = [
        {
            "severity": "notice",
            "kind": "atom_newer_than_release_history",
            "build": f"26200.84{index}",
            "message": f"Notice event {index}",
        }
        for index in range(7)
    ]
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 7, "warning": 0, "error": 0},
            "events": events,
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "7</strong><span>Notices" in index
    assert "+2 more" in index
    assert "Notice event 0" in index
    assert "Notice event 6" in index


def test_pages_index_source_diagnostics_include_stale_freshness_row() -> None:
    policy = ReleasePolicy(generated_at_utc="2000-01-01T00:00:00+00:00")

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "Policy feed stale" in index
    assert "Policy feed currency" in index
    assert "Published policy feed is stale at render time." in index
    assert "Date.now" in index


def test_pages_index_embeds_feed_currency_thresholds_for_current_refresh_due_and_stale_dates() -> None:
    reference = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    for age_days in (0, 15, 46):
        generated = (reference - timedelta(days=age_days)).isoformat()
        index = render_policy_index(ReleasePolicy(generated_at_utc=generated), policy_bytes=None, signature=None)
        freshness = _freshness_data(index)

        assert freshness["generated_at_epoch_s"] == int((reference - timedelta(days=age_days)).timestamp())
        assert freshness["warn_after_epoch_s"] - freshness["generated_at_epoch_s"] == 14 * 24 * 60 * 60
        assert freshness["stale_after_epoch_s"] - freshness["generated_at_epoch_s"] == 45 * 24 * 60 * 60
        assert freshness["strict_stale_after_epoch_s"] == freshness["stale_after_epoch_s"]
        assert "Current" in index
        assert "Refresh Due" in index
        assert "Stale" in index


def test_pages_index_release_link_tracks_future_program_versions(monkeypatch) -> None:
    monkeypatch.setattr(policy_generator_module, "GENERATOR_VERSION", "win11_release_guard/1.2.3")

    index = render_policy_index(ReleasePolicy(), policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert 'href="https://github.com/Avnsx/win11_release_guard/releases/tag/v1.2.3"' in index
    assert "GitHub release tag" not in index
    assert '<div class="title-line"><h1>Windows 11 Release Guard</h1></div>' in index
    assert '<div class="subtitle-line"><p class="subtitle">Broad-fleet Windows 11 release and quality baseline dashboard.</p></div>' in index
    assert index.index('class="header-nav"') < index.index('class="title-version-link')
    assert index.index('class="subtitle"') < index.index('class="title-version-link')
    assert "Program Version</span> 1.2.3</a>" in index


def test_excluded_release_reason_summaries_do_not_end_with_half_words(tmp_path: Path) -> None:
    index = _render_landing(tmp_path)
    summaries = re.findall(
        r"<article class=\"diag-row notice\">.*?<strong>[^<]*excluded for existing devices</strong>.*?<p>(.*?)</p>",
        index,
        re.DOTALL,
    )

    assert summaries
    for summary in summaries:
        assert not summary.endswith("devi.")
        last_word = re.search(r"([A-Za-z]+)\.$", summary)
        assert last_word is None or len(last_word.group(1)) >= 5

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
SOURCE_DIAGNOSTIC_ID_RE = re.compile(r'data-diagnostic-id="(wrg-source-diagnostic-v1:[0-9a-f]{16})"')


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


def _assert_no_external_page_dependencies(index: str) -> None:
    lower = index.lower()
    assert "script src" not in lower
    assert 'rel="stylesheet"' not in lower
    assert "fonts.googleapis" not in lower
    assert "fonts.gstatic" not in lower
    assert "@import" not in lower
    assert "cdnjs" not in lower
    assert "cdn.jsdelivr" not in lower
    assert "unpkg.com" not in lower
    assert "esm.sh" not in lower
    assert "animations/auto" not in lower
    assert "auto-table-of-content" not in lower
    assert "auto-table" not in lower
    assert "npm" not in lower
    assert "fontawesome" not in lower
    assert "lucide" not in lower
    assert "github_token" not in lower
    assert "gh_token" not in lower
    assert "authorization:" not in lower
    assert "bearer " not in lower
    assert "credential" not in lower


def _assert_glass_dashboard_ui_contract(index: str) -> None:
    assert "main{position:relative;z-index:1;width:calc(100% - 80px);max-width:1580px" in index
    assert "backdrop-filter:blur(28px)" in index
    assert "body:before" in index
    assert "body:after" in index
    assert 'class="winmark"' in index
    assert "winmark{width:132px;height:132px" in index
    assert "kpi-card" in index
    assert "icon-bubble" in index
    assert 'class="ui-icon' in index
    assert "<svg" in index
    assert "freshness-ring" in index
    assert "panel-action" in index
    assert "diag-row-icon" in index
    assert "container-type:inline-size" in index
    assert "text-wrap:balance" in index
    assert "@media(max-width:1400px)" in index
    assert "@media(max-width:900px)" in index
    assert "@media(max-width:640px)" in index
    assert "@media(max-width:360px)" in index
    _assert_no_external_page_dependencies(index)


def _assert_diag_count_tile(index: str, severity: str, count: int, label: str) -> None:
    assert (
        f'<button type="button" class="diag-tile {severity}" '
        f'data-diagnostic-filter="{severity}" data-diagnostic-severity="{severity}" '
        'aria-pressed="false" aria-controls="source-diagnostics-feed"'
        in index
    )
    assert (
        f'<strong>{count}</strong><span>{label}</span>'
        '<svg class="ui-icon diag-tile-icon"'
        in index
    )


def _diag_row_marker(severity: str) -> str:
    return f'<article class="diag-row {severity}" data-diagnostic-severity="{severity}" data-diagnostic-id="'


def _diagnostic_ids(index: str) -> list[str]:
    return SOURCE_DIAGNOSTIC_ID_RE.findall(index)


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
    assert (
        '<meta name="description" content="Windows 11 Release Guard dashboard for Windows 11 release compliance, '
        "signed public policy feed freshness, 25H2 target status, source diagnostics, and fleet administration "
        'checks.">'
        in index
    )
    assert '<link rel="canonical" href="https://avnsx.github.io/win11_release_guard/">' in index
    assert '<meta property="og:title" content="Windows 11 Release Guard">' in index
    assert '<meta property="og:url" content="https://avnsx.github.io/win11_release_guard/">' in index
    assert '<meta name="twitter:card" content="summary">' in index
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
    assert "dataset.uiLastError" in index
    assert "data-ui-error-count" in index
    assert "reportMissingNode" in index
    assert "missing '+name" in index
    assert "console.warn('Windows 11 Release Guard UI '+label+' failed')" in index
    assert "console.warn('Windows 11 Release Guard UI '+scope+' failed',error)" not in index
    assert "shutdownUi" in index
    assert "pagehide" in index
    assert "beforeunload" in index
    assert "safeSetTimeout" in index
    assert "safeSetInterval" in index
    assert "safeRequestFrame" in index
    assert "safeCancelFrame" in index
    assert "timer setup" in index
    assert "interval setup" in index
    assert "animation frame request" in index
    assert "animation cancel" in index
    assert "timer cancel" in index
    assert "button.isConnected" in index
    assert "nav.isConnected" in index
    assert "passive:true" in index
    assert "header nav pointer" in index
    assert "header nav focus" in index
    assert "header nav leave" in index
    assert "header nav focusout" in index
    assert "freshness update" in index
    assert "freshness update','data" in index
    assert "@media(prefers-reduced-motion:reduce)" in index
    assert "animation:none!important" in index
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
    assert 'class="header-top-actions"' in index
    assert 'class="header-nav"' in index
    assert 'class="pypi-download-link"' in index
    assert 'class="nav-hover-label"' in index
    assert "nav-binoculars" not in index
    assert 'aria-label="Header navigation"' in index
    assert 'aria-label="Download win11_release_guard from PyPI"' in index
    assert 'href="https://pypi.org/project/win11-release-guard/"' in index
    assert 'src="assets/images/download_from_pypi.png"' in index
    assert 'alt="Download from PyPI"' in index
    assert ".pypi-download-link{display:inline-flex" in index
    assert (tmp_path / "assets" / "images" / "download_from_pypi.png").is_file()
    assert 'id="policy-summary"' in index
    assert 'href="https://avnsx.github.io/win11_release_guard/"' in index
    _assert_glass_dashboard_ui_contract(index)
    assert "--item-size:42px" in index
    assert "@media(max-width:900px)" in index
    assert ".nav-hover-label{display:none}" in index
    assert 'data-nav-label="Dashboard"' in index
    assert "Dashboard" in index
    assert 'data-nav-label="Write a Issue Ticket"' in index
    assert "Write a Issue Ticket" in index
    assert "https://github.com/Avnsx/win11_release_guard/issues/new" in index
    assert 'data-nav-label="Wiki"' in index
    assert "Wiki" in index
    assert "https://avnsx.github.io/win11_release_guard/wiki/" in index
    assert "https://github.com/Avnsx/win11_release_guard/wiki" not in index
    assert "animations/auto" not in index
    assert "auto-table-of-content" not in index
    assert "esm.sh" not in index
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
    _assert_diag_count_tile(index, "notice", 3, "Notices")
    assert index.count(_diag_row_marker("notice")) == 3
    diagnostic_ids = _diagnostic_ids(index)
    assert len(diagnostic_ids) >= 3
    assert len(set(diagnostic_ids)) == len(diagnostic_ids)
    assert "data-diagnostic-id=&quot;" not in index
    assert 'id="source-diagnostics-feed"' in index
    assert (
        '<button type="button" class="panel-action diag-filter-reset" '
        'data-diagnostic-filter="all" aria-controls="source-diagnostics-feed" aria-pressed="true">View all</button>'
        in index
    )
    assert '<a class="panel-action" href="#source-health">Source health</a>' not in index
    assert '<button type="button" class="panel-action" data-source-health' not in index
    assert ">Source health</button>" not in index
    assert 'id="source-diagnostics-filter-status" class="diag-filter-status" aria-live="polite"' in index
    assert "Showing all 3 source diagnostic rows." in index
    assert 'id="source-diagnostics-empty" class="diag-filter-empty" hidden' in index
    assert "No diagnostic rows match the selected severity filter." in index
    assert "data-diagnostic-filter-root" in index
    assert "initDiagnosticFilters" in index
    assert "source diagnostics filter init" in index
    assert "source diagnostics filter" in index
    assert "guard('source diagnostics filter'" in index
    assert "source diagnostics filter','root" in index
    assert "source diagnostics filter','feed" in index
    assert "source diagnostics filter','controls" in index
    assert "source diagnostics filter','rows" in index
    assert "source diagnostics filter','status" in index
    assert "source diagnostics filter','empty state" in index
    assert ".diag-row[hidden]" in index
    assert ".diag-more[hidden]" in index
    assert "row.hidden=!match" in index
    assert "var labels={notice:'notice',warning:'warning',error:'error'}" in index
    assert "function normalizedFilter(value){return labels[value] ? value : '';}" in index
    assert "row.getAttribute('data-diagnostic-severity')===severity" in index
    assert "applyFilter(control.getAttribute('data-diagnostic-filter')||'all')" in index
    assert "status.textContent='Showing '+shown+' '+labels[severity]+' diagnostic '+rowWord(shown)+'.'" in index
    assert "status.textContent='No '+labels[severity]+' diagnostic rows are currently reported.'" in index
    assert "control.setAttribute('aria-pressed',severity ? String(value===severity) : String(value==='all'))" in index
    assert "aria-pressed" in index
    assert "data-diagnostic-filter" in index
    assert "data-diagnostic-severity" in index
    assert "data-diagnostic-id" in index
    assert ".diag-tile.notice{border-color:#bfdbfe" in index
    assert ".diag-tile.notice strong,.diag-tile.notice .diag-tile-icon{color:var(--blue)}" in index
    assert ".severity-badge.notice{color:var(--blue-strong)" in index
    assert ".diag-tile.warning{border-color:#f6d493" in index
    assert ".diag-tile.warning strong,.diag-tile.warning .diag-tile-icon{color:var(--warn)}" in index
    assert ".diag-tile.error{border-color:#f6b7ad" in index
    assert ".diag-tile.error strong,.diag-tile.error .diag-tile-icon{color:var(--err)}" in index
    assert ".diag-row.warning{border-color:#f6d493" in index
    assert ".diag-row.error{border-color:#f6b7ad" in index
    assert ".diag-feed{height:340px;min-height:340px;max-height:340px" in index
    assert "scrollbar-gutter:stable" in index
    assert "background:linear-gradient(180deg,rgba(255,255,255,.76),rgba(238,247,255,.68))" in index
    assert "scrollbar-color:#8eb7df rgba(232,243,255,.68)" in index
    assert ".diag-feed::-webkit-scrollbar-thumb" in index
    assert ".diag-events{gap:10px;padding:2px 4px 12px 2px}" in index
    assert "diag-row-icon" in index
    assert '<article class="diag-row notice" data-diagnostic-severity="notice" hidden' not in index
    assert '<article class="diag-row warning" data-diagnostic-severity="warning" hidden' not in index
    assert '<article class="diag-row error" data-diagnostic-severity="error" hidden' not in index
    assert "source-chip src-diagnostics" in index
    assert "source-chip src-atom-feed" in index
    assert "source-chip src-release-policy" in index
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
    assert ".api-endpoint-row{grid-template-columns:auto minmax(0,1fr)" in index
    assert ".signature-panel,.programmatic-api{grid-column:1/-1}" in index
    assert "Programmatic API" in index
    _assert_no_external_page_dependencies(index)
    freshness = _freshness_data(index)
    assert freshness["generated_at_utc"] == "2026-05-31T14:11:50+00:00"
    assert freshness["generated_at_epoch_s"] == 1780236710
    assert freshness["warn_after_epoch_s"] == 1781446310
    assert freshness["stale_after_epoch_s"] == 1784124710
    assert freshness["max_ok_age_seconds"] == 14 * 24 * 60 * 60
    assert freshness["warning_age_seconds"] == 14 * 24 * 60 * 60
    assert freshness["strict_stale_age_seconds"] == 45 * 24 * 60 * 60
    assert freshness["freshness_policy"]["client_recomputes_age"] is True


def test_pages_index_renders_day_hour_freshness_visual_state(monkeypatch) -> None:
    monkeypatch.setattr(policy_generator_module, "_utc_now", lambda: "2026-06-07T15:00:00+00:00")
    policy = ReleasePolicy(generated_at_utc="2026-06-01T00:00:00+00:00")

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert (
        'id="live-generated-age" class="freshness-metric age-wide" aria-live="polite" '
        'title="Published feed age 6 days, 15 hours, 0 minutes" '
        'aria-label="Published feed age 6 days, 15 hours, 0 minutes">6d 15h</div>'
        in index
    )
    assert ".freshness-panel{container-type:inline-size}" in index
    assert ".freshness-panel .freshness-layout{grid-template-columns:1fr;gap:clamp(24px,3vw,34px)}" in index
    assert (
        ".freshness-panel .freshness-hero{grid-template-columns:minmax(104px,120px) "
        "minmax(0,1fr);gap:clamp(28px,3vw,40px);max-width:100%}"
        in index
    )
    assert ".freshness-metric{white-space:normal;overflow-wrap:normal;word-break:normal;text-wrap:balance}" in index
    assert ".freshness-callout{margin-top:clamp(14px,2vw,22px)}" in index
    assert "@supports(margin-top:1cqw){.freshness-callout{margin-top:clamp(14px,3cqw,24px)}}" in index
    assert ".freshness-panel .thresholds{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}" in index
    assert ".freshness-panel .thresholds{grid-template-columns:1fr;gap:12px}" in index
    assert ".freshness-age-copy{gap:8px;padding-inline-start:2px}" in index
    assert "days+'d '+hours+'h" in index
    _assert_no_external_page_dependencies(index)


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
    assert "font-size:12px;font-weight:620;white-space:nowrap" in index
    assert "width:max-content;overflow:hidden;border:1px solid #a9ddb7" in index
    assert (
        ".trust-indicator.error{color:var(--err);background:linear-gradient(180deg,var(--err-soft),#fff8f6);"
        "border-color:#f6b7ad"
        in index
    )
    assert "--trust-ring:rgba(180,35,24,.2)" in index
    assert ".signature-panel.error{border-color:#f6b7ad;background:linear-gradient(180deg,#fff7f5,#fffdfc)}" in index
    assert ".signature-panel.error:before{background:linear-gradient(90deg,var(--err),rgba(180,35,24,.22))}" in index
    assert ".signature-status-card.error{border-color:#f6b7ad;background:linear-gradient(135deg,var(--err-soft),#fff8f6)}" in index
    assert "box-shadow:0 0 0 4px var(--trust-ring)" in index
    assert "width:9px;height:9px" in index
    assert "animation:trustPulse 2.2s cubic-bezier(.4,0,.2,1) infinite" in index
    assert "will-change:transform" in index
    keyframes = index.split("@keyframes trustPulse", 1)[1].split(".trust-indicator.warning", 1)[0]
    assert "transform:scale(1.48)" in keyframes
    assert "transform:scale(1.12)" in keyframes
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
    assert ".signature-kv dd{margin:0;color:#172033;font-weight:600;line-height:1.25;overflow-wrap:anywhere}" in index
    assert ".signature-kv .mono{font-size:13px;font-weight:600}" in index
    assert (
        ".signature-kv div:hover{border-color:#b8c9dd;background:#fff;"
        "box-shadow:0 7px 16px rgba(31,79,143,.07);transform:translateY(-1px)}"
        in index
    )
    assert (
        ".api-endpoint-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;"
        "gap:10px;align-items:center;border:1px solid var(--line);border-radius:8px;"
        "background:linear-gradient(180deg,#f8fafc,#f3f6fa);padding:10px 11px;"
        "color:inherit;text-decoration:none}"
        in index
    )
    assert "api-row-icon" in index
    assert ".api-endpoint-row:hover{border-color:#aecded" in index
    api_hover_rules = re.findall(r"\.api-endpoint-row:hover\{([^}]*)\}", index)
    assert api_hover_rules
    assert all("transform:" not in rule for rule in api_hover_rules)
    assert ".api-endpoint-row:focus-visible{outline:3px solid rgba(0,120,212,.28)" in index
    assert ".signature-kv div:hover{transform:none!important}" in index


def test_pages_index_uses_balanced_ui_font_weights() -> None:
    index = render_policy_index(ReleasePolicy(), policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    explicit_weights = [int(weight) for weight in re.findall(r"font-weight:(\d+)", index)]
    assert explicit_weights
    assert max(explicit_weights) <= 760

    trust_rule = index.split(".trust-indicator{", 1)[1].split("}", 1)[0]
    assert "font-weight:620" in trust_rule
    assert "font-weight:7" not in trust_rule

    assert ".title-line h1{font-size:clamp(34px,4rem,64px);line-height:1.04;margin:0 0 10px;font-weight:760" in index
    assert ".title-version-link{display:inline-flex;align-items:center;gap:8px;margin-left:auto" in index
    assert "font-size:16px;font-weight:700" in index
    assert ".eyebrow{display:inline-flex;align-items:center;gap:8px;margin-bottom:8px;color:#004de6;font-size:20px;font-weight:740" in index
    assert "h2{font-size:12px;font-weight:720;text-transform:uppercase" in index
    assert ".signature-head h2{margin:0;color:#475569;font-weight:720}" in index
    assert ".source-health h3{margin:0;color:var(--muted);font-size:11px;font-weight:720" in index
    assert ".source-name strong{font-weight:700}" in index

    assert ".metric{font-size:31px;font-weight:680" in index
    assert ".kpi-card .metric{font-size:54px;font-weight:720" in index
    assert ".freshness-metric{font-size:46px;font-weight:720" in index
    assert ".kv dd{margin:0;font-weight:600;overflow-wrap:anywhere}" in index
    assert ".thresholds strong{display:block;font-size:17px;font-weight:640}" in index
    assert ".diag-tile strong{display:block;font-size:22px;font-weight:650" in index
    assert ".diag-row-head strong{font-size:13px;font-weight:640}" in index
    assert ".severity-badge,.source-chip,.diag-tags span,.diag-tags a{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:2px 7px;font-size:11px;font-weight:600" in index
    assert ".api-endpoint-row strong{display:block;color:#172033;font-size:13px;font-weight:640" in index
    assert "footer{position:relative;display:grid;gap:8px;justify-items:center;margin-top:34px;padding:20px 12px 4px" in index
    assert "footer:before{content:'';width:min(640px,100%);height:1px;margin-bottom:8px" in index
    assert ".footer-source{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:4px 6px;margin-top:2px}" in index
    assert ".footer-github{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.82);padding:2px 8px;color:#075985;font-weight:600" in index
    assert "footer{margin-top:28px;padding-top:18px}" in index


def test_pages_index_source_diagnostics_empty_state_is_compact() -> None:
    policy = ReleasePolicy(
        source_diagnostics={"event_counts": {"notice": 0, "warning": 0, "error": 0}},
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "No source issues reported" in index
    assert "Release Health, Atom feed, parser, and freshness checks have no warning or error events." in index
    assert "1</strong><span>Notices" in index
    assert "0</strong><span>Warnings" in index
    assert "0</strong><span>Errors" in index
    _assert_diag_count_tile(index, "notice", 1, "Notices")
    _assert_diag_count_tile(index, "warning", 0, "Warnings")
    _assert_diag_count_tile(index, "error", 0, "Errors")
    assert _diag_row_marker("notice") in index
    assert index.count(_diag_row_marker("notice")) == 1
    assert _diag_row_marker("warning") not in index
    assert _diag_row_marker("error") not in index
    assert "diag-feed" in index
    assert "diag-events-empty" in index
    assert 'id="source-diagnostics-empty" class="diag-filter-empty" hidden' in index
    assert "No diagnostic rows match the selected severity filter." in index
    assert "setEmptyState" in index
    assert "labels={notice:'notice',warning:'warning',error:'error'}" in index
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
    assert "2</strong><span>Notices" in index
    assert "0</strong><span>Warnings" in index
    assert "0</strong><span>Errors" in index
    assert "No source issues reported" in index
    assert "26H1 excluded for existing devices" in index
    assert "Release policy" in index
    assert "Notice" in index
    assert "Release 26H1" in index
    assert "Existing devices" in index
    assert index.count(_diag_row_marker("notice")) == 2
    assert index.find("No source issues reported") < index.find("26H1 excluded for existing devices")


def test_pages_index_derived_source_diagnostic_rows_do_not_render_ticket_links() -> None:
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
                    "number": 70,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/70",
                },
                excluded_id: {
                    "number": 71,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/71",
                },
            },
        },
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "No source issues reported" in index
    assert "26H1 excluded for existing devices" in index
    assert f'data-diagnostic-id="{clear_id}"' in index
    assert f'data-diagnostic-id="{excluded_id}"' in index
    assert index.count(_diag_row_marker("notice")) == 2
    _assert_diag_count_tile(index, "notice", 2, "Notices")
    assert "#Ticket 70" not in index
    assert "#Ticket 71" not in index
    assert '<a class="diag-ticket-link"' not in index


def test_pages_index_source_diagnostics_render_structured_warning_event() -> None:
    event = {
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
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 1, "error": 0},
            "events": [event],
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert _diag_row_marker("warning") in index
    assert "Atom Newer Than Release History" in index
    assert "Atom feed" in index
    assert "Warning" in index
    assert "Release 25H2" in index
    assert "Build 26200.8461" in index
    assert "KB5089600" in index
    assert "Required baseline" in index
    assert "Atom feed reports a newer baseline build." in index
    expected_id = policy_generator_module._source_diagnostic_id_for_event(event)
    assert f'data-diagnostic-id="{expected_id}"' in index
    _assert_diag_count_tile(index, "warning", 1, "Warnings")
    _assert_diag_count_tile(index, "notice", 0, "Notices")
    assert '<span class="severity-badge warning">Warning</span>' in index
    assert "No source issues reported" not in index


def test_pages_index_source_diagnostics_ticket_link_is_static_hover_only_metadata() -> None:
    event = {
        "severity": "warning",
        "kind": "atom_newer_than_release_history",
        "release": "25H2",
        "build_family": 26200,
        "build": "26200.8461",
        "kb_article": "KB5089600",
        "affects_broad_target": True,
        "affects_required_baseline": True,
        "message": "Atom feed reports a newer baseline build.",
    }
    diagnostic_id = policy_generator_module._source_diagnostic_id_for_event(event)
    without_issue_status = render_policy_index(
        ReleasePolicy(source_diagnostics={"event_counts": {"notice": 0, "warning": 1, "error": 0}, "events": [event]}),
        policy_bytes=None,
        signature=None,
    )

    assert '<a class="diag-ticket-link"' not in without_issue_status
    assert "#Ticket 42" not in without_issue_status

    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 1, "error": 0},
            "events": [event],
            "issue_status": {
                diagnostic_id: {
                    "number": 42,
                    "state": "open",
                    "url": "https://github.com/Avnsx/win11_release_guard/issues/42",
                }
            },
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert f'data-diagnostic-id="{diagnostic_id}"' in index
    assert (
        '<a class="diag-ticket-link" '
        'href="https://github.com/Avnsx/win11_release_guard/issues/42" '
        'aria-label="GitHub issue 42 status open">'
    ) in index
    assert "diag-ticket-link-icon" in index
    assert "#Ticket 42" in index
    assert '<svg class="github-icon"' in index
    assert ".diag-row:hover .diag-ticket-link,.diag-row:focus-within .diag-ticket-link" in index
    assert "opacity:0;pointer-events:none" in index
    _assert_no_external_page_dependencies(index)


def test_pages_index_source_diagnostics_renders_issue_sync_unavailable_status() -> None:
    policy = ReleasePolicy(
        source_diagnostics={
            "event_counts": {"notice": 0, "warning": 0, "error": 0},
            "events": [],
            "issue_sync": {
                "status": "unavailable",
                "reason": "github_issues_sync_failed",
                "message": "GitHub Issues sync failed during publish-policy.",
            },
        }
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert 'data-issue-sync-status="unavailable"' in index
    assert "Issue sync unavailable" in index
    assert "GitHub Issues sync failed during publish-policy." in index
    assert "github_issues_sync_failed" in index
    assert "#Ticket" not in index
    _assert_no_external_page_dependencies(index)


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

    _assert_diag_count_tile(index, "warning", 1, "Warnings")
    _assert_diag_count_tile(index, "error", 1, "Errors")
    _assert_diag_count_tile(index, "notice", 0, "Notices")
    assert _diag_row_marker("warning") in index
    assert _diag_row_marker("error") in index
    assert '<article class="diag-row warning" data-diagnostic-severity="warning" hidden' not in index
    assert '<article class="diag-row error" data-diagnostic-severity="error" hidden' not in index
    assert '<span class="severity-badge warning">Warning</span>' in index
    assert '<span class="severity-badge error">Error</span>' in index
    assert "Current Versions Lag Release History" in index
    assert "Missing Broad Target Baseline" in index
    assert "Current Versions is behind Release History." in index
    assert "Required baseline cannot be derived." in index
    assert "No source issues reported" not in index


def test_pages_index_source_diagnostics_warning_error_counts_suppress_clear_placeholder() -> None:
    policy = ReleasePolicy(
        source_diagnostics={"event_counts": {"notice": 0, "warning": 2, "error": 1}},
    )

    index = render_policy_index(policy, policy_bytes=None, signature=None)
    HTMLParser().feed(index)

    assert "No source issues reported" not in index
    _assert_diag_count_tile(index, "notice", 0, "Notices")
    _assert_diag_count_tile(index, "warning", 1, "Warnings")
    _assert_diag_count_tile(index, "error", 1, "Errors")
    assert index.count(_diag_row_marker("warning")) == 1
    assert index.count(_diag_row_marker("error")) == 1
    assert "2 warning diagnostic entries reported without structured row details." in index
    assert "1 error diagnostic entry reported without structured row details." in index


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
    assert "1</strong><span>Notices" in index
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
    diagnostic_ids = _diagnostic_ids(index)
    assert diagnostic_ids
    assert all(diagnostic_id.startswith("wrg-source-diagnostic-v1:") for diagnostic_id in diagnostic_ids)
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

    assert "8</strong><span>Notices" in index
    assert index.count(_diag_row_marker("notice")) == 8
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
        r"<article class=\"diag-row notice\" data-diagnostic-severity=\"notice\" "
        r"data-diagnostic-id=\"wrg-source-diagnostic-v1:[0-9a-f]{16}\">.*?"
        r"<strong>[^<]*excluded for existing devices</strong>.*?<p>(.*?)</p>",
        index,
        re.DOTALL,
    )

    assert summaries
    for summary in summaries:
        assert not summary.endswith("devi.")
        last_word = re.search(r"([A-Za-z]+)\.$", summary)
        assert last_word is None or len(last_word.group(1)) >= 5

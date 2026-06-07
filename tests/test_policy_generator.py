from __future__ import annotations

import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import pytest

from tools import generate_policy as generate_policy_cli
from win11_release_guard.config import (
    DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS,
    DEFAULT_POLICY_URL,
    DEFAULT_POLICY_WARNING_AGE_SECONDS,
    DEFAULT_PUBLISHED_POLICY_URLS,
    DEFAULT_RELEASE_HEALTH_URL,
)
from win11_release_guard.exceptions import PolicyParseError
from win11_release_guard.freshness import epoch_milliseconds_from_iso
from win11_release_guard.models import QualityPolicy, ReleasePolicy
import win11_release_guard.policy_generator as policy_generator_module
from win11_release_guard.policy_generator import (
    _source_label,
    build_policy_from_sources,
    generate_policy,
    parse_atom_feed,
    render_robots_txt,
    write_policy_outputs,
)
from win11_release_guard.policy_schema import GENERATOR_VERSION, validate_policy_document


FIXTURES = Path("tests/fixtures")
EXPECTED_ROBOTS_TXT = (
    "User-agent: *\n"
    "Allow: /\n"
    "Sitemap: https://avnsx.github.io/win11_release_guard/sitemap.xml\n"
)
REMOVED_SCHEMA_PANEL_LABELS = (
    "API " + "and schema",
    "Policy " + "schema",
    "Reader " + "range",
)


def _html() -> str:
    return (FIXTURES / "windows11-release-health.html").read_text(encoding="utf-8")


def test_generator_utc_now_is_monotonic_at_millisecond_precision() -> None:
    values = [policy_generator_module._utc_now() for _ in range(4)]
    epochs = [epoch_milliseconds_from_iso(value) for value in values]

    assert all(epoch is not None for epoch in epochs)
    assert epochs == sorted(epochs)
    assert len(set(epochs)) == len(epochs)
    assert all("." in value for value in values)


def _html_file(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _atom() -> str:
    return (FIXTURES / "windows11-atom.xml").read_text(encoding="utf-8")


def _atom_with_new_b_release() -> str:
    entry = """
  <entry>
    <id>tag:support.microsoft.com,2026:KB5089600</id>
    <title>June 9, 2026-KB5089600 (OS Build 26200.8461)</title>
    <published>2026-06-09T18:00:00Z</published>
    <updated>2026-06-09T18:00:00Z</updated>
    <link rel="alternate" href="https://support.microsoft.com/help/5089600" />
    <content type="text">Monthly security update for Windows 11.</content>
  </entry>
"""
    return _atom().replace("</feed>", entry + "</feed>")


def _atom_with_duplicate_new_b_release() -> str:
    entry = """
  <entry>
    <id>tag:support.microsoft.com,2026:KB5089600-duplicate</id>
    <title>June 9, 2026-KB5089600 (OS Build 26200.8461)</title>
    <published>2026-06-09T18:00:00Z</published>
    <updated>2026-06-09T18:00:00Z</updated>
    <link rel="alternate" href="https://support.microsoft.com/help/5089600" />
    <content type="text">Monthly security update for Windows 11.</content>
  </entry>
"""
    return _atom_with_new_b_release().replace("</feed>", entry + "</feed>")


def test_source_label_requires_exact_upstream_hosts() -> None:
    release_health_url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
    localized_release_health_url = (
        "https://learn.microsoft.com/de-de/windows/release-health/windows11-release-information"
    )
    atom_url = "https://support.microsoft.com/en-us/feed/atom/4ec863cc-2ecd-e187-6cb3-b50c6545db92"
    localized_atom_url = "https://support.microsoft.com/de-de/feed/atom/4ec863cc-2ecd-e187-6cb3-b50c6545db92"
    spoofed_release_health_url = (
        "https://learn.microsoft.com.attacker.invalid/en-us/windows/release-health/windows11-release-information"
    )
    spoofed_atom_url = "https://support.microsoft.com.attacker.invalid/en-us/feed/atom/example"

    assert _source_label(release_health_url) == "Microsoft Release Health"
    assert _source_label(localized_release_health_url) == "Microsoft Release Health"
    assert _source_label(atom_url) == "Microsoft Atom feed"
    assert _source_label(localized_atom_url) == "Microsoft Atom feed"
    assert _source_label(spoofed_release_health_url) == spoofed_release_health_url
    assert _source_label(spoofed_atom_url) == spoofed_atom_url


def _with_26h2_ga(html: str) -> str:
    row = """      <tr>
        <td>26H2</td>
        <td>General Availability Channel</td>
        <td>2026-10-01</td>
        <td>2028-10-10</td>
        <td>2029-10-09</td>
        <td>2026-10-13</td>
        <td>28200.1000</td>
      </tr>
"""
    history = """
  <h3>Version 26H2 (OS build 28200)</h3>
  <table>
    <thead>
      <tr>
        <th>Servicing option</th>
        <th>Update type</th>
        <th>Availability date</th>
        <th>Build</th>
        <th>KB article</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>General Availability Channel</td>
        <td>2026-10 B</td>
        <td>2026-10-13</td>
        <td>28200.1000</td>
        <td>KB5090001</td>
      </tr>
    </tbody>
  </table>
"""
    html = html.replace("      <tr>\n        <td>26H1</td>", row + "      <tr>\n        <td>26H1</td>", 1)
    return html.replace("  <h3>Version 26H1 (OS build 28000)</h3>", history + "\n  <h3>Version 26H1 (OS build 28000)</h3>", 1)


def _with_27h1_special(html: str) -> str:
    note = """
  <p>
    Windows 11, version 27H1 is scoped to support new devices and is not
    designed as a feature update for existing devices. This version is not
    offered as an in-place update from 25H2 or 26H2 on existing devices.
  </p>
"""
    row = """      <tr>
        <td>27H1</td>
        <td>General Availability Channel</td>
        <td>2027-02-10</td>
        <td>2029-03-13</td>
        <td>2030-03-12</td>
        <td>2027-02-10</td>
        <td>29000.1000</td>
      </tr>
"""
    history = """
  <h3>Version 27H1 (OS build 29000)</h3>
  <table>
    <thead>
      <tr>
        <th>Servicing option</th>
        <th>Update type</th>
        <th>Availability date</th>
        <th>Build</th>
        <th>KB article</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>General Availability Channel</td>
        <td>2027-02 B</td>
        <td>2027-02-10</td>
        <td>29000.1000</td>
        <td>KB5097001</td>
      </tr>
    </tbody>
  </table>
"""
    html = html.replace("  <h2>Windows 11 current versions by servicing option</h2>", note + "\n  <h2>Windows 11 current versions by servicing option</h2>", 1)
    html = html.replace("      <tr>\n        <td>26H2</td>", row + "      <tr>\n        <td>26H2</td>", 1)
    return html.replace("  <h3>Version 26H2 (OS build 28200)</h3>", history + "\n  <h3>Version 26H2 (OS build 28200)</h3>", 1)


def _with_oob_row(html: str) -> str:
    row = """      <tr>
        <td>General Availability Channel</td>
        <td>2026-05</td>
        <td>2026-05-16</td>
        <td>26200.8460</td>
        <td>KB5089550</td>
      </tr>
"""
    return html.replace("      <tr>\n        <td>General Availability Channel</td>\n        <td>2026-04 D</td>", row + "      <tr>\n        <td>General Availability Channel</td>\n        <td>2026-04 D</td>", 1)


def _with_25h2_current_latest_build(html: str, build: str) -> str:
    return html.replace("        <td>26200.8457</td>\n      </tr>", f"        <td>{build}</td>\n      </tr>", 1)


def _without_26h1_special_note(html: str) -> str:
    start = html.index("  <p>\n    Windows 11, version 26H1")
    end = html.index("  </p>", start) + len("  </p>\n")
    return html[:start] + html[end:]


def test_generate_policy_from_local_html_and_atom_fixtures(tmp_path):
    policy = build_policy_from_sources(
        release_health_html_path=FIXTURES / "windows11-release-health.html",
        atom_feed_path=FIXTURES / "windows11-atom.xml",
        signature_status="valid",
    )
    data = policy.to_dict()
    validation_warnings = validate_policy_document(data)
    assert not any("source_diagnostics" in warning for warning in validation_warnings)
    written = write_policy_outputs(
        policy,
        output_dir=tmp_path,
        write_index=True,
        write_robots=True,
        write_sitemap=True,
        write_manifest=True,
    )

    assert written["policy"].name == "windows-release-policy.json"
    assert written["index"].name == "index.html"
    assert written["robots"].name == "robots.txt"
    assert written["sitemap"].name == "sitemap.xml"
    assert written["manifest"].name == "policy-manifest.json"
    assert written["nojekyll"].name == ".nojekyll"
    assert json.loads(written["policy"].read_text(encoding="utf-8"))["broad_target_existing_devices"]["version"] == "25H2"
    assert written["robots"].read_bytes() == EXPECTED_ROBOTS_TXT.encode("utf-8")
    assert "windows-release-policy.json" in written["sitemap"].read_text(encoding="utf-8")
    assert json.loads(written["manifest"].read_text(encoding="utf-8"))["broad_target_existing_devices"]["version"] == "25H2"
    assert data["source_fetch_status"]["release_health_html"]["status"] == "ok"
    assert data["source_fetch_status"]["atom_feed"]["status"] == "ok"
    assert data["source_fetch_status"]["release_health_html"]["fetched_at_utc"]
    assert data["source_fetch_status"]["atom_feed"]["fetched_at_utc"]
    diagnostics = data["source_diagnostics"]
    assert data["schema_version"] == 1
    assert data["min_reader_schema_version"] == 1
    assert data["max_reader_schema_version"] == 1
    assert data["api_version"] == "v1"
    assert data["generator_version"] == GENERATOR_VERSION
    assert data["compatibility"]["required_core_schema_version"] == 1
    assert diagnostics["release_health_html"]["source_url"] == DEFAULT_RELEASE_HEALTH_URL
    assert diagnostics["release_health_html"]["bytes"] > 0
    assert diagnostics["release_health_html"]["newest_current_version_revision_date"] == "2026-05-12"
    assert diagnostics["release_health_html"]["newest_release_history_availability_date"] == "2026-05-12"
    assert diagnostics["atom_feed"]["newest_atom_updated"] == "2026-05-16T18:00:00Z"
    assert diagnostics["atom_feed"]["newest_atom_published"] == "2026-05-16T18:00:00Z"
    assert diagnostics["atom_feed"]["newest_atom_build"] == "26200.8460"
    assert any(event["severity"] == "notice" for event in diagnostics["events"])
    assert "quality_baselines" in data
    assert "preview_builds" in data


def test_write_signed_policy_output_includes_key_id(tmp_path):
    policy = generate_policy(
        release_health_html=_html(),
        atom_feed_xml=_atom(),
        generated_at_utc="2026-05-31T14:11:50+00:00",
        signature_status="valid",
    )

    written = write_policy_outputs(
        policy,
        output_dir=tmp_path,
        signing_key="krtF2muLgucP7JDVNKk2g+YQfz92c7xM49dzszxHxjs=",
        key_id="test-policy-key",
    )
    signature = json.loads(written["signature"].read_text(encoding="utf-8"))

    assert signature["algorithm"] == "ed25519"
    assert signature["key_id"] == "test-policy-key"
    assert signature["signature"]
    assert signature["signed_at_utc"]


def test_fixture_with_26h1_25h2_24h2_chooses_25h2():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=_atom())

    assert policy.broad_target_existing_devices is not None
    assert policy.broad_target_existing_devices.version == "25H2"
    special = {entry.version: entry for entry in policy.special_releases}
    assert special["26H1"].metadata["special_release"] is True
    assert special["26H1"].metadata["new_devices_only"] is True
    assert special["26H1"].metadata["not_broad_target_existing_devices"] is True


def test_generate_policy_from_release_health_current_d_preview_fixture():
    policy = generate_policy(
        release_health_html=_html_file("windows11-release-health-current-d-26h1.html"),
        atom_feed_xml=_atom(),
    )
    target = policy.broad_target_existing_devices
    baseline = policy.quality_baselines["25H2"][QualityPolicy.B_RELEASE_ONLY.value]

    assert target is not None
    assert target.latest_observed_build == "26200.8524"
    assert target.required_baseline_build == "26200.8457"
    assert baseline["build"] == "26200.8457"
    current_25h2 = next(entry for entry in policy.current_versions if entry.version == "25H2")
    assert current_25h2.latest_build == "26200.8524"
    assert current_25h2.latest_observed_build == "26200.8524"
    assert current_25h2.baseline_build == "26200.8457"
    assert current_25h2.required_baseline_build == "26200.8457"
    assert any(item["build"] == "26200.8524" for item in policy.preview_builds)
    assert {entry.version for entry in policy.special_releases} == {"26H1"}


def test_generate_policy_fails_on_release_health_26h1_without_special_note():
    with pytest.raises(PolicyParseError, match="26H1 new-devices-only special release note"):
        generate_policy(release_health_html=_without_26h1_special_note(_html()), atom_feed_xml=_atom())


def test_future_26h2_ga_chooses_26h2():
    policy = generate_policy(release_health_html=_with_26h2_ga(_html()), atom_feed_xml=_atom())

    assert policy.broad_target_existing_devices is not None
    assert policy.broad_target_existing_devices.version == "26H2"
    assert policy.broad_target_existing_devices.build_family == 28200


def test_future_27h1_special_does_not_choose_27h1():
    policy = generate_policy(release_health_html=_with_27h1_special(_with_26h2_ga(_html())), atom_feed_xml=_atom())

    assert policy.broad_target_existing_devices is not None
    assert policy.broad_target_existing_devices.version == "26H2"
    special = {entry.version for entry in policy.special_releases}
    assert "27H1" in special


def test_atom_feed_marks_preview_when_table_is_ambiguous():
    html = _html().replace("2026-04 D", "2026-04")
    policy = generate_policy(release_health_html=html, atom_feed_xml=_atom())
    row = next(row for row in policy.release_history if row.kb_article == "KB5083631")

    assert row.preview is True
    assert row.update_type_letter == "D"
    assert row.metadata["atom_enriched"] is True
    assert row.kb_url == "https://support.microsoft.com/help/5083631"
    assert row.catalog_url == "https://www.catalog.update.microsoft.com/Search.aspx?q=KB5083631"


def test_atom_feed_marks_oob_when_table_is_ambiguous():
    policy = generate_policy(release_health_html=_with_oob_row(_html()), atom_feed_xml=_atom())
    row = next(row for row in policy.release_history if row.kb_article == "KB5089550")

    assert row.out_of_band is True
    assert row.update_type_letter == "OOB"
    assert row.metadata["atom_enriched"] is True
    assert any(item["kb_article"] == "KB5089550" for item in policy.out_of_band_builds)


def test_source_diagnostics_notice_when_atom_oob_is_newer_than_release_history():
    policy = generate_policy(
        release_health_html=_html(),
        atom_feed_xml=_atom(),
        generated_at_utc="2026-05-20T00:00:00+00:00",
    )
    diagnostics = policy.source_diagnostics
    drift = diagnostics["drift"]["atom_newer_than_release_history"]
    events = diagnostics["events"]

    assert drift[0]["build"] == "26200.8460"
    assert drift[0]["kb_article"] == "KB5089550"
    assert drift[0]["out_of_band"] is True
    assert diagnostics["drift"]["generated_after_newest_source_hours"] == 78.0
    assert any(
        event["kind"] == "atom_newer_than_release_history"
        and event["severity"] == "notice"
        and event["affects_required_baseline"] is False
        for event in events
    )
    assert not any("Atom feed shows a newer non-preview build" in warning for warning in policy.validation_warnings)


def test_source_diagnostics_warn_when_atom_has_newer_b_release_for_broad_target():
    policy = generate_policy(
        release_health_html=_html(),
        atom_feed_xml=_atom_with_new_b_release(),
        generated_at_utc="2026-06-10T00:00:00+00:00",
    )
    events = policy.source_diagnostics["events"]

    event = next(
        event
        for event in events
        if event["kind"] == "atom_newer_than_release_history" and event["build"] == "26200.8461"
    )
    assert event["severity"] == "warning"
    assert event["release"] == "25H2"
    assert event["affects_broad_target"] is True
    assert event["affects_required_baseline"] is True
    assert any("newer non-preview build for the broad target" in warning for warning in policy.validation_warnings)


def test_source_diagnostics_dedupes_duplicate_atom_events():
    policy = generate_policy(
        release_health_html=_html(),
        atom_feed_xml=_atom_with_duplicate_new_b_release(),
    )
    events = [
        event
        for event in policy.source_diagnostics["events"]
        if event["kind"] == "atom_newer_than_release_history"
        and event["build"] == "26200.8461"
        and event["kb_article"] == "KB5089600"
    ]

    assert len(events) == 1


def test_source_diagnostics_warn_when_current_versions_lag_release_history():
    policy = generate_policy(release_health_html=_with_oob_row(_html()), atom_feed_xml=_atom())
    drift = policy.source_diagnostics["drift"]["current_version_latest_older_than_release_history"]

    assert drift[0]["version"] == "25H2"
    assert drift[0]["latest_build"] == "26200.8457"
    assert drift[0]["newest_release_history_build"] == "26200.8460"
    assert any("Current Versions latest_build appears older" in warning for warning in policy.validation_warnings)


def test_policy_schema_accepts_source_diagnostics_without_unknown_key_warning():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=_atom())

    warnings = validate_policy_document(policy.to_dict())

    assert not any("unknown top-level key 'source_diagnostics'" in warning for warning in warnings)


def test_policy_schema_accepts_structured_source_diagnostics_events():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=_atom_with_new_b_release())
    data = policy.to_dict()

    validate_policy_document(data)

    assert data["source_diagnostics"]["events"]
    assert data["source_diagnostics"]["event_counts"]["warning"] >= 1


def test_policy_schema_rejects_invalid_source_diagnostics_shape():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=_atom())
    data = policy.to_dict()
    data["source_diagnostics"] = {"release_health_html": "not an object"}

    with pytest.raises(PolicyParseError, match="source_diagnostics.release_health_html"):
        validate_policy_document(data)


def test_policy_schema_rejects_invalid_source_diagnostics_event_counts():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=_atom())
    data = policy.to_dict()
    data["source_diagnostics"]["event_counts"]["warning"] = -1

    with pytest.raises(PolicyParseError, match="source_diagnostics.event_counts.warning"):
        validate_policy_document(data)


def test_b_release_quality_baseline_does_not_require_preview():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=_atom())
    baseline = policy.quality_baselines["25H2"][QualityPolicy.B_RELEASE_ONLY.value]

    assert baseline["build"] == "26200.8457"
    assert baseline["preview"] is False


def test_current_table_preview_latest_stays_distinct_from_required_baseline():
    policy = generate_policy(
        release_health_html=_with_25h2_current_latest_build(_html(), "26200.8524"),
        atom_feed_xml=_atom(),
    )
    validate_policy_document(policy.to_dict())
    target = policy.broad_target_existing_devices
    baseline = policy.quality_baselines["25H2"][QualityPolicy.B_RELEASE_ONLY.value]

    assert target is not None
    assert target.latest_build == "26200.8524"
    assert target.latest_observed_build == "26200.8524"
    assert target.baseline_build == "26200.8457"
    assert target.required_baseline_build == "26200.8457"
    current_25h2 = next(entry for entry in policy.current_versions if entry.version == "25H2")
    assert current_25h2.latest_build == "26200.8524"
    assert current_25h2.latest_observed_build == "26200.8524"
    assert current_25h2.baseline_build == "26200.8457"
    assert current_25h2.required_baseline_build == "26200.8457"
    assert baseline["build"] == "26200.8457"
    assert baseline["preview"] is False


def test_missing_atom_feed_still_generates_policy_with_warning():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml=None)

    assert policy.broad_target_existing_devices is not None
    assert policy.broad_target_existing_devices.version == "25H2"
    assert any("Atom feed missing" in warning for warning in policy.validation_warnings)
    event = next(event for event in policy.source_diagnostics["events"] if event["kind"] == "atom_feed_missing")
    assert event["severity"] == "warning"
    assert event["affects_required_baseline"] is False


def test_atom_feed_parse_failure_is_structured_source_diagnostic():
    policy = generate_policy(release_health_html=_html(), atom_feed_xml="<feed>")

    assert any("Atom feed could not be parsed" in warning for warning in policy.validation_warnings)
    event = next(event for event in policy.source_diagnostics["events"] if event["kind"] == "atom_feed_parse_failed")
    assert event["severity"] == "warning"
    assert "Atom feed could not be parsed" in event["message"]


def test_parse_atom_feed_extracts_kb_build_and_classification():
    entries = parse_atom_feed(_atom())
    preview = next(entry for entry in entries if entry.kb_article == "KB5083631")
    oob = next(entry for entry in entries if entry.kb_article == "KB5089550")

    assert preview.preview is True
    assert preview.builds == ("26200.8328",)
    assert oob.out_of_band is True


def test_generator_source_failure_exits_nonzero_and_explains_failure(tmp_path, capsys):
    code = generate_policy_cli.main([
        "--release-health-html",
        str(tmp_path / "missing.html"),
        "--atom-feed",
        str(FIXTURES / "windows11-atom.xml"),
        "--output-dir",
        str(tmp_path / "site"),
    ])

    captured = capsys.readouterr()
    assert code == 1
    assert "release_health_html source failure" in captured.err


def test_generator_cli_writes_pages_support_files(tmp_path):
    output_dir = tmp_path / "site"

    code = generate_policy_cli.main([
        "--release-health-html",
        str(FIXTURES / "windows11-release-health.html"),
        "--atom-feed",
        str(FIXTURES / "windows11-atom.xml"),
        "--output-dir",
        str(output_dir),
        "--write-index",
        "--write-robots",
        "--write-sitemap",
        "--write-manifest",
    ])

    assert code == 0
    assert (output_dir / "windows-release-policy.json").exists()
    assert (output_dir / "index.html").exists()
    assert (output_dir / "robots.txt").exists()
    assert (output_dir / "sitemap.xml").exists()
    assert (output_dir / "policy-manifest.json").exists()
    assert (output_dir / "api/v1/policy.json").exists()
    assert (output_dir / "api/v1/manifest.json").exists()
    assert (output_dir / ".nojekyll").exists()
    assert (output_dir / "robots.txt").read_bytes() == EXPECTED_ROBOTS_TXT.encode("utf-8")


def test_signed_pages_output_contains_manifest_aliases_and_polished_index(tmp_path):
    policy = generate_policy(
        release_health_html=_html(),
        atom_feed_xml=_atom(),
        generated_at_utc="2026-05-31T14:11:50+00:00",
        signature_status="valid",
    )
    written = write_policy_outputs(
        policy,
        output_dir=tmp_path,
        signing_key="krtF2muLgucP7JDVNKk2g+YQfz92c7xM49dzszxHxjs=",
        key_id="test-policy-key",
        write_index=True,
        write_robots=True,
        write_sitemap=True,
        write_manifest=True,
    )

    expected = {
        "index.html",
        "windows-release-policy.json",
        "windows-release-policy.json.sig",
        "policy-manifest.json",
        "api/v1/policy.json",
        "api/v1/policy.sig",
        "api/v1/manifest.json",
        "robots.txt",
        "sitemap.xml",
        ".nojekyll",
    }
    actual = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()}

    assert expected <= actual
    assert (tmp_path / "api/v1/policy.json").read_bytes() == (tmp_path / "windows-release-policy.json").read_bytes()
    assert (tmp_path / "api/v1/policy.sig").read_bytes() == (tmp_path / "windows-release-policy.json.sig").read_bytes()
    assert (tmp_path / "api/v1/manifest.json").read_bytes() == (tmp_path / "policy-manifest.json").read_bytes()

    policy_bytes = (tmp_path / "windows-release-policy.json").read_bytes()
    signature_bytes = (tmp_path / "windows-release-policy.json.sig").read_bytes()
    manifest = json.loads((tmp_path / "policy-manifest.json").read_text(encoding="utf-8"))
    generated_policy = json.loads((tmp_path / "windows-release-policy.json").read_text(encoding="utf-8"))
    api_policy = json.loads((tmp_path / "api/v1/policy.json").read_text(encoding="utf-8"))
    api_manifest = json.loads((tmp_path / "api/v1/manifest.json").read_text(encoding="utf-8"))
    assert manifest["policy_sha256"] == hashlib.sha256(policy_bytes).hexdigest()
    assert manifest["signature_sha256"] == hashlib.sha256(signature_bytes).hexdigest()
    assert manifest["signature_algorithm"] == "ed25519"
    assert manifest["key_id"] == "test-policy-key"
    assert manifest["policy_schema_version"] == 1
    assert manifest["min_reader_schema_version"] == 1
    assert manifest["max_reader_schema_version"] == 1
    assert manifest["api_version"] == "v1"
    assert manifest["compatibility"]["required_core_schema_version"] == 1
    assert manifest["generated_at_epoch_s"] == 1780236710
    assert manifest["warn_after_epoch_s"] == 1781446310
    assert manifest["stale_after_epoch_s"] == 1784124710
    assert manifest["strict_stale_after_epoch_s"] == 1784124710
    assert manifest["max_ok_age_seconds"] == DEFAULT_POLICY_WARNING_AGE_SECONDS
    assert manifest["warning_age_seconds"] == DEFAULT_POLICY_WARNING_AGE_SECONDS
    assert manifest["strict_stale_age_seconds"] == DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS
    assert manifest["freshness_policy"] == {
        "warning_after_days": 14,
        "strict_stale_after_days": 45,
        "max_ok_age_seconds": DEFAULT_POLICY_WARNING_AGE_SECONDS,
        "warning_age_seconds": DEFAULT_POLICY_WARNING_AGE_SECONDS,
        "strict_stale_age_seconds": DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS,
        "client_recomputes_age": True,
    }
    assert api_policy == generated_policy
    assert api_manifest == manifest
    assert manifest["timezone"] == "Europe/Berlin"
    assert manifest["status"] == "Policy current"
    assert manifest["published_urls"]["policy"] == DEFAULT_POLICY_URL
    assert manifest["published_urls"]["api_policy"].endswith("/api/v1/policy.json")
    assert manifest["source_diagnostics"]["atom_feed"]["newest_atom_build"] == "26200.8460"
    assert manifest["broad_target_existing_devices"]["latest_observed_build"] == "26200.8457"
    assert manifest["broad_target_existing_devices"]["required_baseline_build"] == "26200.8457"
    assert manifest["required_baseline_build"] == "26200.8457"
    assert generated_policy["published_urls"] == DEFAULT_PUBLISHED_POLICY_URLS
    assert generated_policy["metadata"]["freshness_policy"]["warning_after_days"] == 14
    assert generated_policy["metadata"]["freshness_policy"]["strict_stale_after_days"] == 45
    assert generated_policy["metadata"]["freshness_policy"]["client_recomputes_age"] is True
    roundtripped_policy = ReleasePolicy.from_dict(generated_policy)
    assert roundtripped_policy.metadata["freshness_policy"]["warning_age_seconds"] == DEFAULT_POLICY_WARNING_AGE_SECONDS
    assert DEFAULT_RELEASE_HEALTH_URL in generated_policy["source_urls"]
    source_hosts = {urlparse(url).hostname for url in generated_policy["source_urls"]}
    assert "avnsx.github.io" not in source_hosts

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<title>Windows 11 Release Guard</title>" in index
    assert "<h1>Windows 11 Release Guard</h1>" in index
    assert "Broad-fleet Windows 11 release and quality baseline dashboard." in index
    assert 'class="header-nav"' in index
    assert 'class="nav-hover-label"' in index
    assert "nav-binoculars" not in index
    assert "main{position:relative;z-index:1;width:calc(100% - 80px);max-width:1580px" in index
    assert "backdrop-filter:blur(28px)" in index
    assert "body:before" in index
    assert "body:after" in index
    assert 'class="winmark"' in index
    assert "kpi-card" in index
    assert "icon-bubble" in index
    assert 'class="ui-icon' in index
    assert "freshness-ring" in index
    assert "panel-action" in index
    assert "diag-row-icon" in index
    assert "--item-size:42px" in index
    assert ".nav-hover-label{display:none}" in index
    assert 'id="policy-summary"' in index
    assert 'href="https://avnsx.github.io/win11_release_guard/"' in index
    assert 'data-nav-label="Dashboard"' in index
    assert "Dashboard" in index
    assert 'data-nav-label="Write a Issue Ticket"' in index
    assert "Write a Issue Ticket" in index
    assert "https://github.com/Avnsx/win11_release_guard/issues/new" in index
    assert 'data-nav-label="Wiki"' in index
    assert "Wiki" in index
    assert "https://github.com/Avnsx/win11_release_guard/wiki" in index
    assert "initHeaderNav" in index
    assert "reportUiError" in index
    assert "data-ui-last-error" in index
    assert "shutdownUi" in index
    assert "pagehide" in index
    assert "beforeunload" in index
    assert "safeSetTimeout" in index
    assert "safeSetInterval" in index
    assert "safeRequestFrame" in index
    assert "button.isConnected" in index
    assert "nav.isConnected" in index
    assert "freshness update" in index
    assert "Bookmarks" not in index
    assert "Blogs" not in index
    assert "E-books" not in index
    assert "Account" not in index
    assert "Menu" not in index
    assert "Policy current" not in index
    assert "25H2" in index
    assert "Latest observed" in index
    assert "Required baseline" in index
    assert "26200" in index
    assert "26200.8457" in index
    assert "b_release_only" in index
    assert "26H1 excluded for existing devices" in index
    assert (
        "26H1 is excluded for existing devices because Microsoft scopes it to new devices and does not offer "
        "it as an in-place update from 24H2/25H2."
    ) in index
    assert "Release policy notes" not in index
    assert "release-note" not in index
    assert "No source issues reported" in index
    assert index.find("No source issues reported") < index.find("26H1 excluded for existing devices")
    assert "existing devi." not in index
    assert "Microsoft Release Health" in index
    assert "Microsoft Atom feed" in index
    assert "Ed25519" in index or "ed25519" in index
    assert "test-policy-key" in index
    assert "/windows-release-policy.json" in index
    assert "/windows-release-policy.json.sig" in index
    assert "/policy-manifest.json" in index
    assert "/api/v1/policy.json" in index
    assert "/api/v1/manifest.json" in index
    assert "Programmatic JSON endpoint" not in index
    assert "Independent Windows release-policy dashboard. Not affiliated with Microsoft." in index
    assert "&copy; 2026 Mikail (&quot;Avnsx&quot;) C. Maintained as an open-source project." in index
    assert "Source code and documentation are available on" in index
    assert "provided under the" in index
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
    assert "https://github.com/Avnsx/win11_release_guard/blob/main/LICENSE.txt" in index
    assert "github-icon" in index
    assert ">LICENSE.txt<" not in index
    assert "Europe/Berlin" not in index
    assert "Sunday, 31 May 2026, 16:11:50 CEST" in index
    assert "Generated age" not in index
    assert "Policy Feed Currency" in index
    assert "Published feed age" in index
    assert "days at render-time fallback" in index
    assert "Browser recalculates published policy feed age from the GitHub Actions generated timestamp" in index
    assert "Date.now" in index
    assert "Current" in index
    assert "Refresh Due" in index
    assert "Stale" in index
    assert "Published policy feed currency: Unknown" in index
    assert "Workflow refresh" in index
    assert "GitHub workflow static feed generation" in index
    assert "Release Health fetched" not in index
    assert "Atom feed fetched" not in index
    assert "Berlin, Germany" in index
    assert "Program versioning" not in index
    assert "Program Version" in index
    program_version = GENERATOR_VERSION.rsplit("/", 1)[-1]
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
    assert "<h2>Sources</h2>" not in index
    assert "sources-panel" not in index
    assert "source-health" in index
    assert "source-tile ok" in index
    assert "source-status" in index
    assert "Signed policy trust" in index
    assert "Signature status" in index
    assert "signature-head" in index
    assert "signature-status-card" in index
    assert "Document trust state" in index
    assert "Detached signature metadata for the published policy artifact." in index
    assert "signature-kv" in index
    assert "<dt>Algorithm</dt>" in index
    assert "<dt>key_id</dt>" in index
    assert "<dt>Policy SHA-256</dt>" in index
    assert "<dt>Signature status</dt>" in index
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
    assert ".signature-panel,.programmatic-api{grid-column:1/-1}" in index
    assert "Notices" in index
    assert "Warnings" in index
    assert "Errors" in index
    assert "auth" not in index.lower()
    assert "token" not in index.lower()
    assert "private-" + "key" not in index.lower()
    assert "http://cdn" not in index.lower()
    assert "https://cdn" not in index.lower()
    assert '<script type="application/json" id="policy-freshness-data">' in index
    assert "script src" not in index.lower()

    assert render_robots_txt() == EXPECTED_ROBOTS_TXT
    assert (tmp_path / "robots.txt").read_bytes() == EXPECTED_ROBOTS_TXT.encode("utf-8")

    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://avnsx.github.io/win11_release_guard/" in sitemap
    assert "https://avnsx.github.io/win11_release_guard/windows-release-policy.json" in sitemap
    assert "https://avnsx.github.io/win11_release_guard/policy-manifest.json" in sitemap

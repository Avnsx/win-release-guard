from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from xml.etree import ElementTree

from .config import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_PAGES_BASE_URL,
    DEFAULT_PUBLISHED_POLICY_URLS,
    DEFAULT_POLICY_STRICT_STALE_AGE_DAYS,
    DEFAULT_POLICY_WARNING_AGE_DAYS,
    DEFAULT_RELEASE_HEALTH_URL,
    DEFAULT_TRUSTED_POLICY_KEY_ID,
    DEFAULT_USER_AGENT,
)
from .exceptions import PolicyFetchError, PolicyParseError
from .freshness import (
    epoch_milliseconds_from_iso,
    freshness_policy_metadata,
    freshness_thresholds,
    parse_iso_utc_datetime,
)
from .json_utils import DEFAULT_MAX_MICROSOFT_SOURCE_BYTES
from .models import QualityPolicy, ReleaseHistoryEntry, ReleasePolicy, ReleasePolicyEntry
from .policy_schema import (
    GENERATOR_VERSION,
    SUPPORTED_POLICY_SCHEMA_VERSION,
    policy_document_to_json,
    validate_policy_document,
)
from .remote_policy import parse_windows11_release_health_html
from .signing import sign_policy_bytes as sign_ed25519_policy_bytes


DEFAULT_WINDOWS11_ATOM_FEED_URL = "https://support.microsoft.com/en-us/feed/atom/4ec863cc-2ecd-e187-6cb3-b50c6545db92"
GITHUB_RELEASES_BASE_URL = "https://github.com/Avnsx/win11_release_guard/releases/tag"
GITHUB_LICENSE_URL = "https://github.com/Avnsx/win11_release_guard/blob/main/LICENSE.txt"
GITHUB_REPOSITORY_URL = "https://github.com/Avnsx/win11_release_guard"
PAGES_TIMEZONE = "Europe/Berlin"
ROBOTS_TXT = (
    "User-agent: *\n"
    "Allow: /\n"
    "Sitemap: https://avnsx.github.io/win11_release_guard/sitemap.xml\n"
)
CURATED_EXCLUDED_RELEASE_SUMMARIES = {
    "26H1": (
        "26H1 is excluded for existing devices because Microsoft scopes it to new devices and does not offer "
        "it as an in-place update from 24H2/25H2."
    )
}
_RELEASE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class SourceText:
    text: str
    status: Mapping[str, Any]


_LAST_UTC_NOW_MS = 0


@dataclass(frozen=True)
class AtomFeedEntry:
    title: str
    link: str | None = None
    published: str | None = None
    updated: str | None = None
    content: str | None = None
    kb_article: str | None = None
    builds: tuple[str, ...] = ()
    preview: bool = False
    out_of_band: bool = False


def _utc_now() -> str:
    global _LAST_UTC_NOW_MS
    epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if epoch_ms <= _LAST_UTC_NOW_MS:
        epoch_ms = _LAST_UTC_NOW_MS + 1
    _LAST_UTC_NOW_MS = epoch_ms
    seconds, milliseconds = divmod(epoch_ms, 1000)
    return datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=milliseconds * 1000).isoformat(
        timespec="milliseconds"
    )


def _parse_policy_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _last_sunday(year: int, month: int) -> datetime:
    if month == 12:
        day = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    else:
        day = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day.replace(hour=1, minute=0, second=0, microsecond=0)


def _berlin_offset_hours(utc_dt: datetime) -> tuple[int, str]:
    start = _last_sunday(utc_dt.year, 3)
    end = _last_sunday(utc_dt.year, 10)
    if start <= utc_dt < end:
        return 2, "CEST"
    return 1, "CET"


def _generated_at_human(value: str | None) -> str:
    utc_dt = _parse_policy_datetime(value)
    offset_hours, label = _berlin_offset_hours(utc_dt)
    local_dt = utc_dt.replace(tzinfo=None) + timedelta(hours=offset_hours)
    weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    return (
        f"{weekdays[local_dt.weekday()]}, {local_dt.day} {months[local_dt.month - 1]} "
        f"{local_dt.year}, {local_dt:%H:%M:%S} {label}"
    )


def _utc_time_human(value: str | None) -> str:
    utc_dt = parse_iso_utc_datetime(value)
    if utc_dt is None:
        return "unavailable"
    weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    return (
        f"{weekdays[utc_dt.weekday()]}, {utc_dt.day} {months[utc_dt.month - 1]} "
        f"{utc_dt.year}, {utc_dt:%H:%M:%S} UTC"
    )


def _epoch_copy_icon_html() -> str:
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M8 7.5A2.5 2.5 0 0 1 10.5 5h6A2.5 2.5 0 0 1 19 7.5v6A2.5 2.5 0 0 1 16.5 16h-6A2.5 2.5 0 0 1 8 13.5z" '
        'fill="none" stroke="currentColor" stroke-width="1.8"/>'
        '<path d="M5 10.5A2.5 2.5 0 0 1 7.5 8H8v5.5A2.5 2.5 0 0 0 10.5 16H16v.5A2.5 2.5 0 0 1 13.5 19h-6A2.5 2.5 0 0 1 5 16.5z" '
        'fill="none" stroke="currentColor" stroke-width="1.8"/>'
        "</svg>"
    )


def _github_icon_html() -> str:
    return (
        '<svg class="github-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
        '<path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38'
        ' 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52'
        '-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2'
        '-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82'
        '.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08'
        ' 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48'
        ' 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/>'
        "</svg>"
    )


def _footer_html() -> str:
    return (
        "<footer>"
        '<p class="footer-note footer-disclaimer">Independent Windows release-policy dashboard. Not affiliated with Microsoft.</p>'
        '<p class="footer-note footer-owner">&copy; 2026 Mikail (&quot;Avnsx&quot;) C. Maintained as an open-source project.</p>'
        '<p class="footer-note footer-source">'
        "Source code and documentation are available on "
        f'<a class="footer-github" href="{escape(GITHUB_REPOSITORY_URL, quote=True)}">'
        f"{_github_icon_html()}<span>GitHub</span></a>, provided under the "
        f'<a class="footer-license-basic" href="{escape(GITHUB_LICENSE_URL, quote=True)}">GPL-3.0 license</a></p>'
        "</footer>"
    )


def _time_with_epoch_copy_html(value: str | None, *, label: str) -> str:
    utc_dt = parse_iso_utc_datetime(value)
    epoch_ms = epoch_milliseconds_from_iso(value)
    if utc_dt is None or epoch_ms is None:
        return '<span class="time-copy unavailable">unavailable</span>'
    iso_value = utc_dt.isoformat()
    display = _utc_time_human(iso_value)
    escaped_epoch = escape(str(epoch_ms), quote=True)
    escaped_label = escape(label, quote=True)
    return (
        '<span class="time-copy">'
        f'<time datetime="{escape(iso_value, quote=True)}">{escape(display)}</time>'
        '<button type="button" class="epoch-copy" '
        f'data-epoch="{escaped_epoch}" '
        f'aria-label="Copy {escaped_label} epoch millisecond timestamp {escaped_epoch}" '
        f'title="Copy epoch millisecond timestamp {escaped_epoch}">'
        f"{_epoch_copy_icon_html()}"
        "</button></span>"
    )


def _generated_age_days(value: str | None, *, reference: datetime | None = None) -> float:
    generated = _parse_policy_datetime(value)
    now = reference or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return round(max(0.0, (now.astimezone(timezone.utc) - generated).total_seconds() / 86400), 2)


def _content_length_from_headers(headers: Mapping[str, object] | None) -> int | None:
    if headers is None:
        return None
    value = None
    if hasattr(headers, "get"):
        value = headers.get("content-length") or headers.get("Content-Length")
    if value is None and hasattr(headers, "items"):
        for key, candidate in headers.items():
            if str(key).lower() == "content-length":
                value = candidate
                break
    if value is None:
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _fetch_url(
    url: str,
    *,
    timeout: float,
    max_bytes: int = DEFAULT_MAX_MICROSOFT_SOURCE_BYTES,
) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/atom+xml,application/xml,text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        content_length = _content_length_from_headers(response.headers)
        if content_length is not None and content_length > max_bytes:
            raise PolicyFetchError(
                f"Microsoft source response is too large: exceeds safety cap of {max_bytes} bytes."
            )
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise PolicyFetchError(
                f"Microsoft source response is too large: exceeds safety cap of {max_bytes} bytes."
            )
        return data.decode(charset, errors="replace")


def load_source_text(
    *,
    url: str,
    fixture_path: str | Path | None = None,
    source_name: str,
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    required: bool = True,
) -> SourceText:
    if fixture_path is not None:
        path = Path(fixture_path)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            if required:
                raise PolicyFetchError(f"{source_name} source failure: could not read {path}: {exc}") from exc
            return SourceText(
                text="",
                status={
                    "url": url,
                    "source": "fixture",
                    "path": str(path),
                    "status": "error",
                    "error": str(exc),
                    "fetched_at_utc": _utc_now(),
                },
            )
        return SourceText(
            text=text,
            status={
                "url": url,
                "source": "fixture",
                "path": str(path),
                "status": "ok",
                "bytes": len(text.encode("utf-8")),
                "fetched_at_utc": _utc_now(),
            },
        )

    try:
        text = _fetch_url(url, timeout=timeout)
    except Exception as exc:
        if required:
            raise PolicyFetchError(f"{source_name} source failure: could not fetch {url}: {exc}") from exc
        return SourceText(
            text="",
            status={
                "url": url,
                "source": "network",
                "status": "error",
                "error": str(exc),
                "fetched_at_utc": _utc_now(),
            },
        )
    return SourceText(
        text=text,
        status={
            "url": url,
            "source": "network",
            "status": "ok",
            "bytes": len(text.encode("utf-8")),
            "fetched_at_utc": _utc_now(),
        },
    )


def _text(element: ElementTree.Element, name: str, ns: Mapping[str, str]) -> str | None:
    child = element.find(name, ns)
    if child is None or child.text is None:
        return None
    text = re.sub(r"\s+", " ", child.text).strip()
    return text or None


def _link(element: ElementTree.Element, ns: Mapping[str, str]) -> str | None:
    for link in element.findall("atom:link", ns):
        href = link.attrib.get("href")
        if href:
            return href
    return None


def _extract_kb(text: str | None) -> str | None:
    match = re.search(r"\bKB\d{6,8}\b", text or "", flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_builds(text: str | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"\b\d{5}\.\d+\b", text or "")))


def _is_preview(text: str) -> bool:
    return "preview" in text.lower()


def _is_out_of_band(text: str) -> bool:
    normalized = text.lower().replace("_", "-")
    return "out-of-band" in normalized or "out of band" in normalized or re.search(r"\boob\b", normalized) is not None


def parse_atom_feed(xml_text: str) -> tuple[AtomFeedEntry, ...]:
    if not xml_text.strip():
        return ()

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise PolicyParseError(f"Atom feed is malformed: {exc}") from exc

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    if not entries:
        entries = root.findall("entry")

    parsed: list[AtomFeedEntry] = []
    for entry in entries:
        title = _text(entry, "atom:title", ns) or _text(entry, "title", ns) or ""
        content = _text(entry, "atom:content", ns) or _text(entry, "content", ns)
        published = _text(entry, "atom:published", ns) or _text(entry, "published", ns)
        updated = _text(entry, "atom:updated", ns) or _text(entry, "updated", ns)
        link = _link(entry, ns)
        blob = " ".join(part for part in (title, content or "") if part)
        kb_article = _extract_kb(blob)
        parsed.append(
            AtomFeedEntry(
                title=title,
                link=link,
                published=published,
                updated=updated,
                content=content,
                kb_article=kb_article,
                builds=_extract_builds(blob),
                preview=_is_preview(blob),
                out_of_band=_is_out_of_band(blob),
            )
        )
    return tuple(parsed)


def _release_key(release: str | None) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{2})H([12])", release or "", flags=re.IGNORECASE)
    if not match:
        return (-1, -1)
    return int(match.group(1)), int(match.group(2))


def _build_key(build: str | None) -> tuple[int, int]:
    if not build:
        return (-1, -1)
    try:
        major, minor = str(build).split(".", 1)
        return int(major), int(minor)
    except ValueError:
        return (-1, -1)


def _history_sort_key(row: ReleaseHistoryEntry) -> tuple[str, tuple[int, int]]:
    return row.availability_date or "", _build_key(row.build)


def _kb_url(kb_article: str | None, feed_entry: AtomFeedEntry | None = None) -> str | None:
    if feed_entry and feed_entry.link:
        return feed_entry.link
    kb = _extract_kb(kb_article)
    if not kb:
        return None
    return f"https://support.microsoft.com/help/{kb[2:]}"


def _catalog_url(kb_article: str | None) -> str | None:
    kb = _extract_kb(kb_article)
    if not kb:
        return None
    return f"https://www.catalog.update.microsoft.com/Search.aspx?q={kb}"


def _match_atom(row: ReleaseHistoryEntry, entries: tuple[AtomFeedEntry, ...]) -> AtomFeedEntry | None:
    row_kb = _extract_kb(row.kb_article)
    if row_kb:
        for entry in entries:
            if entry.kb_article == row_kb:
                return entry
    for entry in entries:
        if row.build in entry.builds:
            return entry
    return None


def _enrich_history(
    release_history: tuple[ReleaseHistoryEntry, ...],
    atom_entries: tuple[AtomFeedEntry, ...],
) -> tuple[ReleaseHistoryEntry, ...]:
    enriched: list[ReleaseHistoryEntry] = []
    for row in release_history:
        atom_entry = _match_atom(row, atom_entries)
        preview = row.preview or bool(atom_entry and atom_entry.preview)
        out_of_band = row.out_of_band or bool(atom_entry and atom_entry.out_of_band)
        update_type_letter = row.update_type_letter
        if out_of_band:
            update_type_letter = "OOB"
        elif preview and not update_type_letter:
            update_type_letter = "D"

        metadata = dict(row.metadata)
        if atom_entry:
            metadata.update(
                {
                    "atom_enriched": True,
                    "atom_feed_title": atom_entry.title,
                    "atom_feed_url": atom_entry.link,
                    "atom_published": atom_entry.published,
                    "atom_updated": atom_entry.updated,
                }
            )

        enriched.append(
            replace(
                row,
                preview=preview,
                out_of_band=out_of_band,
                update_type_letter=update_type_letter,
                kb_url=_kb_url(row.kb_article, atom_entry) or row.kb_url,
                catalog_url=_catalog_url(row.kb_article) or row.catalog_url,
                metadata=metadata,
            )
        )
    return tuple(enriched)


def _entry_with_special_flag(entry: ReleasePolicyEntry) -> ReleasePolicyEntry:
    metadata = dict(entry.metadata)
    if metadata.get("not_broad_target"):
        metadata["not_broad_target_existing_devices"] = True
    return replace(entry, metadata=metadata)


def _baseline_for(
    rows: tuple[ReleaseHistoryEntry, ...],
    release: str,
    policy: QualityPolicy,
) -> ReleaseHistoryEntry | None:
    release_rows = [row for row in rows if row.release == release.upper()]
    if policy is QualityPolicy.B_RELEASE_ONLY:
        candidates = [
            row
            for row in release_rows
            if row.update_type_letter == "B" and not row.preview
        ]
    elif policy is QualityPolicy.LATEST_NON_PREVIEW:
        candidates = [row for row in release_rows if not row.preview]
    else:
        candidates = release_rows
    if not candidates:
        return None
    return max(candidates, key=_history_sort_key)


def _quality_baselines(release_history: tuple[ReleaseHistoryEntry, ...]) -> dict[str, dict[str, dict[str, Any]]]:
    releases = sorted({row.release for row in release_history}, key=_release_key)
    baselines: dict[str, dict[str, dict[str, Any]]] = {}
    for release in releases:
        release_baselines: dict[str, dict[str, Any]] = {}
        for policy in (
            QualityPolicy.B_RELEASE_ONLY,
            QualityPolicy.LATEST_NON_PREVIEW,
            QualityPolicy.LATEST_ANYTHING,
        ):
            baseline = _baseline_for(release_history, release, policy)
            if baseline is not None:
                release_baselines[policy.value] = baseline.to_dict()
        if release_baselines:
            baselines[release] = release_baselines
    return baselines


def _parse_source_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _newest_timestamp(values: list[str | None]) -> str | None:
    candidates = [(parsed, value) for value in values if (parsed := _parse_source_timestamp(value))]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _newest_current_version_revision_date(entries: tuple[ReleasePolicyEntry, ...]) -> str | None:
    values: list[str | None] = []
    for entry in entries:
        raw = entry.metadata.get("raw") if isinstance(entry.metadata.get("raw"), Mapping) else {}
        if isinstance(raw, Mapping):
            values.append(str(raw.get("Latest revision date") or "") or None)
        values.append(str(entry.metadata.get("latest_revision_date") or "") or None)
    return _newest_timestamp(values)


def _newest_release_history_availability_date(rows: tuple[ReleaseHistoryEntry, ...]) -> str | None:
    return _newest_timestamp([row.availability_date for row in rows])


def _newest_atom_timestamp(entries: tuple[AtomFeedEntry, ...], field: str) -> str | None:
    return _newest_timestamp([getattr(entry, field) for entry in entries])


def _history_release_by_family(rows: tuple[ReleaseHistoryEntry, ...]) -> dict[int, str]:
    releases: dict[int, str] = {}
    for row in rows:
        current = releases.get(row.build_family)
        if current is None or _release_key(row.release) > _release_key(current):
            releases[row.build_family] = row.release
    return releases


def _history_build_maps(rows: tuple[ReleaseHistoryEntry, ...]) -> tuple[dict[int, tuple[int, int]], set[str], set[str]]:
    newest_by_family: dict[int, tuple[int, int]] = {}
    builds: set[str] = set()
    kbs: set[str] = set()
    for row in rows:
        builds.add(row.build)
        kb = _extract_kb(row.kb_article)
        if kb:
            kbs.add(kb)
        current = newest_by_family.get(row.build_family, (-1, -1))
        newest_by_family[row.build_family] = max(current, _build_key(row.build))
    return newest_by_family, builds, kbs


def _atom_newer_than_history(
    atom_entries: tuple[AtomFeedEntry, ...],
    release_history: tuple[ReleaseHistoryEntry, ...],
) -> tuple[dict[str, Any], ...]:
    newest_by_family, history_builds, history_kbs = _history_build_maps(release_history)
    release_by_family = _history_release_by_family(release_history)
    missing: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for entry in atom_entries:
        kb = _extract_kb(entry.kb_article)
        for build in entry.builds:
            family = _build_key(build)[0]
            if family < 0:
                continue
            if build in history_builds:
                continue
            if _build_key(build) <= newest_by_family.get(family, (-1, -1)):
                continue
            key = (build, kb)
            if key in seen:
                continue
            seen.add(key)
            missing.append(
                {
                    "release": release_by_family.get(family),
                    "build": build,
                    "build_family": family,
                    "kb_article": kb,
                    "preview": entry.preview,
                    "out_of_band": entry.out_of_band,
                    "kb_missing_from_release_history": bool(kb and kb not in history_kbs),
                    "published": entry.published,
                    "updated": entry.updated,
                    "title": entry.title,
                }
            )
    return tuple(missing)


def _current_version_latest_older_than_history(
    current_versions: tuple[ReleasePolicyEntry, ...],
    release_history: tuple[ReleaseHistoryEntry, ...],
) -> tuple[dict[str, Any], ...]:
    newest_by_family, _history_builds, _history_kbs = _history_build_maps(release_history)
    stale: list[dict[str, Any]] = []
    for entry in current_versions:
        newest_history_key = newest_by_family.get(entry.build_family)
        if newest_history_key is None or _build_key(entry.latest_build) >= newest_history_key:
            continue
        newest_history_build = max(
            (row.build for row in release_history if row.build_family == entry.build_family),
            key=_build_key,
        )
        stale.append(
            {
                "version": entry.version,
                "build_family": entry.build_family,
                "latest_build": entry.latest_build,
                "newest_release_history_build": newest_history_build,
            }
        )
    return tuple(stale)


def _newest_atom_build(entries: tuple[AtomFeedEntry, ...]) -> str | None:
    builds = [build for entry in entries for build in entry.builds]
    if not builds:
        return None
    return max(builds, key=_build_key)


def _event_key(item: Mapping[str, Any]) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    return (
        str(item.get("severity")) if item.get("severity") is not None else None,
        str(item.get("kind")) if item.get("kind") is not None else None,
        str(item.get("release")) if item.get("release") is not None else None,
        str(item.get("build")) if item.get("build") is not None else None,
        str(item.get("kb_article")) if item.get("kb_article") is not None else None,
    )


def _dedupe_source_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None, str | None, str | None]] = set()
    for event in events:
        key = _event_key(event)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(event))
    return deduped


def _source_event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"notice": 0, "warning": 0, "error": 0}
    for event in events:
        severity = str(event.get("severity") or "")
        if severity in counts:
            counts[severity] += 1
    return counts


def _atom_newer_event(item: Mapping[str, Any], target: ReleasePolicyEntry | None) -> dict[str, Any]:
    release = str(item.get("release") or "") or None
    build_family = item.get("build_family")
    affects_broad_target = bool(
        target is not None
        and release == target.version
        and build_family == target.build_family
    )
    affects_required_baseline = affects_broad_target and not bool(item.get("preview") or item.get("out_of_band"))
    severity = "warning" if affects_required_baseline else "notice"
    build = str(item.get("build") or "")
    kb_article = item.get("kb_article")
    if severity == "warning":
        message = (
            "Atom feed shows a newer non-preview build for the broad target that is not present "
            f"in Release Health release_history: {kb_article or 'unknown KB'} build {build}."
        )
    else:
        message = (
            "Atom feed has newer Preview/OOB or non-baseline update information not present in "
            f"Release Health release_history: {kb_article or 'unknown KB'} build {build}."
        )
    return {
        "severity": severity,
        "kind": "atom_newer_than_release_history",
        "release": release,
        "build_family": build_family,
        "build": build or None,
        "kb_article": kb_article,
        "affects_broad_target": affects_broad_target,
        "affects_required_baseline": affects_required_baseline,
        "message": message,
    }


def _current_versions_lag_event(item: Mapping[str, Any], target: ReleasePolicyEntry | None) -> dict[str, Any]:
    release = str(item.get("version") or "") or None
    build_family = item.get("build_family")
    build = item.get("newest_release_history_build")
    affects_broad_target = bool(
        target is not None
        and release == target.version
        and build_family == target.build_family
    )
    return {
        "severity": "warning",
        "kind": "current_versions_lag_release_history",
        "release": release,
        "build_family": build_family,
        "build": build,
        "kb_article": None,
        "affects_broad_target": affects_broad_target,
        "affects_required_baseline": False,
        "message": (
            "Current Versions latest_build appears older than Release History for "
            f"{release}/{build_family}: {item.get('latest_build') or 'unknown'} < {build}."
        ),
    }


def _source_diagnostic_messages(events: list[dict[str, Any]], *, minimum: str = "warning") -> list[str]:
    severities = {"notice": 0, "warning": 1, "error": 2}
    threshold = severities[minimum]
    return [
        str(event["message"])
        for event in events
        if severities.get(str(event.get("severity") or ""), -1) >= threshold
        and event.get("message")
    ]


def _source_diagnostic_notices(events: list[dict[str, Any]]) -> list[str]:
    return [
        str(event["message"])
        for event in events
        if event.get("severity") == "notice" and event.get("message")
    ]


def _source_input_event(kind: str, message: str, *, severity: str = "warning") -> dict[str, Any]:
    return {
        "severity": severity,
        "kind": kind,
        "release": None,
        "build_family": None,
        "build": None,
        "kb_article": None,
        "affects_broad_target": False,
        "affects_required_baseline": False,
        "message": message,
    }


def _source_status(
    source_fetch_status: Mapping[str, Any],
    key: str,
    *,
    source_url: str | None,
    text: str | None = None,
    generated_at_utc: str,
) -> dict[str, Any]:
    status = dict(source_fetch_status.get(key) or {})
    status.setdefault("url", source_url)
    status.setdefault("source", "direct")
    status.setdefault("status", "ok" if text else "missing")
    if text is not None:
        status.setdefault("bytes", len(text.encode("utf-8")))
    status.setdefault("fetched_at_utc", generated_at_utc)
    return status


def _source_diagnostics(
    *,
    current_versions: tuple[ReleasePolicyEntry, ...],
    release_history: tuple[ReleaseHistoryEntry, ...],
    atom_entries: tuple[AtomFeedEntry, ...],
    broad_target: ReleasePolicyEntry | None,
    parser_diagnostics: tuple[Mapping[str, Any], ...] = (),
    source_input_events: tuple[Mapping[str, Any], ...] = (),
    source_fetch_status: Mapping[str, Any],
    release_health_url: str,
    atom_feed_url: str | None,
    release_health_html: str,
    atom_feed_xml: str | None,
    generated_at_utc: str,
) -> dict[str, Any]:
    release_health_status = _source_status(
        source_fetch_status,
        "release_health_html",
        source_url=release_health_url,
        text=release_health_html,
        generated_at_utc=generated_at_utc,
    )
    atom_status = _source_status(
        source_fetch_status,
        "atom_feed",
        source_url=atom_feed_url,
        text=atom_feed_xml,
        generated_at_utc=generated_at_utc,
    )
    newest_current_revision = _newest_current_version_revision_date(current_versions)
    newest_history_availability = _newest_release_history_availability_date(release_history)
    newest_atom_updated = _newest_atom_timestamp(atom_entries, "updated")
    newest_atom_published = _newest_atom_timestamp(atom_entries, "published")
    atom_newer = _atom_newer_than_history(atom_entries, release_history)
    current_stale = _current_version_latest_older_than_history(current_versions, release_history)
    events = _dedupe_source_events(
        [
            *(dict(item) for item in parser_diagnostics),
            *(dict(item) for item in source_input_events),
            *(_atom_newer_event(item, broad_target) for item in atom_newer),
            *(_current_versions_lag_event(item, broad_target) for item in current_stale),
        ]
    )

    source_times = [
        newest_current_revision,
        newest_history_availability,
        newest_atom_updated,
        newest_atom_published,
    ]
    newest_source_timestamp = _newest_timestamp(source_times)
    generated_after_hours = None
    generated_dt = _parse_source_timestamp(generated_at_utc)
    newest_source_dt = _parse_source_timestamp(newest_source_timestamp)
    if generated_dt and newest_source_dt:
        generated_after_hours = round((generated_dt - newest_source_dt).total_seconds() / 3600, 2)

    if generated_after_hours is not None and generated_after_hours >= 24:
        has_unresolved_warning = any(str(event.get("severity")) in {"warning", "error"} for event in events)
        if has_unresolved_warning:
            events.append(
                {
                    "severity": "warning",
                    "kind": "source_drift_unresolved_after_24h",
                    "release": broad_target.version if broad_target else None,
                    "build_family": broad_target.build_family if broad_target else None,
                    "build": broad_target.latest_build if broad_target else None,
                    "kb_article": None,
                    "affects_broad_target": bool(broad_target),
                    "affects_required_baseline": False,
                    "message": (
                        "Policy was generated more than 24 hours after the newest source timestamp while "
                        "warning-level source drift diagnostics remain unresolved."
                    ),
                }
            )
    if (
        generated_after_hours is not None
        and generated_after_hours >= 24
        and not atom_entries
        and atom_status.get("status") != "ok"
    ):
        events.append(
            {
                "severity": "warning",
                "kind": "atom_diagnostics_unavailable",
                "release": broad_target.version if broad_target else None,
                "build_family": broad_target.build_family if broad_target else None,
                "build": broad_target.latest_build if broad_target else None,
                "kb_article": None,
                "affects_broad_target": bool(broad_target),
                "affects_required_baseline": False,
                "message": (
                    "Policy was generated more than 24 hours after the newest Release Health timestamp and "
                    "Atom diagnostics are unavailable; preview/out-of-band enrichment may be incomplete."
                ),
            }
        )
    events = _dedupe_source_events(events)
    warnings = list(dict.fromkeys(_source_diagnostic_messages(events, minimum="warning")))
    notices = list(dict.fromkeys(_source_diagnostic_notices(events)))

    return {
        "release_health_html": {
            "source_url": release_health_status.get("url"),
            "fetched_at_utc": release_health_status.get("fetched_at_utc"),
            "bytes": release_health_status.get("bytes"),
            "status": release_health_status.get("status"),
            "newest_current_version_revision_date": newest_current_revision,
            "newest_release_history_availability_date": newest_history_availability,
        },
        "atom_feed": {
            "source_url": atom_status.get("url"),
            "fetched_at_utc": atom_status.get("fetched_at_utc"),
            "bytes": atom_status.get("bytes"),
            "status": atom_status.get("status"),
            "newest_atom_updated": newest_atom_updated,
            "newest_atom_published": newest_atom_published,
            "newest_atom_build": _newest_atom_build(atom_entries),
        },
        "drift": {
            "atom_newer_than_release_history": [dict(item) for item in atom_newer],
            "current_version_latest_older_than_release_history": [dict(item) for item in current_stale],
            "newest_source_timestamp": newest_source_timestamp,
            "generated_after_newest_source_hours": generated_after_hours,
        },
        "parser": {
            "events": [dict(item) for item in parser_diagnostics],
        },
        "events": events,
        "event_counts": _source_event_counts(events),
        "notices": notices,
        "warnings": warnings,
    }


def _known_notes(policy: ReleasePolicy) -> tuple[dict[str, Any], ...]:
    notes: list[dict[str, Any]] = []
    for entry in policy.special_releases:
        flags = [
            flag
            for flag in (
                "special_release",
                "new_devices_only",
                "not_broad_target_existing_devices",
            )
            if entry.metadata.get(flag)
        ]
        notes.append(
            {
                "type": "special_release",
                "release": entry.version,
                "build_family": entry.build_family,
                "note": entry.reason,
                "flags": flags,
            }
        )
    return tuple(notes)


def _entry_with_b_release_baseline(
    entry: ReleasePolicyEntry,
    quality_baselines: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> ReleasePolicyEntry:
    baseline = quality_baselines.get(entry.version, {}).get(QualityPolicy.B_RELEASE_ONLY.value)
    if not isinstance(baseline, Mapping):
        return entry
    build = baseline.get("build")
    if not build:
        return entry
    baseline_build = str(build)
    return replace(
        entry,
        baseline_build=baseline_build,
        required_baseline_build=baseline_build,
    )


def _policy_with_enrichment(
    base_policy: ReleasePolicy,
    *,
    release_history: tuple[ReleaseHistoryEntry, ...],
    atom_entries: tuple[AtomFeedEntry, ...],
    generated_at_utc: str,
    release_health_url: str,
    atom_feed_url: str | None,
    release_health_html: str,
    atom_feed_xml: str | None,
    source_fetch_status: Mapping[str, Any],
    validation_warnings: tuple[str, ...],
    source_input_events: tuple[Mapping[str, Any], ...] = (),
    signature_status: str,
    published_urls: Mapping[str, str] | None = None,
) -> ReleasePolicy:
    quality_baselines = _quality_baselines(release_history)
    special_releases = tuple(
        _entry_with_b_release_baseline(_entry_with_special_flag(entry), quality_baselines)
        for entry in base_policy.special_releases
    )
    excluded = tuple(
        _entry_with_b_release_baseline(_entry_with_special_flag(entry), quality_baselines)
        for entry in base_policy.excluded_for_existing_devices
    )
    current_versions = tuple(
        _entry_with_b_release_baseline(_entry_with_special_flag(entry), quality_baselines)
        for entry in base_policy.current_versions
    )
    preview_builds = tuple(row.to_dict() for row in release_history if row.preview)
    out_of_band_builds = tuple(row.to_dict() for row in release_history if row.out_of_band)
    source_urls = [release_health_url]
    if atom_feed_url:
        source_urls.append(atom_feed_url)

    target = base_policy.broad_target_existing_devices
    if target is not None:
        baseline_found = False
        baseline = quality_baselines.get(target.version, {}).get(QualityPolicy.B_RELEASE_ONLY.value)
        if isinstance(baseline, Mapping):
            build = baseline.get("build")
            if build:
                baseline_found = True
                baseline_build = str(build)
                target = replace(
                    target,
                    baseline_build=baseline_build,
                    required_baseline_build=baseline_build,
                )
        if not baseline_found:
            raise PolicyParseError(
                "Could not select B-release required baseline for broad_target_existing_devices "
                f"{target.version}/{target.build_family} from Release Health release_history."
            )

    metadata = dict(base_policy.metadata)
    metadata["signature_status"] = signature_status
    metadata["generator"] = GENERATOR_VERSION
    metadata["freshness_policy"] = freshness_policy_metadata()
    parser_source = base_policy.source_diagnostics.get("parser")
    parser_diagnostics: tuple[Mapping[str, Any], ...] = ()
    if isinstance(parser_source, Mapping):
        parser_events = parser_source.get("events")
        if isinstance(parser_events, list):
            parser_diagnostics = tuple(item for item in parser_events if isinstance(item, Mapping))
    source_diagnostics = _source_diagnostics(
        current_versions=current_versions,
        release_history=release_history,
        atom_entries=atom_entries,
        broad_target=target,
        parser_diagnostics=parser_diagnostics,
        source_input_events=source_input_events,
        source_fetch_status=source_fetch_status,
        release_health_url=release_health_url,
        atom_feed_url=atom_feed_url,
        release_health_html=release_health_html,
        atom_feed_xml=atom_feed_xml,
        generated_at_utc=generated_at_utc,
    )
    combined_warnings = tuple(
        dict.fromkeys([*validation_warnings, *source_diagnostics.get("warnings", [])])
    )

    enriched = replace(
        base_policy,
        schema_version=SUPPORTED_POLICY_SCHEMA_VERSION,
        min_reader_schema_version=SUPPORTED_POLICY_SCHEMA_VERSION,
        max_reader_schema_version=SUPPORTED_POLICY_SCHEMA_VERSION,
        api_version="v1",
        compatibility={
            "additive_unknown_top_level_keys": "warning",
            "extension_namespaces": ["extensions", "x_*"],
            "required_core_schema_version": SUPPORTED_POLICY_SCHEMA_VERSION,
        },
        generated_at_utc=generated_at_utc,
        generator_version=GENERATOR_VERSION,
        source_urls=tuple(source_urls),
        published_urls=dict(published_urls or DEFAULT_PUBLISHED_POLICY_URLS),
        source_fetch_status=dict(source_fetch_status),
        source_diagnostics=source_diagnostics,
        current_versions=current_versions,
        release_history=release_history,
        special_releases=special_releases,
        supported_releases=current_versions,
        excluded_for_existing_devices=excluded,
        broad_target_existing_devices=target,
        quality_baselines=quality_baselines,
        preview_builds=preview_builds,
        out_of_band_builds=out_of_band_builds,
        known_notes=_known_notes(replace(base_policy, special_releases=special_releases)),
        validation_warnings=combined_warnings,
        metadata=metadata,
    )
    return enriched


def generate_policy(
    *,
    release_health_html: str,
    atom_feed_xml: str | None = None,
    release_health_url: str = DEFAULT_RELEASE_HEALTH_URL,
    atom_feed_url: str | None = DEFAULT_WINDOWS11_ATOM_FEED_URL,
    generated_at_utc: str | None = None,
    signature_status: str = "unsigned",
    source_fetch_status: Mapping[str, Any] | None = None,
    published_urls: Mapping[str, str] | None = None,
) -> ReleasePolicy:
    warnings: list[str] = []
    source_input_events: list[dict[str, Any]] = []
    generated = generated_at_utc or _utc_now()
    effective_source_fetch_status = {
        "release_health_html": _source_status(
            source_fetch_status or {},
            "release_health_html",
            source_url=release_health_url,
            text=release_health_html,
            generated_at_utc=generated,
        ),
        "atom_feed": _source_status(
            source_fetch_status or {},
            "atom_feed",
            source_url=atom_feed_url,
            text=atom_feed_xml,
            generated_at_utc=generated,
        ),
    }
    base_policy = parse_windows11_release_health_html(release_health_html)
    atom_entries: tuple[AtomFeedEntry, ...] = ()
    if atom_feed_xml:
        try:
            atom_entries = parse_atom_feed(atom_feed_xml)
        except PolicyParseError as exc:
            message = f"Atom feed could not be parsed: {exc}"
            warnings.append(message)
            source_input_events.append(_source_input_event("atom_feed_parse_failed", message))
    else:
        message = "Atom feed missing; preview/out-of-band enrichment unavailable."
        warnings.append(message)
        source_input_events.append(_source_input_event("atom_feed_missing", message))

    if atom_feed_xml and not atom_entries:
        message = "Atom feed contained no usable entries."
        warnings.append(message)
        source_input_events.append(_source_input_event("atom_feed_no_usable_entries", message))

    release_history = _enrich_history(base_policy.release_history, atom_entries)
    policy = _policy_with_enrichment(
        base_policy,
        release_history=release_history,
        atom_entries=atom_entries,
        generated_at_utc=generated,
        release_health_url=release_health_url,
        atom_feed_url=atom_feed_url,
        release_health_html=release_health_html,
        atom_feed_xml=atom_feed_xml,
        source_fetch_status=effective_source_fetch_status,
        validation_warnings=tuple(dict.fromkeys(warnings)),
        source_input_events=tuple(source_input_events),
        signature_status=signature_status,
        published_urls=published_urls,
    )
    validate_policy_document(policy.to_dict())
    return policy


def generate_policy_json(**kwargs: Any) -> str:
    policy = generate_policy(**kwargs)
    return policy_document_to_json(policy.to_dict())


def sign_policy_bytes(
    data: bytes,
    signing_key: str | bytes,
    *,
    key_id: str = DEFAULT_TRUSTED_POLICY_KEY_ID,
) -> dict[str, str]:
    signature = sign_ed25519_policy_bytes(data, signing_key, key_id=key_id)
    signature["signed_at_utc"] = _utc_now()
    return signature


def _write_public_artifact_bytes(path: Path, data: bytes) -> None:
    # Detached signatures and policy manifests are public Pages artifacts, not secrets.
    # codeql[py/clear-text-storage-sensitive-data]
    path.write_bytes(data)


def _write_public_artifact_text(path: Path, text: str) -> None:
    # Generated Pages text files contain public policy metadata only.
    # codeql[py/clear-text-storage-sensitive-data]
    path.write_text(text, encoding="utf-8", newline="\n")


def write_policy_outputs(
    policy: ReleasePolicy,
    *,
    output_dir: str | Path,
    signing_key: str | bytes | None = None,
    key_id: str = DEFAULT_TRUSTED_POLICY_KEY_ID,
    write_index: bool = False,
    write_robots: bool = False,
    write_sitemap: bool = False,
    write_manifest: bool = False,
) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    policy_file = output_path / "windows-release-policy.json"
    json_text = policy_document_to_json(policy.to_dict())
    policy_bytes = json_text.encode("utf-8")
    _write_public_artifact_bytes(policy_file, policy_bytes)
    written = {"policy": policy_file}

    signature: dict[str, str] | None = None
    signature_bytes: bytes | None = None
    if signing_key:
        signature = sign_policy_bytes(policy_bytes, signing_key, key_id=key_id)
        signature_file = output_path / "windows-release-policy.json.sig"
        signature_bytes = (json.dumps(signature, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write_public_artifact_bytes(signature_file, signature_bytes)
        written["signature"] = signature_file

    manifest_text: str | None = None
    if write_index:
        index_file = output_path / "index.html"
        _write_public_artifact_text(
            index_file,
            render_policy_index(
                policy,
                policy_bytes=policy_bytes,
                signature=signature,
            ),
        )
        written["index"] = index_file

    if write_robots:
        robots_file = output_path / "robots.txt"
        _write_public_artifact_text(robots_file, render_robots_txt())
        written["robots"] = robots_file

    if write_sitemap:
        sitemap_file = output_path / "sitemap.xml"
        _write_public_artifact_text(sitemap_file, render_sitemap_xml(policy))
        written["sitemap"] = sitemap_file

    if write_manifest:
        manifest_file = output_path / "policy-manifest.json"
        manifest_text = render_policy_manifest(
            policy,
            policy_bytes=policy_bytes,
            signature_bytes=signature_bytes,
            signature=signature,
        )
        _write_public_artifact_text(manifest_file, manifest_text)
        written["manifest"] = manifest_file

    if any((write_index, write_robots, write_sitemap, write_manifest)):
        nojekyll_file = output_path / ".nojekyll"
        _write_public_artifact_text(nojekyll_file, "")
        written["nojekyll"] = nojekyll_file

    if write_manifest:
        api_dir = output_path / "api" / "v1"
        api_dir.mkdir(parents=True, exist_ok=True)
        policy_alias = api_dir / "policy.json"
        shutil.copyfile(policy_file, policy_alias)
        written["api_policy"] = policy_alias
        if signature_bytes is not None:
            signature_alias = api_dir / "policy.sig"
            _write_public_artifact_bytes(signature_alias, signature_bytes)
            written["api_signature"] = signature_alias
        if manifest_text is not None:
            manifest_alias = api_dir / "manifest.json"
            _write_public_artifact_text(manifest_alias, manifest_text)
            written["api_manifest"] = manifest_alias

    return written


def _sha256_hex(data: bytes | None) -> str | None:
    if data is None:
        return None
    return hashlib.sha256(data).hexdigest()


def _short_hash(value: str | None) -> str:
    return value[:12] if value else "unavailable"


def _signature_field(signature: Mapping[str, Any] | None, key: str) -> str | None:
    if not signature:
        return None
    value = signature.get(key)
    return str(value) if value not in (None, "") else None


def _signature_trust_class(*, signature_attached: bool, signature_status: str) -> str:
    normalized = signature_status.strip().lower()
    if normalized == "valid":
        return ""
    if not signature_attached and normalized in {"unsigned", "unsigned local preview"}:
        return " warning"
    return " error"


def _reason_summary(value: str | None, *, max_length: int = 150) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if not text:
        return "Excluded by signed release policy."
    if len(text) <= max_length:
        return text
    boundary = text.rfind(" ", 0, max_length - 1)
    if boundary < max_length // 2:
        boundary = max_length - 1
    return text[:boundary].rstrip(" ,;:-.") + "."


def _excluded_release_summary(entry: ReleasePolicyEntry) -> str:
    curated = CURATED_EXCLUDED_RELEASE_SUMMARIES.get(entry.version.upper())
    if curated:
        return curated
    return _reason_summary(entry.reason)


def _source_label(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    path_segments = [segment for segment in parsed.path.lower().split("/") if segment]
    has_release_health_path = any(
        left == "windows" and right == "release-health"
        for left, right in zip(path_segments, path_segments[1:])
    )
    has_atom_feed_path = any(
        left == "feed" and right == "atom"
        for left, right in zip(path_segments, path_segments[1:])
    )
    if host == "learn.microsoft.com" and has_release_health_path:
        return "Microsoft Release Health"
    if host == "support.microsoft.com" and has_atom_feed_path:
        return "Microsoft Atom feed"
    return url


def _status_text(policy: ReleasePolicy) -> str:
    return "Warning state" if policy.validation_warnings else "Policy current"


def _source_event_counts_for_policy(policy: ReleasePolicy) -> dict[str, int]:
    source_diagnostics = policy.source_diagnostics if isinstance(policy.source_diagnostics, Mapping) else {}
    raw_counts = source_diagnostics.get("event_counts") if isinstance(source_diagnostics, Mapping) else {}
    counts = {"notice": 0, "warning": 0, "error": 0}
    if isinstance(raw_counts, Mapping):
        for key in counts:
            try:
                counts[key] = max(0, int(raw_counts.get(key) or 0))
            except (TypeError, ValueError):
                counts[key] = 0
    return counts


def _source_diagnostics_for_policy(policy: ReleasePolicy) -> Mapping[str, Any]:
    source_diagnostics = policy.source_diagnostics if isinstance(policy.source_diagnostics, Mapping) else {}
    return source_diagnostics


def _short_diagnostic_text(value: Any, *, max_length: int = 150) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    boundary = text.rfind(" ", 0, max_length - 1)
    if boundary < max_length // 2:
        boundary = max_length - 1
    return text[:boundary].rstrip(" ,;:-.") + "."


def _source_diagnostic_event_severity(value: Any) -> str:
    severity = str(value or "").strip().lower()
    return severity if severity in {"notice", "warning", "error"} else "warning"


def _source_diagnostic_event_label(kind: Any) -> str:
    text = re.sub(r"[_-]+", " ", str(kind or "source diagnostic")).strip()
    if not text:
        return "Source diagnostic"
    acronyms = {"kb", "oob", "esu", "lcu"}
    return " ".join(part.upper() if part.lower() in acronyms else part.capitalize() for part in text.split())


def _source_diagnostic_source_label(kind: Any) -> str:
    text = str(kind or "").strip().lower()
    if "atom" in text:
        return "Atom feed"
    if "manifest" in text:
        return "Manifest"
    if (
        "freshness" in text
        or "stale" in text
        or "aging" in text
        or "currency" in text
        or "refresh" in text
        or "policy_feed" in text
    ):
        return "Policy feed currency"
    if "parser" in text or "parse" in text:
        return "Parser"
    if "release_health" in text or "current_versions" in text or "release_history" in text:
        return "Release Health"
    if "signature" in text:
        return "Signature"
    return "Source"


def _source_diagnostic_timestamp(event: Mapping[str, Any]) -> str | None:
    for key in ("occurred_at_utc", "fetched_at_utc", "published", "updated", "timestamp", "generated_at_utc"):
        value = event.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _source_diagnostic_row_from_event(event: Mapping[str, Any]) -> dict[str, Any]:
    kind = event.get("kind")
    severity = _source_diagnostic_event_severity(event.get("severity"))
    title = _source_diagnostic_event_label(kind)
    message = _short_diagnostic_text(event.get("message") or event.get("title") or title)
    tags: list[str] = []
    for key, label in (
        ("release", "Release"),
        ("build", "Build"),
    ):
        value = event.get(key)
        if value not in (None, ""):
            tags.append(f"{label} {value}")
    kb_article = event.get("kb_article")
    if kb_article not in (None, ""):
        kb_text = str(kb_article)
        tags.append(kb_text if kb_text.upper().startswith("KB") else f"KB {kb_text}")
    build_family = event.get("build_family")
    if build_family not in (None, ""):
        tags.append(f"Family {build_family}")
    if event.get("affects_required_baseline"):
        tags.append("Required baseline")
    elif event.get("affects_broad_target"):
        tags.append("Broad target")
    timestamp = _source_diagnostic_timestamp(event)
    if timestamp:
        tags.append(timestamp)
    return {
        "severity": severity,
        "title": title,
        "source": _source_diagnostic_source_label(kind),
        "message": message,
        "tags": tuple(tags),
    }


def _source_diagnostic_row_from_text(severity: str, message: Any, *, source: str, title: str) -> dict[str, Any]:
    return {
        "severity": _source_diagnostic_event_severity(severity),
        "title": title,
        "source": source,
        "message": _short_diagnostic_text(message),
        "tags": (),
    }


def _raw_diagnostic_messages(source_diagnostics: Mapping[str, Any], key: str) -> tuple[str, ...]:
    values = source_diagnostics.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(str(item) for item in values if str(item or "").strip())


def _freshness_diagnostic_row(generated_age_days: float) -> dict[str, Any] | None:
    if generated_age_days >= DEFAULT_POLICY_STRICT_STALE_AGE_DAYS:
        return _source_diagnostic_row_from_text(
            "error",
            (
                "Published policy feed is stale at render time. Do not treat this data as "
                "production-current until automation refresh succeeds."
            ),
            source="Policy feed currency",
            title="Policy feed stale",
        )
    if generated_age_days >= DEFAULT_POLICY_WARNING_AGE_DAYS:
        return _source_diagnostic_row_from_text(
            "warning",
            (
                "Published policy feed refresh is due at render time. Verify automation health "
                "before treating this data as production-current."
            ),
            source="Policy feed currency",
            title="Policy feed refresh due",
        )
    return None


def _source_diagnostic_rows(policy: ReleasePolicy, *, generated_age_days: float) -> tuple[dict[str, Any], ...]:
    source_diagnostics = _source_diagnostics_for_policy(policy)
    raw_events = source_diagnostics.get("events")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_events, list):
        rows.extend(
            _source_diagnostic_row_from_event(event)
            for event in raw_events
            if isinstance(event, Mapping)
        )

    if not rows:
        for message in _raw_diagnostic_messages(source_diagnostics, "errors"):
            rows.append(_source_diagnostic_row_from_text("error", message, source="Source", title="Source error"))
        for message in _raw_diagnostic_messages(source_diagnostics, "warnings"):
            rows.append(_source_diagnostic_row_from_text("warning", message, source="Source", title="Source warning"))
        for message in _raw_diagnostic_messages(source_diagnostics, "notices"):
            rows.append(_source_diagnostic_row_from_text("notice", message, source="Source", title="Source notice"))
        for message in policy.validation_warnings:
            rows.append(
                _source_diagnostic_row_from_text(
                    "warning",
                    message,
                    source="Policy",
                    title="Policy warning",
                )
            )

    has_freshness_row = any(
        str(row.get("source") or "") in {"Freshness", "Policy feed currency"} for row in rows
    )
    freshness_row = _freshness_diagnostic_row(generated_age_days)
    if freshness_row is not None and not has_freshness_row:
        rows.append(freshness_row)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (str(row.get("severity") or ""), str(row.get("title") or ""), str(row.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return tuple(deduped)


def _excluded_release_diagnostic_rows(policy: ReleasePolicy) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in policy.excluded_for_existing_devices:
        version = str(entry.version or "").strip().upper()
        if not version or version in seen:
            continue
        seen.add(version)
        rows.append(
            {
                "severity": "notice",
                "title": f"{version} excluded for existing devices",
                "source": "Release policy",
                "message": _excluded_release_summary(entry),
                "tags": (
                    f"Release {version}",
                    "Existing devices",
                    "Not broad target",
                ),
            }
        )
    return tuple(rows)


def _display_source_event_counts(counts: Mapping[str, int], rows: tuple[dict[str, Any], ...]) -> dict[str, int]:
    display_counts = {key: max(0, int(counts.get(key, 0))) for key in ("notice", "warning", "error")}
    row_counts = {"notice": 0, "warning": 0, "error": 0}
    for row in rows:
        severity = _source_diagnostic_event_severity(row.get("severity"))
        row_counts[severity] += 1
    for severity, count in row_counts.items():
        display_counts[severity] = max(display_counts[severity], count)
    return display_counts


def _placeholder_rows_for_unexplained_counts(
    counts: Mapping[str, int],
    rows: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    rows_by_severity = {"notice": 0, "warning": 0, "error": 0}
    for row in rows:
        rows_by_severity[_source_diagnostic_event_severity(row.get("severity"))] += 1
    placeholders: list[dict[str, Any]] = []
    for severity, title in (
        ("error", "Error diagnostics reported"),
        ("warning", "Warning diagnostics reported"),
        ("notice", "Notice diagnostics reported"),
    ):
        missing = max(0, int(counts.get(severity, 0)) - rows_by_severity[severity])
        if missing:
            label = "entry" if missing == 1 else "entries"
            placeholders.append(
                _source_diagnostic_row_from_text(
                    severity,
                    f"{missing} {severity} diagnostic {label} reported without structured row details.",
                    source="Source",
                    title=title,
                )
            )
    return tuple(placeholders)


def _render_source_diagnostic_row(row: Mapping[str, Any]) -> str:
    severity = _source_diagnostic_event_severity(row.get("severity"))
    title = str(row.get("title") or "Source diagnostic")
    source = str(row.get("source") or "Source")
    message = str(row.get("message") or "")
    tags = row.get("tags")
    tag_items = ""
    if isinstance(tags, tuple):
        tag_items = "".join(f"<span>{escape(str(tag))}</span>" for tag in tags if str(tag or "").strip())
    return (
        f"<article class=\"diag-row {severity}\">"
        "<span class=\"diag-stripe\" aria-hidden=\"true\"></span>"
        "<div>"
        "<div class=\"diag-row-head\">"
        f"<span class=\"severity-badge {severity}\">{escape(severity.capitalize())}</span>"
        f"<strong>{escape(title)}</strong>"
        f"<span class=\"source-chip\">{escape(source)}</span>"
        "</div>"
        f"<p>{escape(message)}</p>"
        f"<div class=\"diag-tags\">{tag_items}</div>"
        "</div>"
        "</article>"
    )


def _render_source_diagnostics_panel(
    policy: ReleasePolicy,
    counts: Mapping[str, int],
    *,
    generated_age_days: float,
    generated_at_utc: str,
) -> str:
    base_rows = _source_diagnostic_rows(policy, generated_age_days=generated_age_days)
    excluded_rows = _excluded_release_diagnostic_rows(policy)
    counted_rows = (*base_rows, *excluded_rows)
    rows = (*counted_rows, *_placeholder_rows_for_unexplained_counts(counts, counted_rows))
    display_counts = _display_source_event_counts(counts, rows)
    count_tiles = (
        "<div class=\"diag-summary\" aria-label=\"Source diagnostic counts\">"
        f"<div class=\"diag-tile notice\"><strong>{display_counts['notice']}</strong><span>Notices</span></div>"
        f"<div class=\"diag-tile warning\"><strong>{display_counts['warning']}</strong><span>Warnings</span></div>"
        f"<div class=\"diag-tile error\"><strong>{display_counts['error']}</strong><span>Errors</span></div>"
        "</div>"
    )
    if not rows:
        clear_row = _render_source_diagnostic_row(
            {
                "severity": "notice",
                "title": "No source issues reported",
                "source": "Source diagnostics",
                "message": "Release Health, Atom feed, parser, and freshness checks have no warning or error events.",
                "tags": ("No warnings", "No errors"),
            }
        )
        details = f"<div class=\"diag-events diag-events-empty\">{clear_row}</div>"
    else:
        has_warning_or_error = any(
            _source_diagnostic_event_severity(row.get("severity")) in {"warning", "error"}
            for row in rows
        )
        lead_row = ""
        if not has_warning_or_error:
            clear_row = {
                "severity": "notice",
                "title": "No source issues reported",
                "source": "Source diagnostics",
                "message": "Release Health, Atom feed, parser, and freshness checks have no warning or error events.",
                "tags": ("No warnings", "No errors"),
            }
            lead_row = _render_source_diagnostic_row(clear_row)
        visible_rows = rows[:5]
        hidden_rows = rows[5:]
        rendered_visible = lead_row + "".join(_render_source_diagnostic_row(row) for row in visible_rows)
        overflow = ""
        if hidden_rows:
            rendered_hidden = "".join(_render_source_diagnostic_row(row) for row in hidden_rows)
            overflow = (
                f"<details class=\"diag-more\"><summary>+{len(hidden_rows)} more</summary>"
                f"<div class=\"diag-events\">{rendered_hidden}</div></details>"
            )
        details = f"<div class=\"diag-events\">{rendered_visible}</div>{overflow}"
    return (
        "<section class=\"panel span-7 source-diagnostics\"><h2>Source diagnostics</h2>"
        f"{count_tiles}<div class=\"diag-feed\" role=\"region\" aria-label=\"Source diagnostic event feed\">"
        f"{details}</div>{_render_source_tiles(policy, generated_at_utc=generated_at_utc)}</section>\n"
    )


def _program_version_from_generator(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    return text.rsplit("/", 1)[-1] if "/" in text else text


def _program_release_url(version: str | None) -> str | None:
    text = str(version or "").strip()
    if not _RELEASE_VERSION_PATTERN.fullmatch(text):
        return None
    return f"{GITHUB_RELEASES_BASE_URL}/v{text}"


def _program_title_version_html(version: str | None) -> str:
    text = str(version or "").strip() or "unknown"
    url = _program_release_url(text)
    escaped_text = escape(text)
    label = f"Program Version {escaped_text}"
    if url is None:
        return (
            '<span class="title-version-link">'
            f'<span class="title-version-label">Program Version</span> {escaped_text}'
            "</span>"
        )
    escaped_url = escape(url, quote=True)
    return (
        f'<a class="title-version-link mono" href="{escaped_url}" '
        f'aria-label="{escape(label, quote=True)} release">'
        '<span class="title-version-label">Program Version</span> '
        f"{escaped_text}</a>"
    )


def _header_nav_html() -> str:
    dashboard_icon = (
        '<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">'
        '<path d="M20,4H6A2,2,0,0,0,4,6V20a2,2,0,0,0,2,2H20a2,2,0,0,0,2-2V6A2,2,0,0,0,20,4Z"/>'
        '<path d="M42,4H28a2,2,0,0,0-2,2V20a2,2,0,0,0,2,2H42a2,2,0,0,0,2-2V6A2,2,0,0,0,42,4Z"/>'
        '<path d="M20,26H6a2,2,0,0,0-2,2V42a2,2,0,0,0,2,2H20a2,2,0,0,0,2-2V28A2,2,0,0,0,20,26Z"/>'
        '<path d="M42,26H28a2,2,0,0,0-2,2V42a2,2,0,0,0,2,2H42a2,2,0,0,0,2-2V28A2,2,0,0,0,42,26Z"/>'
        "</svg>"
    )
    issue_icon = (
        '<svg viewBox="0 0 512 512" aria-hidden="true" focusable="false">'
        '<path d="M421.073 221.719c-.578 11.719-9.469 26.188-23.797 40.094v183.25c-.016 4.719-1.875 8.719-5.016 11.844-3.156 3.063-7.25 4.875-12.063 4.906H81.558c-4.781-.031-8.891-1.844-12.047-4.906-3.141-3.125-4.984-7.125-5-11.844V152.219c.016-4.703 1.859-8.719 5-11.844 3.156-3.063 7.266-4.875 12.047-4.906h158.609c12.828-16.844 27.781-34.094 44.719-49.906.078-.094.141-.188.219-.281H81.558c-18.75-.016-35.984 7.531-48.25 19.594-12.328 12.063-20.016 28.938-20 47.344v292.844c-.016 18.406 7.672 35.313 20 47.344C45.573 504.469 62.808 512 81.558 512h298.641c18.781 0 36.016-7.531 48.281-19.594 12.297-12.031 20-28.938 19.984-47.344V203.469c0 0-.125-.156-.328-.313-7.766 6.657-16.813 13-27.063 18.563z"/>'
        '<path d="M498.058 0s-15.688 23.438-118.156 58.109C275.417 93.469 211.104 237.313 211.104 237.313c-15.484 29.469-76.688 151.906-76.688 151.906-16.859 31.625 14.031 50.313 32.156 17.656 34.734-62.688 57.156-119.969 109.969-121.594 77.047-2.375 129.734-69.656 113.156-66.531-21.813 9.5-69.906.719-41.578-3.656 68-5.453 109.906-56.563 96.25-60.031-24.109 9.281-46.594.469-51-2.188C513.386 138.281 498.058 0 498.058 0z"/>'
        "</svg>"
    )
    wiki_icon = (
        '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
        '<path d="M5 0C3.343 0 2 1.343 2 3v10c0 1.657 1.343 3 3 3h9v-2H4v-2h10V0H5z"/>'
        "</svg>"
    )
    items = (
        ("Dashboard", DEFAULT_PUBLISHED_POLICY_URLS["landing"], dashboard_icon),
        ("Write a Issue Ticket", "https://github.com/Avnsx/win11_release_guard/issues/new", issue_icon),
        ("Wiki", "https://github.com/Avnsx/win11_release_guard/wiki", wiki_icon),
    )
    links = "".join(
        (
            f'<li><a href="{escape(href, quote=True)}" aria-label="{escape(label, quote=True)}" '
            f'data-nav-label="{escape(label, quote=True)}">'
            f"{icon}<span class=\"sr-only\">{escape(label)}</span></a></li>"
        )
        for label, href, icon in items
    )
    return (
        '<nav class="header-nav" aria-label="Header navigation">'
        '<span class="nav-hover-label" aria-hidden="true">Dashboard</span>'
        f'<ul class="nav-inner">{links}</ul>'
        "</nav>"
    )


def _format_bytes(value: Any) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return "unavailable"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def _hash_html(value: str | None) -> str:
    short = _short_hash(value)
    title = f' title="{escape(value, quote=True)}"' if value else ""
    return f'<span class="mono hash"{title}>{escape(short)}</span>'


def _source_status_for_url(policy: ReleasePolicy, url: str, *, generated_at_utc: str) -> Mapping[str, Any]:
    label = _source_label(url)
    if label == "Microsoft Release Health":
        source = _source_diagnostics_for_policy(policy).get("release_health_html")
    elif label == "Microsoft Atom feed":
        source = _source_diagnostics_for_policy(policy).get("atom_feed")
    else:
        source = None
    if not isinstance(source, Mapping):
        return {
            "status": "recorded",
            "fetched_at_utc": generated_at_utc,
            "bytes": None,
        }
    return source


def _source_status_class(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"ok", "success", "valid", "healthy", "current"}:
        return "ok"
    if any(token in text for token in ("warn", "degraded", "aging", "partial", "stale")):
        return "warning"
    if any(token in text for token in ("error", "err", "fail", "invalid", "blocked", "unavailable")):
        return "error"
    return "unknown"


def _render_source_tiles(policy: ReleasePolicy, *, generated_at_utc: str) -> str:
    if not policy.source_urls:
        return (
            "<div class=\"source-health\" aria-label=\"Policy source status\">"
            "<h3>Source health</h3><div class=\"source-health-grid\">"
            "<div class=\"source-tile unknown\"><div class=\"source-tile-head\">"
            "<strong>None recorded</strong><span class=\"source-status unknown\">unknown</span></div>"
            "<span>No source URLs are present in this policy.</span></div>"
            "</div></div>"
        )
    items: list[str] = []
    for url in policy.source_urls:
        label = _source_label(url)
        status = _source_status_for_url(policy, url, generated_at_utc=generated_at_utc)
        fetched_at = str(status.get("fetched_at_utc") or "")
        fetched_at_html = _time_with_epoch_copy_html(fetched_at, label=f"{label} UTC")
        status_text = str(status.get("status") or "unknown")
        status_class = _source_status_class(status_text)
        bytes_text = _format_bytes(status.get("bytes"))
        escaped_url = escape(url, quote=True)
        items.append(
            f"<div class=\"source-tile {status_class}\">"
            "<div class=\"source-tile-head\">"
            f"<strong>{escape(label)}</strong>"
            f"<span class=\"source-status {status_class}\">{escape(status_text)}</span>"
            "</div>"
            f"<a href=\"{escaped_url}\" title=\"{escaped_url}\">{escape(url)}</a>"
            "<dl class=\"mini-kv\">"
            f"<dt>Fetched:</dt><dd>{fetched_at_html}</dd>"
            f"<dt>Bytes:</dt><dd>{escape(bytes_text)}</dd>"
            "</dl>"
            "</div>"
        )
    return (
        "<div class=\"source-health\" aria-label=\"Policy source status\">"
        "<h3>Source health</h3>"
        f"<div class=\"source-health-grid\">{''.join(items)}</div></div>"
    )


def _render_endpoint_links() -> str:
    endpoints = (
        (
            "Signed policy JSON",
            "windows-release-policy.json",
            "Primary signed policy document used by automation and fleet dashboards.",
        ),
        (
            "Detached signature",
            "windows-release-policy.json.sig",
            "Ed25519 signature that lets clients verify the policy before trusting it.",
        ),
        (
            "Policy manifest",
            "policy-manifest.json",
            "Compact metadata for hashes, freshness thresholds, source state, and API aliases.",
        ),
        (
            "API v1 policy alias",
            "api/v1/policy.json",
            "Backward-compatible policy endpoint for stable reader integrations.",
        ),
        (
            "API v1 manifest alias",
            "api/v1/manifest.json",
            "Backward-compatible manifest endpoint for stable reader integrations.",
        ),
    )
    return "".join(
        (
            f'<a class="api-endpoint-row" href="{escape(endpoint, quote=True)}">'
            f"<span><strong>{escape(title)}</strong><em>{escape(description)}</em></span>"
            f"<code>/{escape(endpoint)}</code></a>"
        )
        for title, endpoint, description in endpoints
    )


def _safe_json_script_payload(data: Mapping[str, Any]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def render_policy_index(
    policy: ReleasePolicy,
    *,
    policy_bytes: bytes | None = None,
    signature: Mapping[str, Any] | None = None,
) -> str:
    target = policy.broad_target_existing_devices
    policy_hash = _sha256_hex(policy_bytes)
    generated_at_utc = policy.generated_at_utc or _utc_now()
    generated_human = _generated_at_human(generated_at_utc)
    generated_age_days = _generated_age_days(generated_at_utc)
    signature_attached = signature is not None
    raw_signature_status = str(policy.metadata.get("signature_status") or "unavailable")
    if signature_attached:
        signature_algorithm = _signature_field(signature, "algorithm") or "unavailable"
        key_id = _signature_field(signature, "key_id") or "legacy default key"
        signature_status = raw_signature_status
        trust_indicator = "Signed policy trust"
    else:
        signature_algorithm = "not attached"
        key_id = "not attached"
        signature_status = "unsigned local preview" if raw_signature_status == "unsigned" else raw_signature_status
        trust_indicator = "Unsigned local preview" if signature_status == "unsigned local preview" else "Signature metadata"
    trust_class = _signature_trust_class(
        signature_attached=signature_attached,
        signature_status=signature_status,
    )
    source_event_counts = _source_event_counts_for_policy(policy)
    source_diagnostics_panel = _render_source_diagnostics_panel(
        policy,
        source_event_counts,
        generated_age_days=generated_age_days,
        generated_at_utc=generated_at_utc,
    )
    program_version = _program_version_from_generator(GENERATOR_VERSION)
    workflow_run = os.environ.get("GITHUB_RUN_ID") or "not available in local render"
    endpoint_links = _render_endpoint_links()
    freshness_data = {
        "generated_at_utc": generated_at_utc,
        **freshness_thresholds(generated_at_utc),
        "freshness_policy": freshness_policy_metadata(),
    }
    warning_items = "\n".join(f"<li>{escape(warning)}</li>" for warning in policy.validation_warnings)
    warning_block = (
        f"      <section class=\"panel span-12\"><h2>Warnings</h2><ul class=\"warnings\">{warning_items}</ul></section>"
        if warning_items
        else ""
    )
    target_release = target.version if target else "unknown"
    target_family = str(target.build_family) if target else "unknown"
    target_latest_observed = target.latest_observed_build if target else None
    target_baseline = target.required_baseline_build if target else None
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "  <title>Windows 11 Release Guard</title>\n"
        "  <style>\n"
        "    :root{color-scheme:light;--bg:#f4f8fd;--ink:#172033;--muted:#667085;--soft:#f8fbff;--line:#d8e3f0;--panel:#ffffff;--blue:#0078d4;--blue-strong:#0067c0;--blue-soft:#e8f3ff;--ok:#107c10;--ok-soft:#eaf7ed;--warn:#b45309;--warn-soft:#fff4df;--err:#b42318;--err-soft:#fff0ed;--unknown:#64748b;--unknown-soft:#f1f5f9;--code:#063f63;--shadow:0 18px 55px rgba(31,79,143,.12)}\n"
        "    *{box-sizing:border-box}html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}html,body{max-width:100%;overflow-x:hidden}body{margin:0;min-height:100vh;background:linear-gradient(145deg,#ffffff 0%,#f5f9ff 42%,#edf4fb 100%);color:var(--ink);font-family:Segoe UI,Arial,sans-serif;line-height:1.45}\n"
        "    main{max-width:1180px;margin:0 auto;padding:28px 24px 24px}.masthead{margin-bottom:16px;padding:20px 22px;border:1px solid rgba(216,227,240,.95);border-radius:8px;background:linear-gradient(180deg,rgba(255,255,255,.94),rgba(248,252,255,.86));box-shadow:var(--shadow);backdrop-filter:blur(18px)}\n"
        "    .brand{display:flex;gap:16px;align-items:center;min-width:0}.brand>div:last-child{min-width:0;flex:1}.brand-layout{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:stretch}.brand-copy{min-width:0}.header-actions{display:flex;flex-direction:column;align-items:flex-end;justify-content:space-between;gap:10px;min-width:0}.winmark{width:58px;height:58px;display:grid;grid-template-columns:1fr 1fr;gap:3px;flex:0 0 auto}.winmark span{background:linear-gradient(145deg,#0091ff,#0067c0);border-radius:2px;box-shadow:inset 0 1px 0 rgba(255,255,255,.35)}\n"
        "    .title-line h1{font-size:34px;line-height:1.08;margin:0 0 6px;font-weight:760;overflow-wrap:anywhere}.subtitle-line{display:flex;align-items:baseline;gap:16px;min-width:0}.title-version-link{display:inline-flex;align-items:center;gap:5px;margin-left:auto;font-size:13px;font-weight:760;color:#0067c0;white-space:nowrap;flex:0 0 auto}.title-version-link:after{content:'\\2197';font-family:Segoe UI,Arial,sans-serif;font-size:11px}.title-version-label{color:var(--muted);font-family:Segoe UI,Arial,sans-serif;font-weight:700}p{margin:0}.subtitle{font-size:15px;color:var(--muted);overflow-wrap:anywhere;min-width:0}.eyebrow{display:block;margin-bottom:5px;color:#2563a7;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}\n"
        "    .header-nav{--item-size:38px;--nav-gap:4px;--enter-nav:0;--label-x:19px;--label-y:0px;position:relative;isolation:isolate}.header-nav ul{list-style:none;margin:0;padding:0}.header-nav .nav-inner{display:flex;gap:var(--nav-gap);white-space:nowrap;border:1px solid rgba(194,213,235,.95);border-radius:999px;background:rgba(255,255,255,.88);box-shadow:0 9px 18px rgba(31,79,143,.09);padding:3px;backdrop-filter:blur(12px)}.header-nav .nav-inner li{display:flex}.header-nav .nav-inner a{width:var(--item-size);height:34px;display:grid;place-items:center;border-radius:999px;color:#667085;text-decoration:none;transition:color .16s ease,background-color .16s ease,transform .16s ease}.header-nav .nav-inner a:hover,.header-nav .nav-inner a:focus-visible{color:var(--blue-strong);background:linear-gradient(180deg,#f6fbff,#e8f3ff);text-decoration:none;transform:translateY(-1px)}.header-nav .nav-inner a:focus-visible{outline:3px solid rgba(0,120,212,.24);outline-offset:3px}.header-nav svg{width:20px;height:20px;display:block;fill:currentColor}.nav-hover-label{position:absolute;left:0;bottom:calc(100% + 6px);max-width:180px;opacity:var(--enter-nav);pointer-events:none;white-space:nowrap;border:1px solid rgba(184,207,234,.95);border-radius:999px;background:rgba(239,246,255,.96);box-shadow:0 9px 18px rgba(31,79,143,.12);color:#075985;font-size:11px;font-weight:780;line-height:1;padding:7px 10px;transform:translate(calc(var(--label-x) - 50%),calc((1 - var(--enter-nav)) * 4px + var(--label-y)));transition:opacity .15s ease,transform .2s ease}.header-nav:not(:hover):not(:focus-within){--enter-nav:0}\n"
        "    .grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px}.kpi-grid{margin-bottom:16px}.dashboard-grid{align-items:stretch}.panel{background:linear-gradient(180deg,rgba(255,255,255,.94),rgba(248,252,255,.9));border:1px solid var(--line);border-radius:8px;padding:14px;min-width:0;box-shadow:0 10px 30px rgba(31,79,143,.08)}.panel *{min-width:0}.panel p,.panel span,.panel dd,.panel strong{overflow-wrap:anywhere}.panel.status-card{display:grid;gap:13px}.span-3{grid-column:span 3}.span-4{grid-column:span 4}.span-5{grid-column:span 5}.span-6{grid-column:span 6}.span-7{grid-column:span 7}.span-8{grid-column:span 8}.span-12{grid-column:span 12}\n"
        "    h2{font-size:12px;text-transform:uppercase;letter-spacing:0;color:var(--muted);margin:0 0 12px}.metric{font-size:31px;font-weight:780;line-height:1;color:#102a43}.metric.blue{color:var(--blue)}.label{display:block;color:var(--muted);font-size:13px;margin-top:6px}.mono{font-family:Consolas,Menlo,monospace;color:var(--code);overflow-wrap:anywhere;word-break:break-word}\n"
        "    .kv{display:grid;grid-template-columns:minmax(126px,160px) 1fr;gap:9px 14px;font-size:14px}.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:650;overflow-wrap:anywhere}.kv dd span{display:block;margin-top:2px;color:var(--muted);font-size:12px;font-weight:500}.compact-kv{grid-template-columns:1fr;gap:4px}.compact-kv dt{font-size:12px}.compact-kv dd{margin:0 0 8px}.metadata{border-top:1px solid var(--line);padding-top:12px}.refresh{border-left:3px solid var(--blue);background:linear-gradient(90deg,var(--blue-soft),rgba(255,255,255,0));padding-left:12px}.time-copy{display:inline-flex!important;align-items:center;gap:6px;max-width:100%;min-width:0;color:inherit;font-size:inherit}.time-copy time{overflow-wrap:anywhere}.time-copy.unavailable{color:var(--muted);font-size:13px}.epoch-copy{display:inline-grid;place-items:center;width:24px;height:24px;min-width:24px;border:1px solid var(--line);border-radius:6px;background:rgba(255,255,255,.86);color:#64748b;cursor:pointer;padding:0;box-shadow:0 1px 1px rgba(15,23,42,.04)}.epoch-copy:hover{border-color:#9cccf6;color:var(--blue-strong);background:#fff}.epoch-copy:focus-visible{outline:3px solid rgba(0,120,212,.28);outline-offset:2px}.epoch-copy[data-copy-state=\"copied\"]{border-color:#b9e6c4;color:var(--ok);background:var(--ok-soft)}.epoch-copy[data-copy-state=\"failed\"]{border-color:#f6b7ad;color:var(--err);background:var(--err-soft)}.epoch-copy svg{width:14px;height:14px;display:block;pointer-events:none}\n"
        "    .freshness-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.freshness-state{display:inline-flex;align-items:center;border-radius:999px;border:1px solid var(--line);padding:6px 10px;font-size:13px;font-weight:750;color:var(--unknown);background:var(--unknown-soft)}.freshness-state.current{color:var(--ok);background:var(--ok-soft);border-color:#b9e6c4}.freshness-state.refresh-due{color:var(--warn);background:var(--warn-soft);border-color:#f6d493}.freshness-state.stale{color:var(--err);background:var(--err-soft);border-color:#f6b7ad}.freshness-state.unknown{color:var(--unknown);background:var(--unknown-soft);border-color:var(--line)}.freshness-metric{font-size:26px;font-weight:780;color:#102a43}.freshness-detail{color:var(--muted);font-size:13px}.thresholds{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.thresholds div{border:1px solid var(--line);border-radius:8px;background:var(--soft);padding:10px}.thresholds strong{display:block;font-size:17px}.thresholds span{display:block;color:var(--muted);font-size:12px}\n"
        "    ul.clean{list-style:none;margin:0;padding:0;display:grid;gap:10px}ul.clean li{display:grid;gap:3px}ul.clean span{color:var(--muted);font-size:13px}a{color:#075985;text-decoration:none;overflow-wrap:anywhere;word-break:break-word}a:hover{text-decoration:underline}a:focus-visible,summary:focus-visible{outline:3px solid rgba(0,120,212,.28);outline-offset:3px;border-radius:6px}.version-link{display:inline-flex;align-items:center;gap:6px;color:#0067c0;font-weight:760}.version-link:after{content:'\\2197';font-family:Segoe UI,Arial,sans-serif;font-size:12px}.hash{display:inline-block;max-width:100%}\n"
        "    .trust-indicator{--trust-ring:rgba(16,124,16,.18);display:inline-flex;align-items:center;gap:8px;width:max-content;border:1px solid #a9ddb7;border-radius:999px;background:linear-gradient(180deg,var(--ok-soft),#f7fff8);color:var(--ok);padding:5px 10px;font-size:12px;font-weight:650;white-space:nowrap;box-shadow:inset 0 1px 0 rgba(255,255,255,.82)}.trust-indicator:before{content:'';width:9px;height:9px;border-radius:999px;background:currentColor;box-shadow:0 0 0 5px var(--trust-ring);transform-origin:center;animation:trustPulse 2.2s cubic-bezier(.4,0,.2,1) infinite;will-change:transform}@keyframes trustPulse{0%,100%{transform:scale(1)}45%{transform:scale(1.7)}72%{transform:scale(1.18)}}.trust-indicator.warning{color:var(--warn);background:linear-gradient(180deg,var(--warn-soft),#fffaf0);border-color:#f6d493;--trust-ring:rgba(180,83,9,.2)}.trust-indicator.error{color:var(--err);background:linear-gradient(180deg,var(--err-soft),#fff8f6);border-color:#f6b7ad;--trust-ring:rgba(180,35,24,.2)}.signature-panel{position:relative;overflow:hidden;display:flex;flex-direction:column;gap:14px;padding:18px;background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(247,251,255,.94));border-color:#c9d9ec}.signature-panel:before{content:'';position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,var(--ok),rgba(0,120,212,.28));opacity:.5}.signature-panel.warning{border-color:#f6d493;background:linear-gradient(180deg,#fffaf1,#fffdf7)}.signature-panel.warning:before{background:linear-gradient(90deg,var(--warn),rgba(180,83,9,.22))}.signature-panel.error{border-color:#f6b7ad;background:linear-gradient(180deg,#fff7f5,#fffdfc)}.signature-panel.error:before{background:linear-gradient(90deg,var(--err),rgba(180,35,24,.22))}.signature-panel>*{position:relative}.signature-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.signature-head h2{margin:0;color:#475569;font-weight:760}.signature-status-card{display:grid;gap:4px;border:1px solid #a9ddb7;border-radius:10px;background:linear-gradient(135deg,#f0fbf3,#fbfffc);padding:13px 14px;box-shadow:inset 0 1px 0 rgba(255,255,255,.8)}.signature-status-card.warning{border-color:#f6d493;background:linear-gradient(135deg,var(--warn-soft),#fffaf0)}.signature-status-card.error{border-color:#f6b7ad;background:linear-gradient(135deg,var(--err-soft),#fff8f6)}.signature-status-card span{color:var(--muted);font-size:12px}.signature-status-card strong{color:#0f172a;font-size:16px;font-weight:760;line-height:1.25}.signature-status-card.error strong{color:var(--err)}.signature-kv{display:grid;gap:9px;margin:0}.signature-kv div{display:grid;grid-template-columns:minmax(104px,30%) minmax(0,1fr);gap:12px;align-items:center;border:1px solid #d5e2f0;border-radius:8px;background:linear-gradient(180deg,#fbfdff,#f5f8fc);padding:10px 12px;box-shadow:inset 0 1px 0 rgba(255,255,255,.7);transition:transform .16s ease,border-color .16s ease,background-color .16s ease}.signature-kv div:hover{border-color:#b8c9dd;background:#fff;box-shadow:0 7px 16px rgba(31,79,143,.07);transform:translateY(-1px)}.signature-kv dt{color:var(--muted);font-size:12px}.signature-kv dd{margin:0;color:#172033;font-weight:560;line-height:1.25;overflow-wrap:anywhere}.signature-kv .mono{font-size:13px;font-weight:560}.source-health{border-top:1px solid var(--line);padding-top:10px;display:grid;gap:8px}.source-health h3{margin:0;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0}.source-health-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.source-tile{border:1px solid var(--line);border-radius:8px;padding:10px;min-width:0;background:var(--soft)}.source-tile.ok{border-color:#b9e6c4;background:linear-gradient(180deg,var(--ok-soft),#f8fff9)}.source-tile.warning{border-color:#f6d493;background:linear-gradient(180deg,var(--warn-soft),#fffaf0)}.source-tile.error{border-color:#f6b7ad;background:linear-gradient(180deg,var(--err-soft),#fff8f6)}.source-tile.unknown{border-color:var(--line);background:linear-gradient(180deg,var(--unknown-soft),#fbfdff)}.source-tile-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}.source-status{border:1px solid var(--line);border-radius:999px;background:#fff;color:#475569;padding:2px 7px;font-size:11px;font-weight:750}.source-status.ok{color:var(--ok);border-color:#b9e6c4;background:#fff}.source-status.warning{color:var(--warn);border-color:#f6d493;background:#fff}.source-status.error{color:var(--err);border-color:#f6b7ad;background:#fff}.source-status.unknown{color:var(--unknown);background:#fff}.source-tile a{display:block;margin:8px 0 10px;font-size:13px}.source-tile>span{display:block;margin-top:4px;color:var(--muted);font-size:13px}.mini-kv{display:grid;grid-template-columns:80px minmax(0,1fr);gap:5px 10px;margin:0;font-size:12px}.mini-kv dt{color:var(--muted)}.mini-kv dd{margin:0;font-weight:650;overflow-wrap:anywhere}\n"
        "    .source-diagnostics{display:flex;flex-direction:column;gap:10px;min-height:0;align-self:start}.diag-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;flex:0 0 auto}.diag-tile{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;column-gap:8px;min-height:48px;border:1px solid var(--line);border-radius:8px;background:linear-gradient(180deg,#fbfdff,#f2f7ff);padding:8px 10px}.diag-tile strong{display:block;font-size:22px;line-height:1}.diag-tile span{color:var(--muted);font-size:12px}.diag-tile.notice{border-color:#bfdbfe;background:linear-gradient(180deg,var(--blue-soft),#f8fbff)}.diag-tile.notice strong{color:var(--blue)}.diag-tile.notice span{color:var(--blue-strong);font-weight:650}.diag-tile.warning{border-color:#f6d493;background:linear-gradient(180deg,var(--warn-soft),#fffaf0)}.diag-tile.warning strong{color:var(--warn)}.diag-tile.warning span{color:var(--warn);font-weight:650}.diag-tile.error{border-color:#f6b7ad;background:linear-gradient(180deg,var(--err-soft),#fff8f6)}.diag-tile.error strong{color:var(--err)}.diag-tile.error span{color:var(--err);font-weight:650}.diag-feed{margin-top:2px;height:340px;min-height:340px;max-height:340px;overflow-y:scroll;overscroll-behavior:contain;scrollbar-gutter:stable;border:1px solid #d8dee8;border-radius:8px;background:linear-gradient(180deg,#f6f7f9,#eef1f5);padding:14px 11px 24px 14px;box-shadow:inset 0 1px 2px rgba(15,23,42,.06);scrollbar-width:thin;scrollbar-color:#a8b0bc #eef1f5}.diag-feed::-webkit-scrollbar{width:10px}.diag-feed::-webkit-scrollbar-track{background:#eef1f5;border-radius:999px}.diag-feed::-webkit-scrollbar-thumb{background:#a8b0bc;border-radius:999px;border:2px solid #eef1f5}.diag-events{display:grid;gap:10px;padding:2px 2px 24px}.diag-events-empty .diag-row{background:linear-gradient(90deg,#ffffff,#f8fafc)}.diag-row{display:grid;grid-template-columns:4px minmax(0,1fr);gap:8px;border:1px solid var(--line);border-radius:8px;background:#fbfdff;padding:8px}.diag-row.warning{border-color:#f6d493;background:linear-gradient(90deg,#fffaf0,#ffffff)}.diag-row.error{border-color:#f6b7ad;background:linear-gradient(90deg,#fff8f6,#ffffff)}.diag-row p{margin:3px 0 0;color:#475569;font-size:13px;line-height:1.35}.diag-stripe{display:block;border-radius:999px;background:var(--blue)}.diag-row.warning .diag-stripe{background:var(--warn)}.diag-row.error .diag-stripe{background:var(--err)}.diag-row-head{display:flex;flex-wrap:wrap;gap:5px;align-items:center}.diag-row-head strong{font-size:13px}.severity-badge,.source-chip,.diag-tags span{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:2px 7px;font-size:11px;font-weight:700;background:#fff;color:#475569}.severity-badge.notice{color:var(--blue-strong);background:var(--blue-soft);border-color:#bfdbfe}.severity-badge.warning{color:var(--warn);background:var(--warn-soft);border-color:#f6d493}.severity-badge.error{color:var(--err);background:var(--err-soft);border-color:#f6b7ad}.source-chip{font-weight:650}.diag-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}.diag-tags:empty{display:none}.diag-more{border:1px solid var(--line);border-radius:8px;background:var(--soft);padding:8px}.diag-more summary{cursor:pointer;color:#075985;font-size:13px;font-weight:750}.diag-more .diag-events{margin-top:8px}\n"
        "    .programmatic-api{display:flex;flex-direction:column;justify-content:flex-start}.api-endpoints{display:grid;gap:9px}.api-endpoint-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;border:1px solid var(--line);border-radius:8px;background:linear-gradient(180deg,#f8fafc,#f3f6fa);padding:10px 11px;color:inherit;text-decoration:none}.api-endpoint-row:hover{border-color:#b8c9dd;background:#ffffff;text-decoration:none}.api-endpoint-row:focus-visible{outline:3px solid rgba(0,120,212,.28);outline-offset:3px}.api-endpoint-row strong{display:block;color:#172033;font-size:13px;line-height:1.25}.api-endpoint-row em{display:block;margin-top:2px;color:var(--muted);font-size:12px;font-style:italic;font-weight:500;line-height:1.35}.api-endpoint-row code{font-family:Consolas,Menlo,monospace;font-size:12px;color:var(--code);white-space:normal;text-align:right;overflow-wrap:anywhere}.api-note{margin-bottom:12px}.warnings{margin:0;padding-left:18px;color:var(--warn)}footer{display:grid;gap:7px;justify-items:center;margin-top:16px;color:var(--muted);font-size:12px;line-height:1.45;text-align:center}.footer-note{max-width:900px;margin:0}.footer-disclaimer,.footer-owner{color:#64748b}.footer-source{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:4px 6px}.footer-github{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.78);padding:2px 8px;color:#075985;font-weight:750;white-space:nowrap}.footer-license-basic{color:#075985;font-weight:650;text-decoration:none}.footer-license-basic:hover,.footer-license-basic:focus-visible{text-decoration:underline}.github-icon{width:13px;height:13px;display:block;flex:0 0 auto}@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important;animation:none!important}.signature-kv div:hover{transform:none!important}}\n"
        "    @media(min-width:901px){#live-freshness-panel{grid-column:1/span 5;grid-row:1/span 2}.source-diagnostics{grid-column:6/span 7;grid-row:1/span 2}.signature-panel{grid-column:1/span 5;grid-row:3}.programmatic-api{grid-column:6/span 7;grid-row:3}}\n"
        "    @media(max-width:900px){.grid{grid-template-columns:repeat(6,minmax(0,1fr))}.span-3,.span-4{grid-column:span 3}.span-5,.span-6,.span-7,.span-8,.span-12{grid-column:span 6}.source-health-grid{grid-template-columns:1fr}.brand-layout{grid-template-columns:1fr}.header-actions{align-items:flex-start}.header-nav{--item-size:37px}.nav-hover-label{display:none}.title-version-link{margin-left:0}}\n"
        "    @media(min-width:741px) and (max-width:900px){.signature-panel{grid-column:span 3}.programmatic-api{grid-column:span 3}.api-endpoint-row{grid-template-columns:1fr}.api-endpoint-row code{text-align:left}}\n"
        "    @media(max-width:740px){.signature-panel,.programmatic-api{grid-column:1/-1}.signature-head{display:grid}.signature-kv div,.api-endpoint-row{grid-template-columns:1fr}.api-endpoint-row code{text-align:left}}\n"
        "    @media(max-width:640px){main{padding:18px 12px}.masthead{padding:16px}.brand{display:grid;grid-template-columns:44px minmax(0,1fr);gap:14px;align-items:start}.brand-layout{gap:12px}.winmark{width:44px;height:44px}.title-line h1{font-size:23px}.subtitle-line{flex-wrap:wrap;gap:5px 12px}.header-nav{--item-size:35px;max-width:100%}.header-nav .nav-inner{width:max-content;max-width:100%;gap:3px;padding:3px}.header-nav .nav-inner a{height:32px}.header-nav svg{width:19px;height:19px}.title-version-link{font-size:12px;margin-left:0}.subtitle{font-size:14px;max-width:240px}.grid{grid-template-columns:1fr;gap:12px}.span-3,.span-4,.span-5,.span-6,.span-7,.span-8,.span-12{grid-column:auto}.kv{grid-template-columns:1fr}.diag-summary,.thresholds{grid-template-columns:1fr}.diag-feed{height:300px;min-height:300px;max-height:300px}}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <header class=\"masthead\">\n"
        "      <div class=\"brand\"><div class=\"winmark\" aria-hidden=\"true\"><span></span><span></span><span></span><span></span></div><div class=\"brand-layout\"><div class=\"brand-copy\"><span class=\"eyebrow\">Signed public policy feed</span><div class=\"title-line\"><h1>Windows 11 Release Guard</h1></div><div class=\"subtitle-line\"><p class=\"subtitle\">Broad-fleet Windows 11 release and quality baseline dashboard.</p></div></div><div class=\"header-actions\">"
        f"{_header_nav_html()}"
        f"{_program_title_version_html(program_version)}"
        "</div></div></div>\n"
        "    </header>\n"
        "    <section class=\"grid kpi-grid\" id=\"policy-summary\" aria-label=\"Policy summary\">\n"
        "      <article class=\"panel span-3\"><h2>Broad target</h2>"
        f"<div class=\"metric blue\">{escape(target_release)}</div><span class=\"label\">existing Windows 11 devices</span></article>\n"
        "      <article class=\"panel span-3\"><h2>Build family</h2>"
        f"<div class=\"metric\">{escape(target_family)}</div><span class=\"label\">Windows build line</span></article>\n"
        "      <article class=\"panel span-3\"><h2>Latest observed</h2>"
        f"<div class=\"metric\">{escape(target_latest_observed or 'unknown')}</div><span class=\"label\">Microsoft Current Versions table</span></article>\n"
        "      <article class=\"panel span-3\"><h2>Required baseline</h2>"
        f"<div class=\"metric\">{escape(target_baseline or 'unknown')}</div><span class=\"label\">{escape(policy.quality_policy.value)} floor</span></article>\n"
        "    </section>\n"
        "    <section class=\"grid dashboard-grid\" aria-label=\"Policy operations dashboard\">\n"
        "      <section class=\"panel span-5 status-card\" id=\"live-freshness-panel\" aria-label=\"Policy feed currency\"><div class=\"freshness-head\"><h2>Policy Feed Currency</h2><span id=\"live-freshness-state\" class=\"freshness-state unknown\" aria-live=\"polite\" aria-label=\"Published policy feed currency: Unknown\">Unknown</span></div>"
        "<span class=\"label\">Published feed age</span>"
        f"<div id=\"live-generated-age\" class=\"freshness-metric\" aria-live=\"polite\">{generated_age_days:g} days</div>"
        "<p id=\"live-freshness-detail\" class=\"freshness-detail\">Render-time fallback. Browser recalculates published policy feed age from the GitHub Actions generated timestamp when JavaScript is available.</p>"
        f"<div class=\"thresholds\"><div><strong>{DEFAULT_POLICY_WARNING_AGE_DAYS} days</strong><span>refresh-due threshold</span></div><div><strong>{DEFAULT_POLICY_STRICT_STALE_AGE_DAYS} days</strong><span>stale threshold</span></div></div>"
        "<dl class=\"kv metadata\">"
        f"<dt>Berlin, Germany:</dt><dd class=\"refresh\">{escape(generated_human)}<span>GitHub workflow static feed generation</span></dd>"
        f"<dt>Time (UTC):</dt><dd>{_time_with_epoch_copy_html(generated_at_utc, label='policy generated UTC')}</dd>"
        f"<dt>Published feed age:</dt><dd>{generated_age_days:g} days at render-time fallback</dd>"
        f"<dt>Workflow refresh:</dt><dd>{escape(workflow_run)}<span>last automatic publish run, when generated in GitHub Actions</span></dd>"
        "<noscript><dt>Browser update:</dt><dd>JavaScript disabled; published feed age cannot recalculate in the browser.</dd></noscript>"
        "</dl></section>\n"
        f"{source_diagnostics_panel}"
        f"      <section class=\"panel span-5 signature-panel{trust_class}\"><div class=\"signature-head\"><h2>Signature</h2><span class=\"trust-indicator{trust_class}\">{escape(trust_indicator)}</span></div>"
        f"<div class=\"signature-status-card{trust_class}\"><span>Document trust state</span><strong>{escape(signature_status)}</strong><span>Detached signature metadata for the published policy artifact.</span></div>"
        "<dl class=\"signature-kv\">"
        f"<div><dt>Algorithm</dt><dd>{escape(signature_algorithm)}</dd></div>"
        f"<div><dt>key_id</dt><dd class=\"mono\">{escape(key_id)}</dd></div>"
        f"<div><dt>Policy SHA-256</dt><dd>{_hash_html(policy_hash)}</dd></div>"
        f"<div><dt>Signature status</dt><dd>{escape(signature_status)}</dd></div>"
        "</dl></section>\n"
        f"{warning_block}\n"
        "      <section class=\"panel span-7 programmatic-api\"><h2>Programmatic API</h2>"
        "<p class=\"subtitle api-note\">Public JSON policy artifacts for fleet dashboards and scripts.</p>"
        "<div class=\"api-endpoints\">"
        f"{endpoint_links}"
        "</div></section>\n"
        "    </section>\n"
        f"    {_footer_html()}\n"
        "  </main>\n"
        f"  <script type=\"application/json\" id=\"policy-freshness-data\">{_safe_json_script_payload(freshness_data)}</script>\n"
        "  <script>\n"
        "    (function(){\n"
        "      var dataNode=document.getElementById('policy-freshness-data');\n"
        "      var stateNode=document.getElementById('live-freshness-state');\n"
        "      var ageNode=document.getElementById('live-generated-age');\n"
        "      var detailNode=document.getElementById('live-freshness-detail');\n"
        "      var uiActive=true;\n"
        "      var uiFrames=[];\n"
        "      var uiTimers=[];\n"
        "      function reportUiError(scope,error){\n"
        "        if(document.documentElement){document.documentElement.setAttribute('data-ui-last-error',scope);}\n"
        "        if(window.console&&console.warn){console.warn('Windows 11 Release Guard UI '+scope+' failed',error);}\n"
        "      }\n"
        "      function guard(scope,fn){try{return fn();}catch(error){reportUiError(scope,error);return undefined;}}\n"
        "      function safeSetTimeout(fn,delay){\n"
        "        if(!uiActive){return 0;}\n"
        "        var id=window.setTimeout(function(){if(uiActive){guard('timer callback',fn);}},delay);\n"
        "        uiTimers.push(['timeout',id]);\n"
        "        return id;\n"
        "      }\n"
        "      function safeSetInterval(fn,delay){\n"
        "        if(!uiActive){return 0;}\n"
        "        var id=window.setInterval(function(){if(uiActive){guard('interval callback',fn);}},delay);\n"
        "        uiTimers.push(['interval',id]);\n"
        "        return id;\n"
        "      }\n"
        "      function safeRequestFrame(fn){\n"
        "        if(!uiActive){return 0;}\n"
        "        if(!window.requestAnimationFrame){return safeSetTimeout(fn,16);}\n"
        "        var id=window.requestAnimationFrame(function(){if(uiActive){guard('animation frame',fn);}});\n"
        "        uiFrames.push(id);\n"
        "        return id;\n"
        "      }\n"
        "      function safeCancelFrame(id){\n"
        "        if(!id){return;}\n"
        "        if(window.cancelAnimationFrame){window.cancelAnimationFrame(id);}else{window.clearTimeout(id);}\n"
        "      }\n"
        "      function shutdownUi(){\n"
        "        uiActive=false;\n"
        "        uiFrames.forEach(safeCancelFrame);\n"
        "        uiFrames=[];\n"
        "        uiTimers.forEach(function(entry){if(entry[0]==='interval'){window.clearInterval(entry[1]);}else{window.clearTimeout(entry[1]);}});\n"
        "        uiTimers=[];\n"
        "      }\n"
        "      window.addEventListener('pagehide',shutdownUi,{once:true});\n"
        "      window.addEventListener('beforeunload',shutdownUi,{once:true});\n"
        "      function setText(node,value){if(uiActive&&node&&node.isConnected){node.textContent=value;}}\n"
        "      function setState(state,label,detail){\n"
        "        if(!uiActive){return;}\n"
        "        if(stateNode&&stateNode.isConnected){stateNode.className='freshness-state '+state;stateNode.textContent=label;stateNode.setAttribute('aria-label','Published policy feed currency: '+label);}\n"
        "        setText(detailNode,detail);\n"
        "      }\n"
        "      function formatAge(seconds){\n"
        "        var days=seconds/86400;\n"
        "        if(days>=2){return days.toFixed(1).replace(/\\.0$/,'')+' days';}\n"
        "        var hours=seconds/3600;\n"
        "        if(hours>=2){return hours.toFixed(1).replace(/\\.0$/,'')+' hours';}\n"
        "        var minutes=Math.max(0,Math.floor(seconds/60));\n"
        "        return minutes+' minutes';\n"
        "      }\n"
        "      function fallbackCopy(text){\n"
        "        if(!uiActive||!document.body){return Promise.reject(new Error('copy unavailable'));}\n"
        "        var area=document.createElement('textarea');\n"
        "        area.value=text;area.setAttribute('readonly','');\n"
        "        area.style.position='fixed';area.style.left='-9999px';\n"
        "        var ok=false;\n"
        "        try{document.body.appendChild(area);area.select();ok=Boolean(document.execCommand&&document.execCommand('copy'));}catch(_error){ok=false;}finally{if(area.parentNode){area.parentNode.removeChild(area);}}\n"
        "        return ok ? Promise.resolve() : Promise.reject(new Error('copy failed'));\n"
        "      }\n"
        "      function copyText(text){\n"
        "        if(!uiActive){return Promise.reject(new Error('ui inactive'));}\n"
        "        try{if(navigator.clipboard&&navigator.clipboard.writeText){return navigator.clipboard.writeText(text);}}catch(_error){return fallbackCopy(text);}\n"
        "        return fallbackCopy(text);\n"
        "      }\n"
        "      function markCopyButton(button,state,title){\n"
        "        if(!uiActive||!button||!button.isConnected){return;}\n"
        "        button.setAttribute('data-copy-state',state);\n"
        "        button.setAttribute('title',title);\n"
        "        safeSetTimeout(function(){if(button&&button.isConnected){button.removeAttribute('data-copy-state');button.setAttribute('title',button.getAttribute('data-default-title')||'Copy epoch millisecond timestamp');}},1600);\n"
        "      }\n"
        "      Array.prototype.forEach.call(document.querySelectorAll('.epoch-copy[data-epoch]'),function(button){\n"
        "        button.setAttribute('data-default-title',button.getAttribute('title')||'Copy epoch millisecond timestamp');\n"
        "        button.addEventListener('click',function(){guard('copy epoch',function(){\n"
        "          if(!uiActive||!button.isConnected){return;}\n"
        "          var epoch=button.getAttribute('data-epoch')||'';\n"
        "          if(!/^\\d+$/.test(epoch)){markCopyButton(button,'failed','Epoch millisecond timestamp unavailable');return;}\n"
        "          copyText(epoch).then(function(){markCopyButton(button,'copied','Copied epoch millisecond timestamp '+epoch);}).catch(function(){markCopyButton(button,'failed','Could not copy epoch millisecond timestamp');});\n"
        "        });});\n"
        "      });\n"
        "      function initHeaderNav(){\n"
        "        var nav=document.querySelector('.header-nav');\n"
        "        if(!nav){return;}\n"
        "        var items=nav.querySelectorAll('.nav-inner a');\n"
        "        if(!items.length){return;}\n"
        "        var frame=0;\n"
        "        var label=nav.querySelector('.nav-hover-label');\n"
        "        function setItem(item,x,y){\n"
        "          if(!uiActive||!nav.isConnected||!item||!item.isConnected){return;}\n"
        "          var navRect=nav.getBoundingClientRect();\n"
        "          var rect=item.getBoundingClientRect();\n"
        "          var text=item.getAttribute('data-nav-label')||item.getAttribute('aria-label')||'';\n"
        "          nav.style.setProperty('--enter-nav','1');\n"
        "          nav.style.setProperty('--label-x',String((rect.left-navRect.left)+(rect.width/2)+(x*5))+'px');\n"
        "          nav.style.setProperty('--label-y',String(y*3)+'px');\n"
        "          if(label&&label.isConnected&&text){label.textContent=text;}\n"
        "        }\n"
        "        function queue(item,event){\n"
        "          if(!uiActive||!item||!item.isConnected||!event){return;}\n"
        "          if(frame){safeCancelFrame(frame);}\n"
        "          frame=safeRequestFrame(function(){\n"
        "            frame=0;\n"
        "            if(!uiActive||!item.isConnected){return;}\n"
        "            var rect=item.getBoundingClientRect();\n"
        "            var x=((event.clientX-rect.left)-(rect.width/2))/rect.width;\n"
        "            var y=((event.clientY-rect.top)-(rect.height/2))/rect.height;\n"
        "            setItem(item,Math.max(-.5,Math.min(.5,x)),Math.max(-.5,Math.min(.5,y)));\n"
        "          });\n"
        "        }\n"
        "        Array.prototype.forEach.call(items,function(item,index){\n"
        "          item.addEventListener('pointermove',function(event){guard('header nav pointer',function(){queue(item,event);});},{passive:true});\n"
        "          item.addEventListener('focus',function(){guard('header nav focus',function(){setItem(item,0,0);});});\n"
        "        });\n"
        "        nav.addEventListener('pointerleave',function(){if(nav.isConnected){nav.style.setProperty('--enter-nav','0');}});\n"
        "        nav.addEventListener('focusout',function(){safeSetTimeout(function(){if(uiActive&&nav.isConnected&&!nav.contains(document.activeElement)){nav.style.setProperty('--enter-nav','0');}},0);});\n"
        "      }\n"
        "      guard('header nav init',initHeaderNav);\n"
        "      function update(){\n"
        "        if(!uiActive){return;}\n"
        "        var data;\n"
        "        try{data=JSON.parse(dataNode ? dataNode.textContent : '{}');}catch(_error){data={};}\n"
        "        var generated=Number(data.generated_at_epoch_s);\n"
        "        if(!Number.isFinite(generated)||generated<=0){setText(ageNode,'unknown');setState('unknown','Unknown','Published policy feed timestamp is unavailable or invalid; feed currency cannot be calculated in the browser.');return;}\n"
        "        var now=Math.floor(Date.now()/1000);\n"
        "        if(!Number.isFinite(now)){setText(ageNode,'unknown');setState('unknown','Unknown','Published policy feed age cannot be calculated because browser time is unavailable.');return;}\n"
        "        var ageSeconds=Math.max(0,now-generated);\n"
        "        var warningSeconds=Number(data.warning_age_seconds)||1209600;\n"
        "        var staleSeconds=Number(data.strict_stale_age_seconds)||3888000;\n"
        "        setText(ageNode,formatAge(ageSeconds));\n"
        "        if(ageSeconds>=staleSeconds){setState('stale','Stale','Published policy feed is stale. Do not treat this data as production-current until automation refresh succeeds.');return;}\n"
        "        if(ageSeconds>=warningSeconds){setState('refresh-due','Refresh Due','Published policy feed refresh is due. Verify automation health before treating this data as production-current.');return;}\n"
        f"        setState('current','Current','Published policy feed is within the {DEFAULT_POLICY_WARNING_AGE_DAYS}-day maintenance threshold.');\n"
        "      }\n"
        "      guard('freshness update',update);\n"
        "      safeSetInterval(function(){guard('freshness update',update);},60000);\n"
        "    }());\n"
        "  </script>\n"
        "</body>\n"
        "</html>\n"
    )


def render_robots_txt() -> str:
    return ROBOTS_TXT


def render_sitemap_xml(policy: ReleasePolicy, *, base_url: str = DEFAULT_PAGES_BASE_URL) -> str:
    generated_at = escape(policy.generated_at_utc or _utc_now())
    urls = (
        f"{base_url}/",
        f"{base_url}/windows-release-policy.json",
        f"{base_url}/policy-manifest.json",
    )
    entries = "\n".join(
        (
            "  <url>\n"
            f"    <loc>{escape(url)}</loc>\n"
            f"    <lastmod>{generated_at}</lastmod>\n"
            "  </url>"
        )
        for url in urls
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{entries}\n"
        "</urlset>\n"
    )


def _published_urls_for_base_url(base_url: str) -> dict[str, str]:
    normalized = base_url.rstrip("/")
    return {
        "landing": f"{normalized}/",
        "policy": f"{normalized}/windows-release-policy.json",
        "signature": f"{normalized}/windows-release-policy.json.sig",
        "manifest": f"{normalized}/policy-manifest.json",
        "api_policy": f"{normalized}/api/v1/policy.json",
        "api_signature": f"{normalized}/api/v1/policy.sig",
        "api_manifest": f"{normalized}/api/v1/manifest.json",
    }


def render_policy_manifest(
    policy: ReleasePolicy,
    *,
    policy_bytes: bytes,
    signature_bytes: bytes | None,
    signature: Mapping[str, Any] | None = None,
    base_url: str = DEFAULT_PAGES_BASE_URL,
) -> str:
    target = policy.broad_target_existing_devices
    policy_sha256 = _sha256_hex(policy_bytes)
    signature_sha256 = _sha256_hex(signature_bytes)
    status = _status_text(policy)
    manifest = {
        "schema_version": 1,
        "generated_at_utc": policy.generated_at_utc,
        "generated_at_human": _generated_at_human(policy.generated_at_utc),
        "timezone": PAGES_TIMEZONE,
        **freshness_thresholds(policy.generated_at_utc),
        "freshness_policy": freshness_policy_metadata(),
        "generator_version": policy.generator_version,
        "policy_schema_version": policy.schema_version,
        "min_reader_schema_version": policy.min_reader_schema_version,
        "max_reader_schema_version": policy.max_reader_schema_version,
        "api_version": policy.api_version,
        "compatibility": dict(policy.compatibility),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "commit_sha": os.environ.get("GITHUB_SHA"),
        "policy_sha256": policy_sha256,
        "signature_sha256": signature_sha256,
        "signature_algorithm": _signature_field(signature, "algorithm"),
        "key_id": _signature_field(signature, "key_id"),
        "source_urls": list(policy.source_urls),
        "source_diagnostics": dict(policy.source_diagnostics),
        "published_urls": dict(policy.published_urls or _published_urls_for_base_url(base_url)),
        "broad_target_existing_devices": (
            {
                "version": target.version,
                "build_family": target.build_family,
                "latest_build": target.latest_build,
                "latest_observed_build": target.latest_observed_build,
                "baseline_build": target.baseline_build,
                "required_baseline_build": target.required_baseline_build,
            }
            if target
            else None
        ),
        "latest_observed_build": target.latest_observed_build if target else None,
        "baseline": target.required_baseline_build if target else None,
        "required_baseline_build": target.required_baseline_build if target else None,
        "warnings": list(policy.validation_warnings),
        "status": status,
    }
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def build_policy_from_sources(
    *,
    release_health_url: str = DEFAULT_RELEASE_HEALTH_URL,
    atom_feed_url: str = DEFAULT_WINDOWS11_ATOM_FEED_URL,
    release_health_html_path: str | Path | None = None,
    atom_feed_path: str | Path | None = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    signature_status: str = "unsigned",
) -> ReleasePolicy:
    release_health = load_source_text(
        url=release_health_url,
        fixture_path=release_health_html_path,
        source_name="release_health_html",
        timeout=timeout,
        required=True,
    )
    atom_feed = load_source_text(
        url=atom_feed_url,
        fixture_path=atom_feed_path,
        source_name="atom_feed",
        timeout=timeout,
        required=False,
    )
    source_fetch_status = {
        "release_health_html": dict(release_health.status),
        "atom_feed": dict(atom_feed.status),
    }
    return generate_policy(
        release_health_html=release_health.text,
        atom_feed_xml=atom_feed.text or None,
        release_health_url=release_health_url,
        atom_feed_url=atom_feed_url,
        source_fetch_status=source_fetch_status,
        signature_status=signature_status,
    )


__all__ = [
    "DEFAULT_WINDOWS11_ATOM_FEED_URL",
    "AtomFeedEntry",
    "SourceText",
    "build_policy_from_sources",
    "generate_policy",
    "generate_policy_json",
    "load_source_text",
    "parse_atom_feed",
    "render_policy_index",
    "render_policy_manifest",
    "render_robots_txt",
    "render_sitemap_xml",
    "sign_policy_bytes",
    "write_policy_outputs",
]

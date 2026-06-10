# Source Diagnostics

Use this when investigating generator/parser drift, Microsoft source changes, Atom feed enrichment, or publish blocks.

---

## Diagnostic Sources

Source diagnostics explain the health of the policy inputs and generator
interpretation, not the final compliance verdict by themselves. They collect
Release Health, Atom feed, parser, and drift signals so an administrator can see
whether the public Microsoft source data changed, whether enrichment arrived
late, or whether a parser assumption needs attention.

The dashboard severity tiles are filters over those generated events. Notices
are visibility-only, warnings call out non-blocking drift or missing enrichment,
and errors are publish-blocking because an error means the generated policy
could not be safely derived. This keeps source problems visible without letting
browser JavaScript mutate GitHub, hide parser failures, or turn diagnostics into
verdict authority.

| Source | Captured data |
| --- | --- |
| Microsoft Release Health HTML | Bytes, fetch time, newest current-version revision, newest release-history date. |
| Microsoft Update History Atom feed | Bytes, newest Atom build, newest published/updated timestamps. |
| Parser | Structured events for missing/changed headers and table anomalies. |
| Drift checks | Current table lag, Atom newer rows, generated-after-source age. |

## Event Severity

| Severity | Meaning |
| --- | --- |
| `notice` | Informational; visible in policy output and the dashboard, but not synced to GitHub Issues. |
| `warning` | Non-blocking drift or missing enrichment; verify before trusting manually. |
| `error` | Publish-blocking source or parser failure. |

Atom drift keeps Preview and out-of-band rows at `notice` severity even when the
build number is newer than Release History. A newer non-preview build for the
current broad target becomes `warning` only when reliable baseline evidence is
present, because it may affect the required baseline after Microsoft source
publication catches up. Missing or malformed Atom input is also `warning`; it is
visible source-health degradation, not a silent condition.

Microsoft's public sources can arrive out of order. The Atom/Update History feed
can expose a KB or build before the Release Health HTML release-history table is
manually refreshed. That race is normal for Preview, out-of-band, unknown-family,
non-broad-target, or incomplete Atom rows, so those rows stay `notice`. Missing
KB metadata is an uncertainty marker, not permanent proof that a row is harmless.
A row is treated as required-baseline drift only when it maps to the current
broad target, is not Preview or out-of-band, and has reliable baseline evidence.
In the current generator that evidence is an extracted KB plus the build/release
mapping; another durable upstream marker would need tests before it could serve
the same role. The `source_drift_unresolved_after_24h` event is reserved for
warning/error drift that remains unresolved after the newest source timestamp,
not for normal notice-only feed lag.

## Diagnostic IDs

Source diagnostic IDs use stable event identity fields: severity, source,
event kind/category, release, build family, build, KB article, affected target
flags, and the source URL host/path when present. Generated timestamps, fetched
timestamps, exact message wording, tag order, and display-only prose are not part
of the normal ID basis.

## Publish Gate

`publish-policy.yml` rejects generated policy output when `source_diagnostics.events` contains `severity: error`. This keeps stale or structurally broken upstream parsing from silently publishing.

## GitHub Issue Sync

Issue sync is workflow-side only and uses the built-in GitHub Actions token.
Its input is deliberately limited to real `source_diagnostics.events` entries
from the generated policy. Dashboard-only rows such as `No source issues
reported`, `26H1 excluded for existing devices`, freshness notices, or other
derived display rows may remain visible and filterable in the Pages UI, but they
do not automatically create or maintain GitHub Issues.
The sync treats an issue as managed only when the body contains exactly one
internal marker:

```text
<!-- wrg-source-diagnostic-id: wrg-source-diagnostic-v1:<hash> -->
```

Labels, titles, and normal text that merely mention a diagnostic ID are ignored
for mutation. Manual issues without that marker are not updated, commented,
reopened, or closed by the sync.

For managed open issues, the sync compares the current title, body, and labels
with the desired diagnostic state. If they already match, the issue is left
unchanged and no "still present" comment is posted. Reopened managed issues and
stale managed issue closes still receive a short workflow comment. New or
updated managed warning/error issues include a compact Markdown tip at the
bottom of the issue body. The tip is selected from the diagnostic kind, severity,
and target flags, and links to the relevant Pages Wiki follow-up page for Atom
drift, parser/source failures, freshness drift, or publish-gate behavior.

Issue-sync labels are fixed as:

| Severity | GitHub label |
| --- | --- |
| `warning` | `internals: warning` |
| `error` | `internals: error` |

Notice events do not create, update, reopen, or keep GitHub Issues current. The
legacy `internals: notices` label may still be searched only so older managed
Notice issues with the exact body marker can be closed as stale. Labels alone do
not make an issue managed; the internal body marker is required.

In the publish workflow, a GitHub Issues API, label, or permission failure in the
sync step is published as static degraded metadata instead of blocking signed
Pages output. The dashboard displays `Issue sync unavailable` from
`source_diagnostics.issue_sync`; source-diagnostic `error` events from the
generator still block publishing.

The dashboard Source Diagnostics tiles are filters. Select Notices, Warnings, or
Errors to show only that severity; select `View all` to reset the feed. Static
`#Ticket <number>` links appear on a row only on hover or keyboard focus and only
when workflow-generated issue metadata provides a canonical repository issue URL
for a real synced event. Not every visible Notice, Warning, or Error row has an
issue.

The small copy button above the diagnostic feed exports the rows visible at the
time of the click as JSON to the local clipboard. The export includes severity,
deterministic diagnostic ID, title, source, message, tags, optional static issue
URL, the active filter, visible counts, and a short neutral context note. It is
meant for technical lookup and handoff of the current dashboard state; it does
not call GitHub, write browser-side data back to the repository, or change the
signed policy verdict.

For rehearsal runs, use `tools/sync_source_diagnostics_issues.py --dry-run` with
`--dry-run-report-output` and `--dry-run-report-format json` or `markdown`.
Dry-run reports list deterministic IDs, severities, labels, skipped Notice
counts, and planned create/update/reopen/close actions without mutating GitHub
Issues or writing tokens.

## Common Issues

| Symptom | Check | Action |
| --- | --- | --- |
| Current Versions parser fails. | Release Health table headers changed. | Update parser tests and code together. |
| Atom feed has newer build than Release Health. | `atom_newer_than_release_history` event. | Inspect whether it is preview/OOB or missing B-release data. |
| Source diagnostics warning appears on dashboard. | Event kind and affected release/build. | Keep visible; only block if severity is error. |

## Verify

```powershell
pytest -q tests/test_remote_policy.py tests/test_policy_generator.py tests/test_publish_policy_workflow.py
python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html --atom-feed tests/fixtures/windows11-atom.xml --output-dir site --write-index --write-manifest
```

## Related Pages

[Home](Home) | [Policy Feed and Trust Model](Policy-Feed-and-Trust-Model) | [GitHub Pages Dashboard](GitHub-Pages-Dashboard)

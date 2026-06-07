# Source Diagnostics

Use this when investigating generator/parser drift, Microsoft source changes, Atom feed enrichment, or publish blocks.

---

## Diagnostic Sources

| Source | Captured data |
| --- | --- |
| Microsoft Release Health HTML | Bytes, fetch time, newest current-version revision, newest release-history date. |
| Microsoft Update History Atom feed | Bytes, newest Atom build, newest published/updated timestamps. |
| Parser | Structured events for missing/changed headers and table anomalies. |
| Drift checks | Current table lag, Atom newer rows, generated-after-source age. |

## Event Severity

| Severity | Meaning |
| --- | --- |
| `notice` | Informational; should remain visible. |
| `warning` | Non-blocking drift or missing enrichment; verify before trusting manually. |
| `error` | Publish-blocking source or parser failure. |

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
stale managed issue closes still receive a short workflow comment.

Severity labels are fixed as:

| Severity | GitHub label |
| --- | --- |
| `notice` | `internals: notices` |
| `warning` | `internals: warning` |
| `error` | `internals: error` |

Labels alone do not make an issue managed; the internal body marker is required.

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

For rehearsal runs, use `tools/sync_source_diagnostics_issues.py --dry-run` with
`--dry-run-report-output` and `--dry-run-report-format json` or `markdown`.
Dry-run reports list deterministic IDs, severities, labels, and planned
create/update/reopen/close actions without mutating GitHub Issues or writing
tokens.

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

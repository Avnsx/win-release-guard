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

## Publish Gate

`publish-policy.yml` rejects generated policy output when `source_diagnostics.events` contains `severity: error`. This keeps stale or structurally broken upstream parsing from silently publishing.

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

[[Home]] | [[Policy Feed and Trust Model|Policy-Feed-and-Trust-Model]] | [[GitHub Pages Dashboard|GitHub-Pages-Dashboard]]

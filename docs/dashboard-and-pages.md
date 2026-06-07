# Dashboard And Pages

Purpose: document the generated static Pages surface and the public endpoint contract that maintainers must preserve.

Related links: [maintainer guide](maintainer-guide.md) | [wiki dashboard](../wiki/GitHub-Pages-Dashboard.md) | [anti-static freshness](anti-static-freshness.md)

## Generated Files

| File | Role |
| --- | --- |
| `site/index.html` | Static dashboard for humans. |
| `site/windows-release-policy.json` | Canonical signed policy JSON. |
| `site/windows-release-policy.json.sig` | Detached Ed25519 signature. |
| `site/policy-manifest.json` | Hashes, freshness, source diagnostics, public URL metadata. |
| `site/api/v1/policy.json` | Compatibility policy alias. |
| `site/api/v1/policy.sig` | Compatibility signature alias. |
| `site/api/v1/manifest.json` | Compatibility manifest alias. |
| `site/robots.txt`, `site/sitemap.xml`, `site/.nojekyll` | GitHub Pages support files. |

`site/` is generated output. Local `site/` is for testing and must not be committed; `.github/workflows/publish-policy.yml` regenerates it inside GitHub Actions, uploads it with `actions/upload-pages-artifact`, and deploys it with `actions/deploy-pages`. Use workflow_dispatch to refresh Pages manually. Docs/wiki-only changes do not need a Pages rebuild unless they affect dashboard-rendered content, generated metadata, public URLs, or workflow path filters.

## Dashboard Contract

| Area | Must show |
| --- | --- |
| Target summary | Broad target, baseline, latest observed build. |
| Excluded releases | Data-driven 26H1 existing-device exclusion summary. |
| Feed currency | Generated time, live age state, 14/45-day thresholds. |
| Source diagnostics | Keyboard-accessible severity filters, deterministic diagnostic IDs, counts, events, source health tiles, drift warnings. |
| Programmatic API | Canonical and `/api/v1` endpoint links. |

The Source Diagnostics count tiles for Notices, Warnings, and Errors are native
buttons. Selecting one filters the event feed to that severity, updates
`aria-pressed`, and reports the visible row count through the live status text.
The `View all` button resets the filter and shows every diagnostic row again.
The feed may include derived dashboard-only rows such as `No source issues
reported`, existing-device exclusion notes, or freshness notices. Those rows are
filterable and may carry deterministic DOM IDs, but they are not GitHub
Issue-sync inputs.

Optional source-diagnostic issue status must be static generated metadata, not
browser-fetched data. When `source_diagnostics.issue_status` maps a deterministic
ID for a real `source_diagnostics.events` entry to a GitHub issue number/state,
the dashboard may render a hover/focus-only `#Ticket <number>` link only to
`https://github.com/Avnsx/win11_release_guard/issues/<number>`. Derived
dashboard-only rows do not show ticket links without workflow-generated metadata
for a real synced event. Invalid IDs, non-positive issue numbers, and
non-canonical issue URLs are ignored. Browser JavaScript must not fetch GitHub
issue state.

When the publish workflow cannot sync GitHub Issues, `source_diagnostics.issue_sync`
may report `status: unavailable`. The dashboard must render that degraded state
as static HTML so missing ticket links are visible without client-side API calls.

## Rules

| Do | Do not |
| --- | --- |
| Keep Pages static and GitHub-Pages-compatible. | Add external JS, CSS, fonts, CDN dependencies, or backend runtime assumptions. |
| Keep Source Diagnostics issue sync in GitHub Actions. | Create GitHub Issues from browser JavaScript or embed GitHub tokens in the dashboard. |
| Keep API aliases byte-equivalent unless manifest documents a compatible difference. | Break `/api/v1` paths. |
| Preserve no-JavaScript fallback text for feed age. | Rely only on render-time generated age. |

## Verify

```powershell
python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html --atom-feed tests/fixtures/windows11-atom.xml --output-dir site --write-index --write-robots --write-sitemap --write-manifest
pytest -q tests/test_pages_landing.py tests/test_policy_generator.py tests/test_policy_source_cli.py
python -m win11_release_guard --check-public-pages
```

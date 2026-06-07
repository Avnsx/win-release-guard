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

Optional source-diagnostic issue status must be static generated metadata, not
browser-fetched data. When `source_diagnostics.issue_status` maps a deterministic
diagnostic ID to a GitHub issue number/state, the dashboard may render a
hover/focus-only `#Ticket <number>` link only to
`https://github.com/Avnsx/win11_release_guard/issues/<number>`. Invalid IDs,
non-positive issue numbers, and non-canonical issue URLs are ignored. Browser
JavaScript must not fetch GitHub issue state.

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

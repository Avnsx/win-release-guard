# GitHub Pages Dashboard

Use this when changing the generated static dashboard or public Pages endpoint contract.

---

## Dashboard Sections

| Section | Shows |
| --- | --- |
| Header | Product display name, program version, dashboard/wiki/repo links. |
| Target cards | Broad target, required baseline, latest observed build. |
| Feed currency | Generated time, live age state, thresholds. |
| Source diagnostics | Counts, source health tiles, drift or parser events. |
| Excluded releases | Data-driven existing-device exclusion summary. |
| Programmatic API | Canonical and `/api/v1` links. |

## Static Output Contract

| File | Required |
| --- | --- |
| `index.html` | Yes |
| `windows-release-policy.json` | Yes |
| `windows-release-policy.json.sig` | Yes when signing key exists in production |
| `policy-manifest.json` | Yes |
| `api/v1/policy.json` | Yes |
| `api/v1/policy.sig` | Yes |
| `api/v1/manifest.json` | Yes |
| `robots.txt`, `sitemap.xml`, `.nojekyll` | Yes for Pages support |

Local `site/` is generated output for testing and must not be committed. The Pages workflow regenerates `site/`, signs policy output, uploads the Pages artifact, deploys it, and then verifies live endpoints. Use workflow_dispatch to refresh Pages manually. Docs/wiki-only changes do not need a Pages rebuild unless they change dashboard-rendered content, generated metadata, public URLs, or workflow path filters.

## Rules

| Do | Do not |
| --- | --- |
| Keep dashboard static and no-token. | Add backend runtime dependencies. |
| Keep JavaScript inline and local. | Add external JS/CSS/fonts/CDNs. |
| Keep public endpoints stable. | Break API aliases or published URL fields. |
| Preserve source diagnostics visibility. | Hide parser/source drift events. |

GitHub Actions schedules are best-effort platform automation and do not guarantee a refresh time. Treat live endpoint checks and generated timestamps as operational truth.

## Verify

```powershell
python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html --atom-feed tests/fixtures/windows11-atom.xml --output-dir site --write-index --write-robots --write-sitemap --write-manifest
pytest -q tests/test_pages_landing.py tests/test_policy_generator.py
python -m win11_release_guard --check-public-pages
```

## Related Pages

[[Home]] | [[Anti-Static Freshness|Anti-Static-Freshness]] | [[Source Diagnostics|Source-Diagnostics]]

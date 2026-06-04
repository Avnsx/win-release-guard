# Dashboard And Pages

Purpose: document the generated static Pages surface and the public endpoint contract that maintainers must preserve.

Related links: [docs index](README.md) | [wiki dashboard](../wiki/GitHub-Pages-Dashboard.md) | [anti-static freshness](anti-static-freshness.md)

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

## Dashboard Contract

| Area | Must show |
| --- | --- |
| Target summary | Broad target, baseline, latest observed build. |
| Excluded releases | Data-driven 26H1 existing-device exclusion summary. |
| Feed currency | Generated time, live age state, 14/45-day thresholds. |
| Source diagnostics | Counts, events, source health tiles, drift warnings. |
| Programmatic API | Canonical and `/api/v1` endpoint links. |

## Rules

| Do | Do not |
| --- | --- |
| Keep Pages static and GitHub-Pages-compatible. | Add external JS, CSS, fonts, CDN dependencies, or backend runtime assumptions. |
| Keep API aliases byte-equivalent unless manifest documents a compatible difference. | Break `/api/v1` paths. |
| Preserve no-JavaScript fallback text for feed age. | Rely only on render-time generated age. |

## Verify

```powershell
python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html --atom-feed tests/fixtures/windows11-atom.xml --output-dir site --write-index --write-robots --write-sitemap --write-manifest
pytest -q tests/test_pages_landing.py tests/test_policy_generator.py tests/test_policy_source_cli.py
python -m win11_release_guard --check-public-pages
```

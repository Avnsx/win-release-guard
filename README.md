# Windows 11 Release Guard

[![CI](https://github.com/Avnsx/win11_release_guard/actions/workflows/ci.yml/badge.svg)](https://github.com/Avnsx/win11_release_guard/actions/workflows/ci.yml)
[![Publish policy](https://github.com/Avnsx/win11_release_guard/actions/workflows/publish-policy.yml/badge.svg)](https://github.com/Avnsx/win11_release_guard/actions/workflows/publish-policy.yml)
[![CodeQL](https://github.com/Avnsx/win11_release_guard/actions/workflows/codeql.yml/badge.svg)](https://github.com/Avnsx/win11_release_guard/actions/workflows/codeql.yml)
[![Pylint](https://github.com/Avnsx/win11_release_guard/actions/workflows/pylint.yml/badge.svg)](https://github.com/Avnsx/win11_release_guard/actions/workflows/pylint.yml)
[![Dependency audit](https://github.com/Avnsx/win11_release_guard/actions/workflows/dependency-audit.yml/badge.svg)](https://github.com/Avnsx/win11_release_guard/actions/workflows/dependency-audit.yml)
[![Dependency freshness](https://github.com/Avnsx/win11_release_guard/actions/workflows/dependency-freshness.yml/badge.svg)](https://github.com/Avnsx/win11_release_guard/actions/workflows/dependency-freshness.yml)

Windows release policy guard for broad-fleet Windows 11 version checks.

Windows 11 Release Guard tells administrators whether an existing Windows 11 device is on the current broad-fleet release and quality baseline, using a signed public policy feed plus local build evidence. The repository, distribution package, installed console command, and Python import package use the same `win11_release_guard` name.

## At A Glance

| Question | Answer |
| --- | --- |
| Current broad target | Windows 11 `25H2` for existing broad-fleet devices |
| Special release handling | `26H1` is treated as new-devices-only / excluded for existing 24H2 or 25H2 devices |
| Trust source | Public JSON policy plus detached Ed25519 signature |
| Local truth model | Build-first evidence; display labels are diagnostics |
| WUA role | Optional read-only secondary evidence |
| Output | Pretty console, JSON, JSON-pretty, file output |
| Version | `0.3.0` |

## Project Identity

- GitHub repo: `https://github.com/Avnsx/win11_release_guard`
- Public feed: `https://avnsx.github.io/win11_release_guard/windows-release-policy.json`
- Python entry point: `python -m win11_release_guard`
- Console script: `win11_release_guard`

Do not reintroduce the old prototype script named by joining `windows`, `releases`, and `info` with underscores and adding `.py`; do not revert naming back to earlier project identities.

## Quick Start

```powershell
python -m pip install -e ".[test]"
python -m win11_release_guard --pretty
python -m win11_release_guard --json-pretty --no-wua
python -m win11_release_guard --check-policy-source
python -m win11_release_guard --check-public-pages
```

For production compliance jobs, prefer:

```powershell
python -m win11_release_guard --strict-production --json-pretty --no-wua
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | compliant or source check passed |
| `1` | feature or quality update required |
| `2` | unknown, incomplete, or source/policy problem |
| `3` | above broad target or special release |
| `10` | CLI argument error |

## Public Feed / Dashboard

| Artifact | Link |
| --- | --- |
| Pages dashboard | https://avnsx.github.io/win11_release_guard/ |
| Signed policy JSON | https://avnsx.github.io/win11_release_guard/windows-release-policy.json |
| Detached signature | https://avnsx.github.io/win11_release_guard/windows-release-policy.json.sig |
| Policy manifest | https://avnsx.github.io/win11_release_guard/policy-manifest.json |
| API v1 policy | https://avnsx.github.io/win11_release_guard/api/v1/policy.json |
| API v1 signature | https://avnsx.github.io/win11_release_guard/api/v1/policy.sig |
| API v1 manifest | https://avnsx.github.io/win11_release_guard/api/v1/manifest.json |

## Workflow Badge Semantics

Dependency freshness is checked by a scheduled workflow. `Dependency freshness` is a scheduled direct-dependency check over direct dependency specifiers; it is not an always-current dependency guarantee. The Pylint badge reports the workflow for the current `--fail-under=8.0` gate, not a permanent quality certificate.

## Core Concepts

- Runtime clients fetch public JSON plus `.sig`; they do not authenticate to GitHub.
- Ed25519 verification, schema validation, hash checks, and source status decide whether policy evidence is usable.
- Local Windows evidence is build-first: `RtlGetVersion`, DISM, kernel file version, registry, and WMI/CIM are weighted signals.
- `ProductName`, WMI `Caption`, and `DisplayVersion` are display-only diagnostics and must not override build and policy evidence.
- WUA is optional read-only secondary evidence; it explains offers/history but never changes the signed policy target.
- `25H2` is the current broad target for existing devices; `26H1` is excluded for existing devices.
- `baseline_build` / `required_baseline_build` is the required B-release baseline; `latest_observed_build` can include newer observed preview/current-table builds.
- B-release baselines are the default quality policy; D-preview builds can be compliant with preview warnings unless disallowed.
- The Pages dashboard avoids static-age drift by embedding `generated_at_epoch_s` and recalculating feed age with browser `Date.now()`.
- `--strict-production` returns production-green only from fresh live signed remote JSON; cache and bundled fallback are degraded evidence.
- Public `/api/v1` aliases and signing-key overlap rules are maintained for at least 24 months unless a documented last-resort trust break is required.

The production generator uses public Microsoft Release Health and Atom sources only; it does not use token-authenticated Microsoft APIs. Runtime clients do not authenticate to GitHub and do not need GitHub tokens, private repository access, or a paid signing certificate. WUA diagnostics never override the policy verdict.

## Wiki Deep Dive

| Topic | Link |
| --- | --- |
| Wiki home | https://github.com/Avnsx/win11_release_guard/wiki |
| Quick Start | https://github.com/Avnsx/win11_release_guard/wiki/Quick-Start |
| Architecture | https://github.com/Avnsx/win11_release_guard/wiki/Architecture |
| Policy Feed & Trust Model | https://github.com/Avnsx/win11_release_guard/wiki/Policy-Feed-and-Trust-Model |
| Local Windows Detection | https://github.com/Avnsx/win11_release_guard/wiki/Local-Windows-Detection |
| GitHub Pages Dashboard | https://github.com/Avnsx/win11_release_guard/wiki/GitHub-Pages-Dashboard |
| Source Diagnostics | https://github.com/Avnsx/win11_release_guard/wiki/Source-Diagnostics |
| Anti-Static Freshness | https://github.com/Avnsx/win11_release_guard/wiki/Anti-Static-Freshness |
| CLI & RMM Usage | https://github.com/Avnsx/win11_release_guard/wiki/CLI-and-RMM-Usage |
| Build, Test & Release | https://github.com/Avnsx/win11_release_guard/wiki/Build-Test-and-Release |
| Tagged Release Lane | https://github.com/Avnsx/win11_release_guard/wiki/Tagged-Release-Lane |
| Safe Exports & Clean Archives | https://github.com/Avnsx/win11_release_guard/wiki/Safe-Exports-and-Clean-Archives |
| Troubleshooting | https://github.com/Avnsx/win11_release_guard/wiki/Troubleshooting |
| Agent Chokepoints | https://github.com/Avnsx/win11_release_guard/wiki/Agent-Chokepoints |
| FAQ | https://github.com/Avnsx/win11_release_guard/wiki/FAQ |

## Maintainer Commands

```powershell
python -m compileall -q win11_release_guard tools
python tools/check_project_identity.py
python tools/check_version_consistency.py
python tools/check_github_action_versions.py
pytest -q
python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github
python tools/export_clean_archive.py --output dist/win11_release_guard-source.zip
python tools/export_clean_archive.py --validate dist/win11_release_guard-source.zip
```

Workflow JavaScript actions opt into Node 24 with `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`.

Deployment-affecting changes require the live Pages gate before handover. Deployment-affecting changes include workflow changes, policy generator changes, signing changes, Pages landing page changes, manifest/API alias changes, source URL or published URL changes, CLI changes to `--check-policy-source`, and `--check-public-pages`. If live network is unavailable, run local/mocked gates and do not claim live success. If a live check fails, record the exact failing URL, status, and error.

Required live-gate command set:

```powershell
python -m compileall -q win11_release_guard tools
pytest -q
python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html --atom-feed tests/fixtures/windows11-atom.xml --output-dir site --write-index --write-robots --write-sitemap --write-manifest
python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github
python -m win11_release_guard --check-policy-source
python -m win11_release_guard --check-public-pages
```

See [docs/README.md](docs/README.md) for maintainer documentation and the local wiki source folder under [wiki/Home.md](wiki/Home.md). Maintainer deep links: [Tagged release lane](docs/tagged-release-lane.md), [policy signing](docs/policy-signing.md), [security automation](docs/security-automation.md).

## Contribution And Security Notes

Do not commit GitHub tokens, private signing keys, raw worktree ZIPs, local handover notes, generated caches, or private key scratch files. Generated policy feed data is public non-secret data, but trust comes from the detached signature and committed public verification keys.

This project is independent open-source software and is not affiliated with Microsoft.

# Release v0.3.4

Compact human summary of the `0.3.4` source-evidence and release-tooling hardening release. Code, tests, workflows, `pyproject.toml`, README, docs, local wiki source, and `AGENTS.md` remain source truth.

---

## Pick Your Path

| You are | Read | Why |
| --- | --- | --- |
| User | [Quick Start](Quick-Start) | Run the guard and understand output/exit codes. |
| Admin / RMM owner | [CLI and RMM Usage](CLI-and-RMM-Usage) | Integrate JSON output and strict-production checks. |
| Maintainer | [Build, Test and Release](Build-Test-and-Release) | Reproduce local gates and release checks. |
| Release manager | [Tagged Release Lane](Tagged-Release-Lane) | Publish a validated source archive and understand the separate PyPI lane. |
| Future agent | [Agent Chokepoints](Agent-Chokepoints) | Avoid known regression traps. |

## Highlights

| Area | 0.3.4 state |
| --- | --- |
| Versioning | Package/runtime/generator/WUA identity is centralized at `win11_release_guard/0.3.4`. |
| Baseline notice copy | Summary wording is source-aware: MSRC only for MSRC CVRF evidence, Microsoft Support for validated Support articles, neutral otherwise; no `B.;` artifact and no raw status enums in human copy. |
| Date parsing | Impossible/malformed Release Health dates degrade instead of crashing; non-padded dates normalize; date-only precision is preserved. |
| Atom fallback | Safe build-agnostic KB-only enrichment is kept while wrong-build, unsafe-URL, Preview/OOB, and ambiguous candidates are rejected; missing hrefs never synthesize `/help/<KB>`. |
| Archive validation | The inner pytest gate runs with plugin autoload disabled and with ambient `PYTEST_ADDOPTS`/`PYTEST_PLUGINS` removed; real failures stay fatal. |
| Pages wiki | The wiki/changelog visual scale and width match the dashboard at normal browser zoom with no zoom/transform/viewport hacks; tables and code blocks use the available width and code blocks gain a hover copy button. |
| PyPI lane | `pypi-publish.yml` builds wheel/sdist and publishes through Trusted Publishing / GitHub OIDC only after tag or published-release gates. |

## What Changed

The baseline-update notice summary is now built from complete, source-aware
sentences. It credits MSRC only when the evidence source is MSRC CVRF, attributes
validated Support article evidence to Microsoft Support, and stays neutral when
evidence is unavailable, unknown, or non-security. It no longer produces a `B.;`
punctuation artifact or exposes raw status enums in user-facing copy; the
machine JSON keeps the structured evidence fields.

Impossible or malformed ISO-shaped Release Health dates degrade to no active
notice instead of crashing generation, and non-zero-padded dates normalize.
Date-only Microsoft precision is preserved without inventing exact times.

Atom remains discovery for Support article hrefs. After exact KB+build and
build-only matching fail, a build-agnostic KB-only candidate may enrich a row
only when its KB matches, it has a safe canonical `support.microsoft.com` href,
it is not Preview/Out-of-band for a normal broad target, it is unambiguous, and
no same-family explicit candidate contradicts the row build. Wrong-build,
unsafe-URL, Preview/OOB, and ambiguous candidates are rejected, and the valid
KB5094126 multi-build case still enriches both explicit build rows.

## Generated Output Coverage

Generated-output regressions exercise the policy JSON, policy manifest, dashboard
HTML, `/api/v1` aliases, visible Source Diagnostics JSON export, and remote
parser acceptance, plus the Pages wiki visual scale, content width, responsive
tables/code blocks, and the absence of zoom/transform/viewport hacks or external
assets. They confirm source-aware security wording, no synthesized
`/help/5094126` fallback, and no raw Support HTML leakage.

## Release Gate Result

Local `0.3.4` gates passed compileall, identity/version/action audits, and the
targeted plus full pytest suites with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. The
tagged release lane runs the full deployment gate; this release is prepared but
not yet published.

## Packaging And PyPI

| Item | State |
| --- | --- |
| PyPI project | [win11_release_guard](https://pypi.org/project/win11-release-guard/) |
| End-user install | `python -m pip install win11_release_guard` |
| Package metadata | `pyproject.toml` defines `win11_release_guard` version `0.3.4`, GPL-3.0-only license, console script, project URLs, and package data. |
| Build artifacts | wheel and sdist are generated in `dist/`, checked with `python -m twine check dist/*`, and never committed. |
| Publishing | `.github/workflows/pypi-publish.yml` uses PyPI Trusted Publishing / GitHub OIDC with environment `pypi`. |
| First publish | Pending Trusted Publisher setup is required if the project is absent; a PyPI 404 is not a name reservation. |

## Signed Policy Note

The local version bump does not regenerate the signed bundled production policy
or detached signature. Release packaging and Pages publishing must use the
existing secure signing workflow with the real policy signing key.

## Unchanged Boundaries

| Boundary | Rule |
| --- | --- |
| Verdict | Signed public policy remains the authority. |
| WUA | Optional read-only secondary probe; never decides the policy verdict. |
| Panther/setup logs | Administrator troubleshooting evidence only. |
| Source Diagnostics | Source-health evidence only; notices are dashboard-only and not issue-syncable. |
| Baseline notice | Informational dashboard output only, visible for 14 days. |
| 26H1 | New-devices-only / excluded for existing devices. |
| `/api/v1` | Existing public aliases remain compatible. |

## Verify Commands

```powershell
python -m compileall -q win11_release_guard tools tests
python tools/check_version_consistency.py
python tools/check_project_identity.py
python tools/check_github_action_versions.py
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; python -m pytest -q
python -m win11_release_guard --self-test
python tools/scan_for_secret_material.py README.md CHANGELOG.md AGENTS.md docs wiki win11_release_guard tests tools pyproject.toml .github
python tools/export_clean_archive.py --output dist/win11_release_guard-source.zip
python tools/export_clean_archive.py --validate dist/win11_release_guard-source.zip
python -m build
python -m twine check dist/*
```

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

## Related Pages

[Home](Home) | [Architecture](Architecture) | [Policy Feed and Trust Model](Policy-Feed-and-Trust-Model) | [Source Diagnostics](Source-Diagnostics) | [Tagged Release Lane](Tagged-Release-Lane) | [Build, Test and Release](Build-Test-and-Release)

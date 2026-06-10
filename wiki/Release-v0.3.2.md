# Release v0.3.2

Compact human summary of the `0.3.2` compatibility and documentation-alignment release. Code, tests, workflows, `pyproject.toml`, README, docs, local wiki source, and `AGENTS.md` remain source truth.

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

| Area | 0.3.2 state |
| --- | --- |
| Versioning | Package/runtime/generator/WUA identity is centralized at `win11_release_guard/0.3.2`. |
| Python support | Package metadata declares Python 3.10, 3.11, 3.12, 3.13, and 3.14. |
| CI | Ubuntu and Windows matrix covers Python 3.10 through 3.14 without allowed-failure jobs. |
| Packaging | Runtime dependency remains `cryptography>=41`; test/tooling extras add `tomli` only for Python before 3.11. |
| Trust | Runtime uses public policy JSON plus detached Ed25519 signature; clients do not authenticate to GitHub. |
| Dashboard | Static Pages shows trust, Source Diagnostics filters, target builds, feed currency, optional static issue links for real warning/error events, and API links. |
| Source Diagnostics | Source-health evidence only; no event changes device compliance verdicts. |
| PyPI lane | `pypi-publish.yml` builds wheel/sdist and publishes through Trusted Publishing / GitHub OIDC only after tag or published-release gates. |

## Compatibility

CI is the active interpreter compatibility gate:

- `ubuntu-latest`: Python 3.10, 3.11, 3.12, 3.13, and 3.14.
- `windows-latest`: Python 3.10, 3.11, 3.12, 3.13, and 3.14.

Release, Pages, PyPI, dependency, and Wiki workflows keep Python 3.12 as their automation toolchain. The package artifacts are universal wheel/sdist outputs; interpreter compatibility is covered by CI and package metadata.

## Source Diagnostics

Source Diagnostics are source-health evidence, not compliance verdict authority. Release Health and Atom/Update History can be temporarily out of step. Preview, OOB, non-broad-target, unknown-family, and missing-KB Atom drift stays `notice` until reliable required-baseline evidence exists. Non-preview broad-target drift with an extracted KB and matching build/release evidence can be `warning`; notice-only drift does not trigger `source_drift_unresolved_after_24h`.

GitHub Issue sync remains workflow-only with `github.token` / `GITHUB_TOKEN`. It tracks real warning/error `source_diagnostics.events` only. Browser JavaScript renders static issue metadata and never writes to GitHub.

## Packaging And PyPI

| Item | State |
| --- | --- |
| PyPI project | [win11_release_guard](https://pypi.org/project/win11-release-guard/) |
| End-user install | `python -m pip install win11_release_guard` |
| Package metadata | `pyproject.toml` defines `win11_release_guard` version `0.3.2`, GPL-3.0-only license, console script, project URLs, and package data. |
| Build artifacts | Wheel and sdist are generated in `dist/`, checked with `python -m twine check dist/*`, and never committed. |
| Publishing | `.github/workflows/pypi-publish.yml` uses PyPI Trusted Publishing / GitHub OIDC with environment `pypi`. |
| First publish | Pending Trusted Publisher setup is required if the project is absent; a PyPI 404 is not a name reservation. |

## Unchanged Boundaries

| Boundary | Rule |
| --- | --- |
| Verdict | Signed public policy remains the authority. |
| WUA | Optional read-only secondary probe; never decides the policy verdict. |
| Panther/setup logs | Administrator troubleshooting evidence only. |
| 26H1 | New-devices-only / excluded for existing devices. |
| `/api/v1` | Existing public aliases remain compatible. |

## Verify Commands

```powershell
python -m compileall -q win11_release_guard tools tests
python tools/check_version_consistency.py
python tools/check_project_identity.py
python tools/check_github_action_versions.py
pytest -q
python -m win11_release_guard --self-test
python tools/scan_for_secret_material.py README.md CHANGELOG.md AGENTS.md docs wiki win11_release_guard tests tools pyproject.toml .github
python -m build
python -m twine check dist/*
```

## Related Pages

[Home](Home) | [Architecture](Architecture) | [Policy Feed and Trust Model](Policy-Feed-and-Trust-Model) | [Source Diagnostics](Source-Diagnostics) | [Tagged Release Lane](Tagged-Release-Lane) | [Build, Test and Release](Build-Test-and-Release)

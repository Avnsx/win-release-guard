# Release v0.3.1

Compact human summary of the `0.3.1` hardening and packaging release. Code, tests, workflows, `pyproject.toml`, README, docs, local wiki source, and `AGENTS.md` remain source truth.

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

| Area | 0.3.1 state |
| --- | --- |
| Versioning | Package/runtime/generator/WUA identity is centralized at `win11_release_guard/0.3.1`. |
| Packaging | `pyproject.toml` defines GPL-3.0-only metadata, `LICENSE.txt`, project URLs, console script, dependencies, test extras, and package data. |
| Trust | Runtime uses public policy JSON plus detached Ed25519 signature; clients do not authenticate to GitHub. |
| Freshness | Manifest/dashboard carry epoch freshness fields; browser age uses `Date.now()` and CLI checks enforce 14/45-day gates. |
| Dashboard | Static Pages shows trust, Source Diagnostics filters, target builds, feed currency, optional static issue links, and API links. |
| JSON hardening | Strict JSON rejects duplicate keys, non-finite numbers, invalid UTF-8, wrong object top-level shape, and oversized payloads. |
| Local truth | Build evidence beats `ProductName`, WMI `Caption`, and `DisplayVersion`; those values remain raw diagnostics. |
| Local diagnostic output | Default JSON compacts bulky Panther/setup log tails; `--include-raw-local-diagnostics` restores raw bounded local log tails; Panther reads use fixed known paths, 5 MiB per-file tails, and a generous 512 MiB total guard. |
| WUA | Optional read-only secondary probe; never decides the policy verdict. |
| Panther/setup logs | Administrator troubleshooting evidence only; never overrides signed public policy; collection is narrow, tail-bounded, and globally guarded. |
| Release lane | `release.yml` validates `vX.Y.Z` tag/version parity, links changelog/release notes/Pages Wiki/changelog/feed in the release body, and attaches only a validated clean source archive. |
| PyPI lane | `pypi-publish.yml` builds wheel/sdist and publishes through Trusted Publishing / GitHub OIDC only after tag or published-release gates. |

## Packaging And PyPI

| Item | State |
| --- | --- |
| PyPI project | [win11_release_guard](https://pypi.org/project/win11_release_guard/) |
| End-user install | `python -m pip install win11_release_guard` |
| Package metadata | `pyproject.toml` defines `win11_release_guard` version `0.3.1`, GPL-3.0-only license, console script, project URLs, and package data. |
| Build artifacts | Wheel and sdist are generated in `dist/`, checked with `python -m twine check dist/*`, and never committed. |
| Publishing | `.github/workflows/pypi-publish.yml` uses PyPI Trusted Publishing / GitHub OIDC with environment `pypi`. |
| First publish | Pending Trusted Publisher setup is required if the project is absent; a PyPI 404 is not a name reservation. |

## What Changed By Area

| Area | Files / functions |
| --- | --- |
| Versioning | `version.py`, `package_version()`, `runtime_user_agent()`, `generator_version()`, `client_application_id()`, `tools/check_version_consistency.py` |
| Policy feed | `ReleasePolicy`, `ReleasePolicyEntry`, `generate_policy()`, `render_policy_manifest()` |
| Pages dashboard | `render_policy_index()`, `_render_source_diagnostics_panel()`, `_safe_json_script_payload()` |
| Freshness | `freshness.py`, `freshness_policy_metadata()`, `freshness_thresholds()`, `_public_pages_freshness_check()` |
| Runtime loading | `check_current_system()`, `_load_runtime_policy()`, `_load_cache_policy()`, `decide_source_degradation()` |
| Local detection | `get_local_windows_state()`, `derive_local_consensus()`, `evaluate_windows_update_state()`, `query_wua_secondary()` |
| Local diagnostic output | `--include-raw-local-diagnostics`, compact markers such as `content_omitted`, `content_chars`, and `content_bytes_utf8` |
| JSON/signature/cache | `strict_json_loads()`, `strict_json_object()`, `verify_policy_signature()`, `load_trusted_policy()` |
| Workflows | `publish-policy.yml`, `sync-wiki.yml`, `release.yml`, `pypi-publish.yml`, `ci.yml`, action/dependency workflows |
| PyPI publishing | Project `win11_release_guard`, owner `Avnsx`, repository `win11_release_guard`, workflow `pypi-publish.yml`, environment `pypi`, no PyPI token |
| Documentation | `README.md`, `CHANGELOG.md`, `docs/releases/v0.3.1.md`, `docs/`, `wiki/` |

## PyPI Lane

| Check | Rule |
| --- | --- |
| Manual without tag | Build/test/scan/build distributions/Twine check only; publish job is skipped. |
| Manual with tag | Tag must already exist, match `vX.Y.Z`, and match `pyproject.toml` version. |
| Published GitHub Release | Triggers the separate PyPI workflow from the release tag. |
| Package name | Must be `win11_release_guard`. |
| Artifact path | Workflow-generated `dist/`, uploaded/downloaded between jobs. |
| Publish job | GitHub Environment `pypi`; `id-token: write` only in that job. |
| Credentials | No PyPI API token, Twine password, username, or credentialed repository URL. |

## Pages And Wiki

| Topic | Rule |
| --- | --- |
| Local `site/` | Generated output only; do not commit. |
| Pages refresh | `.github/workflows/publish-policy.yml` regenerates and deploys Pages; `workflow_dispatch` can refresh manually. |
| Wiki changes | Pages rebuild because `wiki/*.md` renders to `site/wiki/`. |
| Changelog changes | Pages rebuild because `CHANGELOG.md` renders to `site/wiki/changelog/`. |
| Pages renderer | First-party Python escapes raw HTML, converts GitHub Wiki links, warns on broken or missing Wiki inputs, and may add local-only inline SVG topic icons without changing Markdown source. |
| Docs-only changes | No Pages rebuild unless dashboard-rendered content, generated metadata, public URLs, or workflow path filters change. |
| Local `wiki/` | Source for the static Pages Wiki and source/staging for the live GitHub internal Wiki. |
| Live wiki | `.github/workflows/sync-wiki.yml` can mirror `wiki/*.md` with the built-in Actions token or produce a dry-run artifact for manual fallback. |
| Changelog history | Newer entries are added at the top; older version sections stay visible for Pages changelog, release history, SEO, and auditability. |

## Verify Commands

```powershell
python -m compileall -q win11_release_guard tools tests
python tools/check_version_consistency.py
python tools/check_project_identity.py
python tools/check_github_action_versions.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_pypi_publish_workflow.py tests/test_repository_automation.py tests/test_agents_contract.py tests/test_branding_contract.py tests/test_project_identity.py tests/test_import_contract.py -k "pypi or release or changelog or docs or wiki or readme or version or workflow"
python tools/scan_for_secret_material.py README.md CHANGELOG.md AGENTS.md docs wiki win11_release_guard tests tools pyproject.toml .github
python -m build
python -m twine check dist/*
```

## Common Mistakes

| Mistake | Correct behavior |
| --- | --- |
| Treat `schema_version` or `api_version` as the package version. | Use `pyproject.toml` and `package_version()` for program version. |
| Treat `ProductName` or WMI `Caption` as OS authority. | Use build-first evidence and signed policy mapping. |
| Let WUA offers override the policy target. | Keep WUA optional, read-only, and diagnostic. |
| Target existing devices at 26H1. | Keep 26H1 new-devices-only / excluded for existing devices. |
| Commit local `site/` or `dist/`. | Regenerate those as workflow/local build output only. |
| Publish raw worktree ZIPs. | Use `tools/export_clean_archive.py` and validate the archive. |
| Add PyPI credentials to Actions. | Use Trusted Publishing with GitHub OIDC. |
| Create GitHub Issues from dashboard JavaScript. | Keep issue sync workflow-side with the built-in Actions token and static dashboard links only. |
| Assume the Pages publish job also updates the GitHub internal Wiki. | Use the separate `sync-wiki.yml` workflow or its dry-run artifact fallback. |

## Related Pages

[Home](Home) | [Architecture](Architecture) | [Policy Feed and Trust Model](Policy-Feed-and-Trust-Model) | [Anti-Static Freshness](Anti-Static-Freshness) | [Tagged Release Lane](Tagged-Release-Lane) | [Build, Test and Release](Build-Test-and-Release)

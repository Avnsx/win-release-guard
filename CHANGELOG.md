# Changelog

## [Unreleased]

### Added

* GitHub internal Wiki sync workflow and first-party `tools/sync_github_wiki.py` helper for mirroring `wiki/*.md` source Markdown to the same repository's `.wiki.git` remote with the built-in Actions token, plus dry-run Markdown artifact fallback.
* First-party static Pages changelog generation from `CHANGELOG.md`, including `/wiki/changelog/`, per-version Pages routes, version sidebar links, GitHub Release links, sitemap entries, and no external JS/CSS/CDN dependencies.

### Changed

* `publish-policy.yml` now avoids tag-triggered Pages deploys because the protected `github-pages` environment rejects tag-sourced deployments; release tags rely on the main Pages publish lane or manual `workflow_dispatch` from `main`.
* `release.yml` now checks for matching `CHANGELOG.md`, `docs/releases/vX.Y.Z.md`, and `wiki/Release-vX.Y.Z.md` release material, and links Pages Wiki/changelog routes in GitHub Release notes.

### Documentation

* Documented that `sync-wiki.yml` is the only non-release workflow allowed to request `contents: write`, scoped only to GitHub internal Wiki Markdown sync.
* Added the AGENTS.md rule that future agents must keep historical `CHANGELOG.md` version sections and add newer entries at the top.

## v0.3.1 - 2026-06-05

### Summary

Version 0.3.1 documents and hardens the current `win11_release_guard` worktree: package/runtime version identity, signed public policy feed handling, static GitHub Pages output, strict JSON trust boundaries, tagged source releases, and the PyPI Trusted Publishing lane. Windows release semantics are unchanged: existing broad-fleet devices target Windows 11 `25H2`; `26H1` remains excluded for existing-device targeting; local build evidence outranks display labels; WUA remains optional secondary evidence; policy `schema_version` and public `api_version` are not program versions.

Comparison basis: no local `v*` tags are present in this checkout. These notes are based on the current worktree at `main` `56915c9` plus uncommitted worktree files, not on earlier handover text or old release-note drafts.

### Added

* Central version helpers in `win11_release_guard/version.py`: `package_version()`, `versioned_product_id()`, `runtime_user_agent()`, `generator_version()`, and `client_application_id()`.
* Static feed freshness helpers in `win11_release_guard/freshness.py` for UTC parsing, epoch timestamps, 14-day warning metadata, and 45-day strict-stale metadata.
* Tagged GitHub Release workflow in `.github/workflows/release.yml` for `vX.Y.Z` tag validation, version parity, tests, live checks, dependency freshness, clean archive creation, and draft release publication.
* PyPI Trusted Publishing workflow in `.github/workflows/pypi-publish.yml` with build-only manual dispatch, existing-tag publish, published GitHub Release publish, package name and tag/version checks, wheel/sdist build, Twine check, dist artifact handoff, GitHub Environment `pypi`, and OIDC publishing.
* Local `wiki/` source tree and `docs/releases/v0.3.1.md` release notes for staged GitHub Wiki, rendered Pages Wiki, and maintainer documentation.
* GPL-3.0-only packaging metadata and `LICENSE.txt` inclusion in validated clean archives.
* Panther JSON support tooling: a Windows live regression harness, a developer leak debugger, and a dedicated `docs/panther-support.md` implementation/operations guide.

### Changed

* Program/package version is `0.3.1` in `pyproject.toml`; runtime user-agent, generator identity, and WUA client application ID derive from the shared version helper.
* `ReleasePolicyEntry` rendering keeps `latest_observed_build` separate from `required_baseline_build`, so preview/current-table observations do not become mandatory B-release compliance floors.
* The static Pages dashboard now exposes program version, release link, public endpoint links, source tiles, Source Diagnostics severity filters, feed currency, target build details, optional static issue links, and signature/hash state.
* `wiki/*.md` now renders into a first-party static Pages Wiki under `site/wiki/` without changing GitHub internal Wiki Markdown compatibility.
* `render_policy_manifest()` carries manifest/API metadata, freshness epochs, source diagnostics, hashes, published URLs, and broad-target build fields used by public checks.
* `publish-policy.yml` path filters include `pyproject.toml`, version/identity tools, secret scanning, generator inputs, `win11_release_guard/**`, and `wiki/**` because generated Pages output includes program metadata, runtime policy artifacts, and rendered Wiki HTML.

### Fixed

* Build-first local truth is preserved through `get_local_windows_state()`, `derive_local_consensus()`, `evaluate_windows_update_state()`, and `check_current_system()`: `ProductName`, WMI `Caption`, and `DisplayVersion` remain diagnostics.
* `query_wua_secondary()` remains read-only and secondary; WUA offers/history can explain behavior but never override the signed policy verdict.
* Strict-production mode returns production-green only from fresh live signed remote JSON. Cache and bundled fallback remain visible degraded evidence.
* Public Pages checks validate policy/signature/manifest/API aliases and fail stale feed timestamps instead of treating HTTP reachability as enough.

### Hardened

* `win11_release_guard/json_utils.py` rejects duplicate JSON keys, non-finite numbers, invalid UTF-8, wrong object top-level shapes where objects are required, and oversized trust-boundary payloads.
* Strict JSON and byte caps are applied to policy JSON, manifest JSON, signature JSON, trusted public-key JSON, cache JSON, public endpoint checks, and Microsoft source payload reads.
* Default JSON output compacts bulky local Panther/setup log tails; raw bounded local diagnostics remain available with `--include-raw-local-diagnostics`.
* The live Panther JSON harness treats missing readable Panther/setup sources as a normal clean-machine pass condition and reports `no_panther_source_present` instead of requiring an affected machine.
* Panther/setup logs remain administrator troubleshooting evidence only; they do not decide compliance or override signed public policy.
* Ed25519 verification and key-rotation windows remain enforced in `win11_release_guard/signing.py`; retired or retiring keys need bounded `verify_not_after_utc`.
* Source Diagnostics validation is structured across generator, schema, dashboard, CLI checks, GitHub Actions issue sync, and the publish workflow; `severity: error` blocks Pages publishing while issue state remains diagnostic.
* Panther/setup collection uses bounded, encoding-aware tail reads across current, UnattendGC, NewOS, `$Windows.~BT`, and rollback locations, with per-path read-error isolation and a deliberately generous global collection cap.
* Panther privacy diagnostics report category, finding type, marker, path, line number, line length, safe hint, count, truncation, and notice metadata only; matched password/token/key/secret values are not copied into privacy findings.

### Documentation

* Rebuilt root release documentation around current code, tests, workflows, `pyproject.toml`, README, docs, and local wiki source.
* Documented the v0.3.1 state that local `wiki/` is source for rendered Pages Wiki HTML and required a separate live GitHub internal Wiki sync at that time.
* Documented that local `site/` is generated output; Pages is regenerated by `.github/workflows/publish-policy.yml` and can be refreshed manually with workflow_dispatch.
* Clarified that wiki changes require a Pages rebuild because they render to `site/wiki/`; docs-only changes still require a rebuild only when they affect dashboard-rendered content, generated metadata, public URLs, or workflow path filters.
* Added `docs/panther-support.md` to describe Panther entry points, supported paths, default/opt-in JSON behavior, privacy notices, useful troubleshooting scenarios, limits, and safe extension rules.

### Workflows

* `.github/workflows/release.yml` requests `contents: write` only for explicit GitHub Release publication; `.github/workflows/sync-wiki.yml` requests it only for GitHub internal Wiki Markdown sync from `wiki/*.md`.
* GitHub Release bodies link the root changelog, detailed `docs/releases/vX.Y.Z.md` notes, Pages dashboard, Pages Wiki/changelog routes, public feed, GitHub internal Wiki sync lane, and the separate PyPI Trusted Publishing lane.
* `.github/workflows/publish-policy.yml` uses `contents: read`, `pages: write`, and `id-token: write`; it generates signed static Pages artifacts, scans them, uploads a Pages artifact, deploys Pages, and runs post-deploy live verification.
* `.github/workflows/pypi-publish.yml` uses `contents: read` globally and `id-token: write` only in `publish-to-pypi`.
* `tools/check_github_action_versions.py` allows `pypa/gh-action-pypi-publish` only in `pypi-publish.yml`, pinned to `cef221092ed1bacb1cc03d23a2d87d1d172e277b`.

### Packaging And PyPI

* `pyproject.toml` package name is `win11_release_guard`, version is `0.3.1`, readme is `README.md`, license is `GPL-3.0-only`, license file is `LICENSE.txt`, author metadata is `Mikail ("Avnsx") C.`, runtime dependency is `cryptography>=41`, and test extras are `packaging>=24` plus `pytest>=8`.
* PyPI project URL is `https://pypi.org/project/win11_release_guard/`; end users install released packages with `python -m pip install win11_release_guard`.
* Console script remains `win11_release_guard = "win11_release_guard.__main__:main"`.
* Package data includes `win11_release_guard/data/*.json` and `win11_release_guard/data/*.sig`.
* Project URLs cover Homepage, Repository, Documentation, Changelog, Bug Tracker, Public Feed, and Pages Dashboard.
* `.github/workflows/pypi-publish.yml` builds wheel and sdist artifacts in generated `dist/`, uploads/downloads that workflow artifact between jobs, and runs `python -m twine check dist/*` before publication.
* PyPI publishing is Trusted Publishing / GitHub OIDC only: project `win11_release_guard`, owner `Avnsx`.
* First publish requires PyPI Pending Trusted Publisher setup if the project is not already live; TestPyPI is not implemented in the current workflow.

### Tests

* Added or updated tests for PyPI publishing workflow guarantees, action pinning, project/package identity, version consistency, clean archive contents, release workflow gates, publish-policy path filters, no-secret scanning, and documentation contracts.
* Prompt-specific verification commands and results are reported in the final task handoff; release notes avoid claiming live or destructive validation that was not rerun in the current context.

# Handover Prompt 21

Node.js 24 workflow migration audit for `win-release-guard`, completed on
2026-05-31.

## Summary

- Migrated first-party GitHub Actions to Node.js 24-ready majors.
- Added `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to every workflow that uses
  JavaScript actions.
- Did not add the insecure Node.js opt-out.
- Kept `github/codeql-action` at v4 after inspecting tags; current tags showed
  v4 as the latest supported major.
- Publish policy workflow still uses same-repo Pages artifact deployment.
- Live CI, publish, CodeQL, Pylint, dependency audit, and dependency freshness
  workflows all succeeded after the migration.
- Workflow logs were checked for the old Node.js 20 deprecation warning; none
  of the required runs contained it.

## Files Changed

- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/dependency-audit.yml`
- `.github/workflows/dependency-freshness.yml`
- `.github/workflows/publish-policy.yml`
- `.github/workflows/pylint.yml`
- `tests/test_publish_policy_workflow.py`
- `tests/test_repository_automation.py`
- `tests/test_workflow_node24.py`
- `docs/handover-prompt21.md`

## Action Versions

- `actions/checkout@v6`
- `actions/setup-python@v6`
- `actions/configure-pages@v6`
- `actions/upload-pages-artifact@v5`
- `actions/deploy-pages@v5`
- `github/codeql-action/init@v4`
- `github/codeql-action/analyze@v4`

## Local Commands Run

- Node.js 24 migration reference search across `.github`, tests, README,
  AGENTS, and docs
- `gh api repos/actions/checkout/releases/latest --jq .tag_name`
- `gh api repos/actions/setup-python/releases/latest --jq .tag_name`
- `gh api repos/actions/configure-pages/releases/latest --jq .tag_name`
- `gh api repos/actions/upload-pages-artifact/releases/latest --jq .tag_name`
- `gh api repos/actions/deploy-pages/releases/latest --jq .tag_name`
- `gh api repos/github/codeql-action/tags --paginate --jq '.[].name'`
- `python -m compileall -q win11_release_guard tools`
- `pytest -q`
- `python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github`
- `python tools/export_clean_archive.py`
- stale Node.js 20 action reference scan across `.github`, tests, README, AGENTS, and docs
- fixture policy generation with a temporary ignored signing-test key
- `python -m win11_release_guard --check-policy-source`
- `python -m win11_release_guard --check-public-pages`
- workflow log scan for Node.js 20 deprecation warnings

## Local Results

- Compileall: passed.
- Full pytest: `268 passed`.
- Secret material scan: passed.
- Clean archive: passed; `78` entries.
- Stale first-party action refs: no matches.
- Insecure Node.js opt-out: no matches.
- Mandatory live Pages gate: passed.
- Temporary local signing-test private key was removed after fixture generation.

## Live Workflow Results

Commit: `3333966 Migrate GitHub Actions workflows to Node 24`

- CI: success
  - `https://github.com/Avnsx/win-release-guard/actions/runs/26722238748`
- Publish policy: success
  - `https://github.com/Avnsx/win-release-guard/actions/runs/26722238754`
- CodeQL: success
  - `https://github.com/Avnsx/win-release-guard/actions/runs/26722238759`
- Pylint: success
  - `https://github.com/Avnsx/win-release-guard/actions/runs/26722238767`
- Dependency audit: success
  - `https://github.com/Avnsx/win-release-guard/actions/runs/26722238747`
- Dependency freshness: success
  - `https://github.com/Avnsx/win-release-guard/actions/runs/26722238757`

Workflow logs for these runs did not contain the previous Node.js 20
deprecation warning.

## Live Pages Result

- `python -m win11_release_guard --check-policy-source`: passed.
- `python -m win11_release_guard --check-public-pages`: passed.
- Published policy generated at: `2026-05-31T19:28:27+00:00`.
- Manifest hash matched policy bytes.
- Landing, policy, signature, manifest, API aliases, robots, and sitemap all
  returned HTTP 200.

## Remaining Risks

- CodeQL is still on major v4 because no v5 major tag was found during the
  audit. Re-check when GitHub releases a new CodeQL action major.
- Future GitHub action major releases may require another compatibility audit.
- `docs/handover-prompt20.md` was already deleted in the working tree before
  this migration and was not restored or committed as part of this task.

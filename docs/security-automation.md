# Security Automation

Purpose: document repository automation that protects public feed generation, release publication, dependency posture, and GitHub Actions execution.

Related links: [docs index](README.md) | [docs/tagged-release-lane.md](tagged-release-lane.md) | [wiki build/test/release](../wiki/Build-Test-and-Release.md) | [wiki tagged release lane](../wiki/Tagged-Release-Lane.md)

## Automation Configuration Files

| File | Purpose |
| --- | --- |
| `.github/dependabot.yml` | Keeps GitHub Actions and Python dependency update signals visible. |
| `.github/workflows/codeql.yml` | Runs CodeQL code scanning for the Python source tree. |
| `tools/check_github_action_versions.py` | Enforces the audited Actions allowlist and pinning rules. |

Enable or verify CodeQL in repository settings via Settings -> Code security and analysis -> Code scanning. GitHub UI settings are not fully controlled by repository files. Treat workflow status badges as public status links, not as complete security or freshness guarantees.

## Workflow Map

| Workflow | Trigger | Role |
| --- | --- | --- |
| `ci.yml` | push / pull request | Compile, audit actions, check identity, run tests, generate fixture policy, scan, export archive. |
| `publish-policy.yml` | schedule / `workflow_dispatch` / selected pushes | Generate signed Pages feed and deploy static Pages artifact. |
| `release.yml` | tags / `workflow_dispatch` | Validate version/tag parity and publish clean source archive as GitHub Release asset. |
| `codeql.yml` | schedule / push / PR | CodeQL scan. |
| `dependency-audit.yml` | schedule / `workflow_dispatch` | `pip-audit` dependency vulnerability check. |
| `dependency-freshness.yml` | schedule / `workflow_dispatch` | Direct dependency freshness summary. |
| `pylint.yml` | push / PR | Pylint quality gate. |

## Permissions

| Lane | Required permission |
| --- | --- |
| CI / checks | Read-only repository access. |
| Pages publish | `contents: read`, `pages: write`, `id-token: write`. |
| Tagged releases | `contents: write` only in `release.yml`. |

Production Pages publishing must not use PATs, branch pushes, or `gh-pages` branch deployment.

## GitHub Actions Pinning

| Rule | Enforcement |
| --- | --- |
| GitHub-owned first-party actions may use audited major tags. | `tools/check_github_action_versions.py` |
| Third-party actions are forbidden unless explicitly allowlisted. | Audit tool plus tests. |
| Allowlisted third-party actions must use a full 40-character commit SHA. | Audit tool plus tests. |
| JavaScript actions opt into Node 24. | Workflow env and tests. |

## Source Diagnostics Gate

`publish-policy.yml` blocks deployment when generated `source_diagnostics.events` contains `severity: error`. These are source-diagnostics `error` events; notice and warning events remain visible diagnostic output.

README badges show latest workflow status only. The schedule is not the only control: workflow dispatch, source diagnostics, signature checks, public Pages checks, and live verification gates are the operational controls.

## Do / Do Not

| Do | Do not |
| --- | --- |
| Keep workflow permissions minimal. | Add `contents: write` outside the tagged release workflow. |
| Keep signed feed generation public-source only. | Add token-authenticated Microsoft API requirements to production generator. |
| Scan generated Pages output before upload. | Publish stale or unsigned artifacts silently. |
| Treat scheduled runs as best-effort. | Present schedules as guaranteed timing. |

## Verify

```powershell
python tools/check_github_action_versions.py
python tools/check_project_identity.py
python tools/check_version_consistency.py
python -m win11_release_guard --check-policy-source
python -m win11_release_guard --check-public-pages
pytest -q tests/test_repository_automation.py tests/test_publish_policy_workflow.py tests/test_workflow_node24.py
```

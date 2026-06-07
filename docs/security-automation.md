# Security Automation

Purpose: document repository automation that protects public feed generation, release publication, dependency posture, and GitHub Actions execution.

Related links: [maintainer guide](maintainer-guide.md) | [docs/tagged-release-lane.md](tagged-release-lane.md) | [wiki build/test/release](../wiki/Build-Test-and-Release.md) | [wiki tagged release lane](../wiki/Tagged-Release-Lane.md)

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
| `sync-source-diagnostics-issues.yml` | `workflow_dispatch` | Sync source-diagnostic notice/warning/error events to GitHub Issues using only the built-in Actions token. |
| `release.yml` | tags / `workflow_dispatch` | Validate version/tag parity and publish clean source archive as GitHub Release asset. |
| `pypi-publish.yml` | `workflow_dispatch` / published GitHub Release | Build wheel/sdist on manual runs; publish to PyPI through Trusted Publishing / GitHub OIDC only from an existing tag or published release. |
| `codeql.yml` | schedule / push / PR | CodeQL scan. |
| `dependency-audit.yml` | schedule / `workflow_dispatch` | `pip-audit` dependency vulnerability check. |
| `dependency-freshness.yml` | schedule / `workflow_dispatch` | Direct dependency freshness summary. |
| `pylint.yml` | push / PR | Pylint quality gate. |

## Permissions

| Lane | Required permission |
| --- | --- |
| CI / checks | Read-only repository access. |
| Pages publish | `contents: read`, `pages: write`, `id-token: write`. |
| Source diagnostics issue sync | `contents: read`, `issues: write`; uses `GITHUB_TOKEN` / `${{ github.token }}` only. |
| Tagged releases | `contents: write` only in `release.yml`. |
| PyPI publish | `id-token: write` only in the `publish-to-pypi` job; no PyPI API token. |

Production Pages publishing must not use PATs, branch pushes, or `gh-pages` branch deployment.

## GitHub Actions Pinning

| Rule | Enforcement |
| --- | --- |
| GitHub-owned first-party actions may use audited major tags. | `tools/check_github_action_versions.py` |
| Third-party actions are forbidden unless explicitly allowlisted. | Audit tool plus tests. |
| Allowlisted third-party actions must use a full 40-character commit SHA. | Audit tool plus tests. |
| `pypa/gh-action-pypi-publish` is allowed only in `pypi-publish.yml`, pinned to `cef221092ed1bacb1cc03d23a2d87d1d172e277b`. | Narrow Trusted Publishing exception; no stored PyPI credentials. |
| JavaScript actions opt into Node 24. | Workflow env and tests. |

## PyPI Trusted Publishing

| Field | Value |
| --- | --- |
| PyPI project name | Derived from `pyproject.toml` `[project].name`: `win11_release_guard` |
| PyPI project URL | `https://pypi.org/project/win11_release_guard/` |
| Owner | `Avnsx` |
| Repository | `win11_release_guard` |
| Workflow | `pypi-publish.yml` |
| Environment | `pypi` |

PyPI and GitHub exchange a short-lived OIDC publishing identity during the workflow run. Artifact transfer is workflow-initiated: the workflow builds generated wheel/sdist files in `dist/`, checks them with Twine, uploads the artifact between jobs, and actively publishes it only after an existing tag is checked out and the `pypi` environment gate approves. Manual dispatch without a tag is build-only. If the PyPI project does not exist yet, configure a Pending Trusted Publisher first; that does not reserve the name. Do not add workflow YAML that asks maintainers to paste publishing tokens, usernames, passwords, or credentialed repository URLs.

No TestPyPI lane is currently implemented. If one is added later, use a separate TestPyPI Trusted Publisher and a separate GitHub Environment such as `testpypi`.

## Source Diagnostics Gate

`publish-policy.yml` blocks deployment when generated `source_diagnostics.events` contains `severity: error`. These are source-diagnostics `error` events; notice and warning events remain visible diagnostic output.

`sync-source-diagnostics-issues.yml` and the `publish-policy.yml`
`sync-source-diagnostics-issues` job use `issues: write` only for workflow-side
GitHub Issues synchronization. The deployment job does not receive issue-write
permission. The sync reads only real `source_diagnostics.events` entries,
deduplicates by the deterministic source diagnostic ID, stores the ID in the
issue body as
`<!-- wrg-source-diagnostic-id: ... -->`, and caps new issues per run. Notices,
warnings, and errors from that event list are synced by default. Derived
dashboard-only rows such as `No source issues reported`, existing-device
exclusion notes, and freshness notices are not issue-sync inputs. Matching open
issues are left untouched when their title, body, and labels already match the
current diagnostic. Changed open issues are patched without a recurring
still-present comment. Matching closed issues are reopened with a comment while
the diagnostic is still present, and open managed issues are closed with a
comment when their diagnostic ID disappears from the current policy.
Before creating a new issue, the sync checks both GitHub Search results for the
diagnostic ID and open issues carrying the managed internals labels. Every
candidate is accepted only after the exact internal body marker matches the
current diagnostic ID, so labels alone still cannot block or trigger mutation.

Severity labels are fixed as `internals: notices`, `internals: warning`, and
`internals: error`. Labels help filtering in GitHub, but they are not sufficient
to mark an issue as managed without the internal body marker.

During `publish-policy.yml`, GitHub Issues API, label, or permission failures in
the issue-sync mutation step are degraded rather than publish-blocking. The
workflow writes static `source_diagnostics.issue_sync.status: unavailable`
metadata into the issue-status artifact, and the signed policy, manifest, and
dashboard expose that degraded state. Generator source-diagnostic `error` events
still block publication in the build validation step.

Source diagnostic IDs are based on stable event identity fields: severity,
source, event kind/category, release, build family, build, KB article, affected
target flags, and source URL host/path when available. Generated/fetched
timestamps, exact message wording, tag order, and display-only prose are
excluded from the normal ID basis to avoid duplicate issue churn.

An issue is considered managed only when its body contains exactly one internal
HTML comment marker of the form
`<!-- wrg-source-diagnostic-id: wrg-source-diagnostic-v1:<hash> -->`. Labels,
titles, or plain-text diagnostic ID mentions are not enough for the sync to
update, comment, reopen, or close an issue.

The standalone `sync-source-diagnostics-issues.yml` workflow supports manual
dry-runs. In dry-run mode the tool does not create, update, comment, reopen, or
close issues, and can write JSON or Markdown reports with deterministic IDs,
labels, planned actions, and static issue-status metadata. The workflow uploads
a Markdown dry-run artifact without adding any secret beyond the built-in
`GITHUB_TOKEN`.

The dashboard renders issue links only from static generated
`source_diagnostics.issue_status` metadata. Browser JavaScript must not query the
GitHub Issues API, expose workflow logs, or embed tokens.

README badges show latest workflow status only. The schedule is not the only control: workflow dispatch, source diagnostics, signature checks, public Pages checks, and live verification gates are the operational controls.

## Do / Do Not

| Do | Do not |
| --- | --- |
| Keep workflow permissions minimal. | Add `contents: write` outside the tagged release workflow. |
| Keep GitHub Issues sync in Actions with the built-in token. | Add issue creation calls, tokens, or GitHub API writes to client-side Pages JavaScript. |
| Keep signed feed generation public-source only. | Add token-authenticated Microsoft API requirements to production generator. |
| Keep PyPI publishing on Trusted Publishing / OIDC. | Add PyPI API tokens, Twine passwords, usernames, or credentialed repository URLs. |
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
pytest -q tests/test_pypi_publish_workflow.py tests/test_github_action_versions.py
```

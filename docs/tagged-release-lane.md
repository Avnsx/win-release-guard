# Tagged Release Lane

Purpose: document the explicit GitHub Release path for clean source archives. These are distribution checkpoints for Windows 11 Release Guard source archives, separate from the twice-daily public policy feed publish workflow.

Related links: [maintainer guide](maintainer-guide.md) | [v0.3.0 release notes](releases/v0.3.0.md) | [wiki tagged release lane](../wiki/Tagged-Release-Lane.md) | [safe exports](../wiki/Safe-Exports-and-Clean-Archives.md)

## Release Contract

| Item | Rule |
| --- | --- |
| Tag format | `vX.Y.Z`, matching `pyproject.toml` and runtime identity. |
| Workflow | `.github/workflows/release.yml`. |
| Artifact | `dist/win11_release_guard-source.zip`. |
| License | Repository `LICENSE.txt` is the GPL-3.0 license file and is included in the validated source archive. |
| Default release state | Draft unless explicitly changed by workflow input. |
| Release body | Links `CHANGELOG.md`, matching `docs/releases/vX.Y.Z.md`, Pages dashboard, public feed, and the separate PyPI lane. |
| Token | Built-in `github.token`; no PAT. |
| Scope | Source archive release, not Pages policy deployment. Publishing a GitHub Release can trigger the separate PyPI workflow, which still owns its own gates and environment approval. |

The manual workflow can create an annotated tag only when `create_tag=true` is explicitly provided. The built-in GitHub API token is used by the workflow and must never be exposed in logs, docs, or client code.

## PyPI Trusted Publishing Lane

| Item | Rule |
| --- | --- |
| Workflow | `.github/workflows/pypi-publish.yml`. |
| Trigger | Manual `workflow_dispatch` without a tag runs build/twine/self-test only; manual dispatch with an existing `vX.Y.Z` tag or a published GitHub Release can publish. No normal push or pull request publishing. |
| PyPI project | `https://pypi.org/project/win11_release_guard/`. |
| Environment | `pypi`, intended for manual approval. |
| Permission | `id-token: write` only in the PyPI publish job. |
| Credentials | No PyPI API token, Twine password, username, or credentialed repository URL. |
| Package artifacts | Wheel and sdist built from the selected source ref into generated `dist/`, checked with `twine check`, uploaded as a workflow artifact, then published through OIDC only when publish is tag-enabled. |
| Public install | `python -m pip install win11_release_guard` after a successful PyPI release. |

PyPI Trusted Publisher setup must match these values:

| Field | Value |
| --- | --- |
| Project name | `win11_release_guard` from `pyproject.toml` `[project].name` |
| Owner | `Avnsx` |
| Repository | `win11_release_guard` |
| Workflow | `pypi-publish.yml` |
| Environment | `pypi` |

If the project does not exist on PyPI, configure a Pending Trusted Publisher first. Pending Publisher does not reserve the package name; if the name is already owned by someone else, stop and report instead of publishing. Do not synthesize a publish tag from a branch run; the workflow verifies and checks out an existing tag before publishing.

TestPyPI is not wired in this workflow. If added later, it needs a separate Trusted Publisher configuration and a separate environment such as `testpypi`.

## Preflight Gates

```powershell
python -m compileall -q win11_release_guard tools
python tools/check_project_identity.py
python tools/check_github_action_versions.py
python tools/check_version_consistency.py
pytest -q
python -m win11_release_guard --self-test
python -m win11_release_guard --check-policy-source
python -m win11_release_guard --check-public-pages
python tools/export_clean_archive.py --output dist/win11_release_guard-source.zip
python tools/export_clean_archive.py --validate dist/win11_release_guard-source.zip
```

## Release Checklist

| Step | Action |
| --- | --- |
| 1 | Confirm worktree scope and version parity. |
| 2 | Run the preflight gates. |
| 3 | Create or select an annotated `vX.Y.Z` tag. |
| 4 | Run `release.yml` through tag push or manual dispatch. |
| 5 | Review the draft GitHub Release and attached clean archive. |
| 6 | Publish the GitHub Release only after verification output is credible. |
| 7 | Publish to PyPI separately through `pypi-publish.yml` only when explicitly intended. |

## Do / Do Not

| Do | Do not |
| --- | --- |
| Attach only the validated clean archive. | Upload raw worktree ZIPs. |
| Keep Pages publishing in `publish-policy.yml`. | Use release workflow to mutate the policy feed. |
| Keep PyPI publishing in `pypi-publish.yml` with Trusted Publishing. | Add long-lived PyPI credentials to Actions. |
| Document failed live checks honestly. | Claim live verification when network or endpoint checks failed. |
| Keep commit messages descriptive. | Use prompt/checkpoint/final-final style commit messages. |

## Rollback Notes

Tagged source releases are immutable audit anchors. If a release is wrong, publish a corrected tag/release with notes; do not rewrite public history casually.

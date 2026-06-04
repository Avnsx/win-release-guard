# Tagged Release Lane

Purpose: document the explicit GitHub Release path for clean source archives. These are distribution checkpoints for Windows 11 Release Guard source archives, separate from the twice-daily public policy feed publish workflow.

Related links: [docs index](README.md) | [wiki tagged release lane](../wiki/Tagged-Release-Lane.md) | [safe exports](../wiki/Safe-Exports-and-Clean-Archives.md)

## Release Contract

| Item | Rule |
| --- | --- |
| Tag format | `vX.Y.Z`, matching `pyproject.toml` and runtime identity. |
| Workflow | `.github/workflows/release.yml`. |
| Artifact | `dist/win11_release_guard-source.zip`. |
| License | Repository `LICENSE.txt` is the GPL-3.0 license file and is included in the validated source archive. |
| Default release state | Draft unless explicitly changed by workflow input. |
| Token | Built-in `github.token`; no PAT. |
| Scope | Source archive release, not Pages policy deployment. |

The manual workflow can create an annotated tag only when `create_tag=true` is explicitly provided. The built-in GitHub API token is used by the workflow and must never be exposed in logs, docs, or client code.

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
| 6 | Publish the release only after verification output is credible. |

## Do / Do Not

| Do | Do not |
| --- | --- |
| Attach only the validated clean archive. | Upload raw worktree ZIPs. |
| Keep Pages publishing in `publish-policy.yml`. | Use release workflow to mutate the policy feed. |
| Document failed live checks honestly. | Claim live verification when network or endpoint checks failed. |
| Keep commit messages descriptive. | Use prompt/checkpoint/final-final style commit messages. |

## Rollback Notes

Tagged source releases are immutable audit anchors. If a release is wrong, publish a corrected tag/release with notes; do not rewrite public history casually.

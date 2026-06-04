# Tagged Release Lane

Use this when publishing a GitHub Release with a validated clean source archive.

---

## Release Contract

| Item | Rule |
| --- | --- |
| Workflow | `.github/workflows/release.yml` |
| Tag | `vX.Y.Z`, matching package/runtime version |
| Artifact | `dist/win11_release_guard-source.zip` |
| Default state | Draft release |
| Token | Built-in GitHub token only |

## Checklist

| Step | Action |
| --- | --- |
| 1 | Confirm version parity with `tools/check_version_consistency.py`. |
| 2 | Run tests and source checks. |
| 3 | Create or select the exact `vX.Y.Z` tag. |
| 4 | Run release workflow. |
| 5 | Review draft release and attached archive. |

## Commands

```powershell
python tools/check_version_consistency.py
python tools/export_clean_archive.py --output dist/win11_release_guard-source.zip
python tools/export_clean_archive.py --validate dist/win11_release_guard-source.zip
```

## Do / Do Not

| Do | Do not |
| --- | --- |
| Attach only validated clean archives. | Attach raw worktree ZIPs. |
| Keep policy feed publishing in the Pages workflow. | Use release workflow for scheduled feed publication. |
| Keep release notes factual. | Hide failed gates or skipped live checks. |

## Related Pages

[[Home]] | [[Build, Test and Release|Build-Test-and-Release]] | [[Safe Exports and Clean Archives|Safe-Exports-and-Clean-Archives]]

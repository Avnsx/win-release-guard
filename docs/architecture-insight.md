# Architecture Insight

Purpose: document the current implementation boundaries that future maintainers must preserve. This is technical context, not a substitute for code, tests, workflows, and `AGENTS.md`.

Related links: [maintainer guide](maintainer-guide.md) | [wiki architecture](../wiki/Architecture.md) | [local detection](../wiki/Local-Windows-Detection.md) | [policy trust](../wiki/Policy-Feed-and-Trust-Model.md)

## Runtime Flow

| Step | Module | Contract |
| --- | --- | --- |
| Build config and CLI options | `__main__.py`, `config.py` | CLI flags and env vars become `ReleaseCheckerConfig`. |
| Fetch policy source | `api.py`, `remote_policy.py`, `cache.py` | Prefer live signed JSON; degrade visibly to cache or bundled policy. |
| Verify trust | `signing.py`, `json_utils.py`, `policy_schema.py` | Verify Ed25519 signature, strict JSON, schema, size bounds. |
| Probe local state | `local_state.py` | Build-first evidence with raw admin-facing diagnostics preserved. |
| Evaluate verdict | `evaluator.py`, `models.py` | Signed policy target drives status; local evidence describes installed state. |
| Optional diagnostics | `wua_probe.py`, `audit_probes.py`, `policy_diagnostics.py` | Read-only secondary context for update offers, logs, and likely blockers. |

## Source Hierarchy

| Rank | Evidence | Use |
| --- | --- | --- |
| 1 | Live public policy JSON plus `.sig` | Preferred runtime policy source. |
| 2 | Verified fresh cache | Degraded fallback when live fetch fails. |
| 3 | Verified stale cache | Degraded fallback with stronger warning. |
| 4 | Bundled signed policy | Last-known-good fallback; not production green in strict mode. |
| 5 | Local build and edition probes | Installed-state detection only. |
| 6 | WUA, Panther, DISM packages, event logs | Explanatory context only. |

## Release Targeting

| Rule | Reason |
| --- | --- |
| Prefer supported GA H2 release for existing devices. | Broad-fleet policy should not chase every upstream release string. |
| Exclude special/new-devices-only releases from existing-device target selection. | Current 26H1 semantics are explicit in policy/tests. |
| Keep LTSC and GA rows separate. | Enterprise LTSC and IoT Enterprise LTSC have different servicing paths. |
| Use `required_baseline_build` for the required quality baseline. | `latest_observed_build` can show newer observed rows without becoming the required baseline. |

## Do / Do Not

| Do | Do not |
| --- | --- |
| Keep runtime JSON-first and signed by default. | Re-enable Microsoft HTML parsing in normal runtime paths. |
| Preserve raw local diagnostic values. | Treat marketing/display labels as decisive identity evidence. |
| Keep WUA optional, bounded, and read-only. | Use WUA offers/history to replace the signed policy verdict. |
| Add fields compatibly to public `/api/v1`. | Remove or rename v1 fields/paths casually. |

## Verify

```powershell
python -m compileall -q win11_release_guard tools
pytest -q tests/test_evaluator.py tests/test_runtime_policy_sources.py tests/test_remote_policy.py
pytest -q tests/test_local_state.py tests/test_policy_generator.py
python tools/check_project_identity.py
```

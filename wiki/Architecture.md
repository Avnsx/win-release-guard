# Architecture

Use this to understand the current codebase shape before changing runtime behavior, policy generation, signing, or Pages output.

![Windows 11 Release Guard architecture flow from Microsoft public sources to fleet verdict](https://raw.githubusercontent.com/Avnsx/win11_release_guard/main/assets/images/windows-11-release-guard-architecture-flow.png)

---

## Flow

| Stage | Modules | Output |
| --- | --- | --- |
| Config | `__main__.py`, `config.py` | `ReleaseCheckerConfig` from CLI/env/defaults. |
| Policy source | `api.py`, `remote_policy.py`, `cache.py`, `bundled_policy.py` | Trusted or degraded policy source with structured source status. |
| Trust/schema | `signing.py`, `json_utils.py`, `policy_schema.py` | Verified signature, strict JSON, schema-safe model. |
| Local state | `local_state.py` | Build-first Windows evidence and raw diagnostics. |
| Evaluation | `evaluator.py`, `models.py` | `EvaluationResult` with status, target, warnings, source fields. |
| Diagnostics | `wua_probe.py`, `audit_probes.py`, `policy_diagnostics.py` | Optional read-only explanatory evidence. |
| Generation | `policy_generator.py`, `tools/generate_policy.py` | Static signed feed, dashboard, manifest, aliases. |

## Source Hierarchy

| Rank | Source | Production meaning |
| --- | --- | --- |
| 1 | Live signed public JSON | Preferred source. |
| 2 | Verified fresh cache | Degraded fallback. |
| 3 | Verified stale cache | Degraded fallback with stronger warning. |
| 4 | Bundled signed policy | Last-known-good fallback. |
| 5 | Local Windows probes | Installed-state detection only. |
| 6 | WUA / logs / packages | Explanation only. |

Source Diagnostics and workflow-synced GitHub Issues are source/publish
troubleshooting evidence only. They may explain parser drift, source freshness,
or ticket status, but they do not override signed policy trust or runtime
compliance verdicts.

## Rules

| Do | Do not |
| --- | --- |
| Keep runtime JSON-first. | Parse Microsoft HTML in normal runtime mode. |
| Keep generator parsing centralized. | Duplicate upstream parsing in clients. |
| Preserve raw admin diagnostics behind explicit opt-ins when default JSON compacts bulky Panther/setup log tails; keep Panther collection fixed-path, tail-bounded, and guarded by a generous total cap. | Hide surprising local values. |
| Keep Source Diagnostics and GitHub Issues as diagnostic context. | Treat issue labels or dashboard diagnostics as compliance authority. |
| Add public API fields compatibly. | Break `/api/v1` paths or remove existing contract fields. |

## Verify

```powershell
python -m compileall -q win11_release_guard tools
pytest -q tests/test_runtime_policy_sources.py tests/test_evaluator.py tests/test_remote_policy.py
python tools/check_project_identity.py
```

## Related Pages

[Home](Home) | [Policy Feed and Trust Model](Policy-Feed-and-Trust-Model) | [Local Windows Detection](Local-Windows-Detection)

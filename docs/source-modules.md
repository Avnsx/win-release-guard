# Source Module Map

Purpose: provide a compact maintainer map of source modules, scripts, and tests without duplicating implementation details.

Related links: [docs index](README.md) | [wiki architecture](../wiki/Architecture.md)

## Runtime Modules

| Module | Responsibility |
| --- | --- |
| `__main__.py` | CLI parsing, output formatting, self-test/source-check modes. |
| `api.py` | Top-level orchestration, policy source fallback, strict-production degradation. |
| `config.py` | Defaults, env vars, runtime knobs. |
| `models.py` | Result, policy, source, and diagnostic data models. |
| `evaluator.py` | Target selection and verdict computation. |
| `local_state.py` | Local Windows build/edition evidence. |
| `wua_probe.py` | Optional bounded read-only WUA probe. |
| `audit_probes.py`, `policy_diagnostics.py` | Read-only blocker diagnostics. |
| `remote_policy.py` | JSON loading plus generator-only Release Health parsing. |
| `policy_generator.py` | Policy/dashboard/manifest/API generation. |
| `signing.py`, `json_utils.py`, `policy_schema.py` | Trust, strict JSON, schema validation. |
| `cache.py`, `bundled_policy.py`, `freshness.py`, `version.py` | Cache, bundled fallback, age calculations, identity. |

## Tool Scripts

| Script | Responsibility |
| --- | --- |
| `generate_policy.py` | CLI wrapper for policy/dashboard generation. |
| `generate_signing_key.py` | Local key generation into ignored scratch space. |
| `export_clean_archive.py` | Clean source archive creation and validation. |
| `scan_for_secret_material.py` | Secret/private-key pattern scanner. |
| `check_project_identity.py` | Naming, legacy entrypoint, generated identity checks. |
| `check_version_consistency.py` | Version marker parity. |
| `check_github_action_versions.py` | Workflow action pinning audit. |
| `check_dependency_freshness.py` | Direct dependency freshness report. |
| `check_commit_message.py` | Commit message hygiene. |

## Repository Legal File

| File | Responsibility |
| --- | --- |
| `LICENSE.txt` | GPL-3.0 license text for repository source distribution and validated clean archive consumers. |

## Test Layout

| Area | Representative tests |
| --- | --- |
| Runtime source fallback | `test_runtime_policy_sources.py`, `test_source_failures.py` |
| Evaluator and local truth | `test_evaluator.py`, `test_edge_cases.py`, `test_local_state.py` |
| Generator and Pages | `test_policy_generator.py`, `test_pages_landing.py`, `test_remote_policy.py` |
| Signing and JSON hardening | `test_signing.py`, `test_signing_key_management.py`, `test_json_hardening.py` |
| Automation and release | `test_repository_automation.py`, `test_publish_policy_workflow.py`, `test_ci_workflow.py` |
| Identity and exports | `test_branding_contract.py`, `test_project_identity.py`, `test_export_clean_archive.py` |

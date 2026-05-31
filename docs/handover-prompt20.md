# Handover Prompt 20

Final hardening pass summary for `win-release-guard`, completed on 2026-05-31.

## Current State

- Repository/product/site/distribution name: `win-release-guard`.
- Python import namespace remains `win11_release_guard`.
- Supported CLI entry point remains `python -m win11_release_guard` or console script `win-release-guard`.
- `docs/handover-prompt19.md` was intentionally removed and was not restored.
- Root prototype script remains absent.
- Active production path uses public Microsoft Release Health and Atom sources only.
- Runtime clients fetch public GitHub Pages JSON plus detached `.sig` and verify Ed25519 signatures locally.
- Runtime clients do not use GitHub tokens, PATs, private repo access, or client-side GitHub authentication.
- WUA remains secondary evidence only.

## Files Changed During This Pass

- `AGENTS.md`
- `README.md`
- `docs/handover-prompt19.md` deleted intentionally
- `docs/policy-signing.md`
- `tests/test_branding_contract.py`
- `tests/test_cli.py`
- `tests/test_commit_message_hygiene.py`
- `tests/test_export_clean_archive.py`
- `tests/test_import_contract.py`
- `tests/test_no_active_graph_auth_references.py`
- `tests/test_no_secret_material.py`
- `tests/test_pages_landing.py`
- `tests/test_policy_generator.py`
- `tests/test_policy_source_cli.py`
- `tests/test_publish_policy_workflow.py`
- `tests/test_remote_policy.py`
- `tests/test_runtime_policy_sources.py`
- `tests/test_signing.py`
- `tests/test_signing_key_management.py`
- `tests/test_source_failures.py`
- `tools/export_clean_archive.py`
- `tools/check_commit_message.py`
- `tools/generate_signing_key.py`
- `tools/scan_for_secret_material.py`
- `win11_release_guard/policy_generator.py`

## Commits Created During This Pass

- `5953876 Preserve fixed robots contract in policy generator`
- `5b79d4b Enforce win-release-guard branding and source hygiene`
- `eeff852 Harden Ed25519 policy signing safeguards`
- `14ad217 Polish public policy feed landing page`
- `457a2e0 Clarify excluded release summaries on Pages dashboard`
- `7ea5315 Document final Pages policy feed hardening`
- `Enforce descriptive commit message hygiene`

## Final Commands Run

- `git -c safe.directory=* status --short`
- `python -m compileall -q win11_release_guard tools`
- `python tools/check_commit_message.py --message "Enforce descriptive commit message hygiene"`
- `pytest -q tests/test_commit_message_hygiene.py tests/test_agents_contract.py tests/test_export_clean_archive.py`
- `pytest -q`
- `python -m win11_release_guard --self-test`
- `python -m win11_release_guard --diagnose-config`
- `python -m win11_release_guard --check-policy-source`
- `python -m win11_release_guard --check-public-pages`
- `python -m win11_release_guard --json-pretty --no-wua | python -m json.tool`
- `python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github`
- `python tools/export_clean_archive.py`
- `gh run view 26720624585 --repo Avnsx/win-release-guard --json status,conclusion,url`
- `gh secret list --repo Avnsx/win-release-guard`

## Final Verification Results

- `python -m compileall -q win11_release_guard tools`: passed.
- `python tools/check_commit_message.py --message "Enforce descriptive commit message hygiene"`: passed.
- `pytest -q tests/test_commit_message_hygiene.py tests/test_agents_contract.py tests/test_export_clean_archive.py`: `10 passed`.
- `pytest -q`: `249 passed`.
- `python -m win11_release_guard --self-test`: passed, package import ok, bundled policy loaded, bundled signature valid, policy schema ok, no remote fetch, no WUA probe.
- `python -m win11_release_guard --diagnose-config`: passed, remote fetch not performed, bundled policy present, bundled signature valid.
- `python -m win11_release_guard --check-policy-source`: passed.
- `python -m win11_release_guard --check-public-pages`: passed.
- `python -m win11_release_guard --json-pretty --no-wua | python -m json.tool`: passed; parsed JSON was written to a temporary file for validation.
- `python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github`: passed after this handover was created.
- `python tools/export_clean_archive.py`: passed after this handover was created; archive had `66` entries.

## Live Endpoint Results

- Live network checks were run successfully.
- `https://avnsx.github.io/win-release-guard/`: HTTP 200 through `--check-public-pages`.
- `https://avnsx.github.io/win-release-guard/windows-release-policy.json`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/windows-release-policy.json.sig`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/policy-manifest.json`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/api/v1/policy.json`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/api/v1/policy.sig`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/api/v1/manifest.json`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/robots.txt`: HTTP 200.
- `https://avnsx.github.io/win-release-guard/sitemap.xml`: HTTP 200.
- Live policy signature was valid.
- Live manifest hash matched live policy bytes.
- Manifest/API aliases return 200.
- Old manifest 404 remains resolved.
- The old loaded URL warning is gone; `source_urls` is upstream-only and GitHub Pages URLs are validated through `published_urls`.

## GitHub Actions Status

- Publish policy workflow for latest Pages dashboard commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26720624598`
  - Commit: `457a2e09be73fd8e2567570153cf008cba08c2c2`
- CI workflow for latest Pages dashboard commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26720624585`
  - Commit: `457a2e09be73fd8e2567570153cf008cba08c2c2`

## Signing And Secrets

- Current production key id: `win-release-guard-policy-2026-05`.
- Live signature key id: `win-release-guard-policy-2026-05`.
- Live manifest key id: `win-release-guard-policy-2026-05`.
- `win11_release_guard/data/trusted_policy_keys.json` contains the active 2026-05 public key and the old 2026-01 public key marked `retiring`.
- GitHub secret `WIN_RELEASE_GUARD_POLICY_SIGNING_KEY_B64` is configured in the repository.
- The secret value was not inspected, printed, copied into source, or committed.
- No private signing key material is committed.
- `site/` secret scan passed.
- Full source/generated-output secret scan passed.
- Explicit local check found no `.tmp/**/private-key.b64` files.

## Robots Contract

`robots.txt` remains exactly:

```text
User-agent: *
Allow: /
Sitemap: https://avnsx.github.io/win-release-guard/sitemap.xml
```

- Local generator tests assert byte-for-byte content.
- Live `robots.txt` was fetched and matched the exact immutable content.

## Pages Dashboard

- Landing page is HTML/CSS, no external JavaScript or analytics.
- Landing page includes direct links to canonical policy/signature/manifest and API aliases.
- Landing page uses the curated 26H1 summary:
  `26H1 is excluded for existing devices because Microsoft scopes it to new devices and does not offer it as an in-place update from 24H2/25H2.`
- Live landing page contains the curated 26H1 summary.
- Live landing page does not contain the previous truncated `existing devi.` fragment.

## Clean Archive

- Clean archive command passed after the commit-message hygiene files were added.
- `dist/win-release-guard-source.zip` contains `68` entries after the commit-message hygiene files were added.
- Archive excludes `.git/`, `.pytest_cache/`, `__pycache__/`, `.cache/`, `.tmp/`, `dist/`, local `site/`, generated ZIPs, `out*.json`, old prototype files, and private key file names.
- Ignored local generated artifacts may still exist after verification:
  - `site/`
  - `.tmp/`
  - `dist/`
  - `.pytest_cache/`
  - `__pycache__/`
- These ignored artifacts are not source and are excluded from the clean archive.

## Remaining Risks

- Live GitHub Pages health depends on GitHub Pages and GitHub Actions availability; normal PR/unit-test CI intentionally does not depend on live Pages.
- GitHub Actions emitted a Node.js 20 deprecation warning for current action versions; the workflow succeeded, but action versions may need future refresh when GitHub changes runner defaults.
- Microsoft Release Health HTML or Atom feed shape can change; parser tests and source failure classification cover known expected shapes, but feed drift remains an operational risk.
- WUA is intentionally secondary diagnostic evidence and should not be treated as authority over signed policy verdicts.

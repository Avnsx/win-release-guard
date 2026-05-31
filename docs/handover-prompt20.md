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
- Repository automation now includes Dependabot version updates, CodeQL, Pylint, direct dependency freshness, and dependency audit workflows.

## Files Changed During This Pass

- `AGENTS.md`
- `.github/dependabot.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/dependency-audit.yml`
- `.github/workflows/dependency-freshness.yml`
- `.github/workflows/pylint.yml`
- `.gitignore`
- `README.md`
- `docs/handover-prompt19.md` deleted intentionally
- `docs/policy-signing.md`
- `docs/security-automation.md`
- `tests/test_branding_contract.py`
- `tests/test_cli.py`
- `tests/test_commit_message_hygiene.py`
- `tests/test_export_clean_archive.py`
- `tests/test_import_contract.py`
- `tests/test_dependency_freshness.py`
- `tests/test_live_verification_gate_docs.py`
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
- `tools/check_dependency_freshness.py`
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
- `88d40f1 Enforce descriptive commit message hygiene`
- `1b08ebd Add live verification gate for Pages feed changes`
- `6aa3ee3 Record final production readiness audit`
- `e06bdff Add repository security automation`
- `Document repository automation rollout`

## Final Commands Run

- `git -c safe.directory=* status --short`
- `python -m compileall -q win11_release_guard tools`
- `python tools/check_commit_message.py --message "Enforce descriptive commit message hygiene"`
- `python tools/check_commit_message.py --message "Add live verification gate for Pages feed changes"`
- `python tools/check_commit_message.py --message "Add repository security automation"`
- `pytest -q tests/test_commit_message_hygiene.py tests/test_agents_contract.py tests/test_export_clean_archive.py`
- `pytest -q tests/test_agents_contract.py tests/test_live_verification_gate_docs.py`
- `pytest -q tests/test_dependency_freshness.py tests/test_repository_automation.py tests/test_export_clean_archive.py tests/test_agents_contract.py`
- `pytest -q`
- `pylint --fail-under=8.0 win11_release_guard tools`
- isolated `pip-audit --local` run in ignored `.tmp/` virtual environment
- `python tools/check_dependency_freshness.py --help`
- `python tools/check_dependency_freshness.py --output dependency-freshness.json`
- `python tools/generate_policy.py --release-health-html tests/fixtures/windows11-release-health.html --atom-feed tests/fixtures/windows11-atom.xml --output-dir site --write-index --write-robots --write-sitemap --write-manifest --signing-key-file .tmp/signing-test/private-key.b64`
- `python -m win11_release_guard --self-test`
- `python -m win11_release_guard --diagnose-config`
- `python -m win11_release_guard --check-policy-source`
- `python -m win11_release_guard --check-public-pages`
- `python -m win11_release_guard --json-pretty --no-wua | python -m json.tool`
- `python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github`
- `python tools/export_clean_archive.py`
- live badge SVG HEAD checks for CI, Publish policy, CodeQL, Pylint, Dependency audit, and Dependency freshness
- live workflow run polling for CI, CodeQL, Pylint, Dependency audit, and Dependency freshness
- code scanning alerts API check
- dependency alerts API check
- dependency security updates API check
- stale project/prototype identity scan across the repository
- active authenticated Microsoft API reference scan across README, AGENTS, docs, package, tools, and workflows
- GitHub token and private-key marker scan across source and generated site paths
- `gh run list --repo Avnsx/win-release-guard --workflow "CI" --branch main --limit 1 --json databaseId,status,conclusion,headSha,url,createdAt`
- `gh run list --repo Avnsx/win-release-guard --workflow "Publish policy" --branch main --limit 1 --json databaseId,status,conclusion,headSha,url,createdAt`
- `gh secret list --repo Avnsx/win-release-guard`

## Final Verification Results

- `python -m compileall -q win11_release_guard tools`: passed.
- `python tools/check_commit_message.py --message "Enforce descriptive commit message hygiene"`: passed.
- `python tools/check_commit_message.py --message "Add live verification gate for Pages feed changes"`: passed.
- `python tools/check_commit_message.py --message "Add repository security automation"`: passed.
- `pytest -q tests/test_commit_message_hygiene.py tests/test_agents_contract.py tests/test_export_clean_archive.py`: `10 passed`.
- `pytest -q tests/test_agents_contract.py tests/test_live_verification_gate_docs.py`: `6 passed`.
- `pytest -q tests/test_dependency_freshness.py tests/test_repository_automation.py tests/test_export_clean_archive.py tests/test_agents_contract.py`: `20 passed`.
- `pytest -q`: `265 passed`.
- Pylint: passed with score `8.84/10`.
- Isolated dependency audit: no known vulnerabilities found; local package itself was skipped because it is not published on PyPI.
- Dependency freshness: `current`; checked `cryptography`, `packaging`, and `pytest`; updates available: `0`.
- `python -m win11_release_guard --self-test`: passed, package import ok, bundled policy loaded, bundled signature valid, policy schema ok, no remote fetch, no WUA probe.
- `python -m win11_release_guard --diagnose-config`: passed, remote fetch not performed, bundled policy present, bundled signature valid.
- `python -m win11_release_guard --check-policy-source`: passed.
- `python -m win11_release_guard --check-public-pages`: passed.
- `python -m win11_release_guard --json-pretty --no-wua | python -m json.tool`: passed; parsed JSON was written to a temporary file for validation.
- `python tools/scan_for_secret_material.py site win11_release_guard tests tools docs README.md AGENTS.md pyproject.toml .github`: passed after this handover was created.
- `python tools/export_clean_archive.py`: passed; archive had `78` entries.
- Stale prototype/package identity search: no matches.
- Active authenticated Microsoft API reference search across active paths: no matches.
- GitHub token/private-key block search across source/site paths: no matches.
- Explicit private-key filename check in source and `.tmp/`: no private key files found after removing the local ignored signing-test key.

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
- README workflow badge SVG URLs returned HTTP 200 for CI, Publish policy, CodeQL, Pylint, Dependency audit, and Dependency freshness.

## GitHub Actions Status

- Publish policy workflow for latest Pages dashboard commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26720624598`
  - Commit: `457a2e09be73fd8e2567570153cf008cba08c2c2`
- CI workflow for latest pushed hardening commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26721003945`
  - Commit: `1b08ebd40b9819605596ae18d79c7ae8acf4c3ee`
- CI workflow for repository automation commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26721441587`
  - Commit: `e06bdff600c840e72c8a67edb234fe458b6de6f8`
- CodeQL workflow for repository automation commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26721441591`
- Pylint workflow for repository automation commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26721441593`
- Dependency audit workflow for repository automation commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26721441576`
- Dependency freshness workflow for repository automation commit: success.
  - Run: `https://github.com/Avnsx/win-release-guard/actions/runs/26721441612`

## Repository Security Automation

- Dependabot version updates are configured in `.github/dependabot.yml` for `pip` and `github-actions`.
- CodeQL code scanning is configured in `.github/workflows/codeql.yml`.
- Code scanning alerts API returned a valid array response after the CodeQL workflow succeeded.
- Dependency alerts API returned enabled status.
- Dependency security updates API returned `enabled: true`.
- GitHub UI settings are still documented in `docs/security-automation.md` because not every repository setting is fully controlled by source files.
- README badges are workflow status badges only; no static dependency currency or code quality claim was added.
- Dependency freshness badge is backed by `.github/workflows/dependency-freshness.yml`.
- Dependency audit badge is backed by `.github/workflows/dependency-audit.yml`.

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

- Clean archive command passed after repository automation files were added.
- `dist/win-release-guard-source.zip` contains `78` entries.
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
- Dependency freshness checks direct dependency specifiers against latest stable PyPI releases; it does not audit transitive currency.
- Dependency audit depends on the Python vulnerability database and PyPI availability during workflow execution.

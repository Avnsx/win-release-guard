# Policy Feed And Trust Model

Use this when changing policy source loading, signature verification, manifest checks, key rotation, or public API aliases.

---

## Public Artifacts

| Artifact | URL / path | Purpose |
| --- | --- | --- |
| Policy JSON | `/windows-release-policy.json` | Canonical policy document. |
| Signature | `/windows-release-policy.json.sig` | Detached Ed25519 signature metadata. |
| Manifest | `/policy-manifest.json` | Hashes, freshness fields, source diagnostics, published URLs. |
| API policy | `/api/v1/policy.json` | Stable policy alias. |
| API signature | `/api/v1/policy.sig` | Stable signature alias. |
| API manifest | `/api/v1/manifest.json` | Stable manifest alias. |

## Trust Rules

| Rule | Detail |
| --- | --- |
| Public data is not automatically trusted. | Runtime verifies the detached signature before accepting policy bytes. |
| Key lookup uses `key_id`. | Committed public keys live in `win11_release_guard/data/trusted_policy_keys.json`. |
| Private signing key is never committed. | GitHub Actions secret stores the production private key. |
| Retiring keys stay bounded. | `verify_not_after_utc` prevents fresh signatures from retired/retiring keys after their window. |
| `/api/v1` stays compatible. | Add fields compatibly; do not remove paths during the compatibility window. |

## JSON Hardening

| Guard | Behavior |
| --- | --- |
| Duplicate keys | Rejected by strict JSON parsing. |
| NaN / Infinity | Rejected as non-finite JSON numbers. |
| Non-object top level | Rejected where objects are required. |
| Size caps | Policy, manifest, signature, cache, and trusted-key payloads are bounded before parsing. |
| Unknown additive keys | Allowed as forward-compatible warnings unless schema rules reject them. |

## Fallback Order

| Order | Source | Source status |
| --- | --- | --- |
| 1 | Live signed remote JSON | `REMOTE_POLICY_OK` |
| 2 | Verified fresh cache | `USING_FRESH_CACHE` |
| 3 | Verified stale cache | `USING_STALE_CACHE` |
| 4 | Bundled signed policy | `USING_BUNDLED_POLICY` |
| 5 | No valid source | `POLICY_UNAVAILABLE` / `CHECK_INCOMPLETE` |

## Baseline And Preview Semantics

| Field / term | Meaning |
| --- | --- |
| `baseline_build` | Required broad-fleet quality baseline. |
| `required_baseline_build` | Explicit required baseline used by current readers. |
| `latest_observed_build` | Newest Microsoft-observed current-table or release-history build. |
| B-release | Default required quality baseline. |
| D-preview | Can explain a newer local build without becoming the default required baseline. |

## Manifest Hash Checks

| Check | Purpose |
| --- | --- |
| `policy_sha256` | Confirms downloaded policy bytes match the manifest. |
| `signature_sha256` | Confirms signature bytes match the manifest when present. |
| API alias hashes | Confirms public aliases match or are documented as compatible. |

## Verify

```powershell
python -m win11_release_guard --self-test
python -m win11_release_guard --check-policy-source
python -m win11_release_guard --check-public-pages
pytest -q tests/test_signing.py tests/test_json_hardening.py tests/test_policy_source_cli.py
```

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| Trusting public hosting without signature verification. | Verify Ed25519 signature over exact JSON bytes. |
| Deleting old public keys during rotation. | Keep retiring keys with bounded overlap. |
| Moving Pages URLs into `source_urls`. | Keep public hosting URLs in `published_urls`; upstream Microsoft inputs stay in `source_urls`. |

## Related Pages

[[Home]] | [[Source Diagnostics|Source-Diagnostics]] | [[Anti-Static Freshness|Anti-Static-Freshness]]

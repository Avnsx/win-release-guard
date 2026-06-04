# Configuration

Use this when choosing runtime defaults or documenting CLI/env knobs for fleet usage.

---

## Recommended Defaults

| Context | Default |
| --- | --- |
| Human local check | `--pretty` |
| RMM compliance | `--json --no-wua` |
| Production compliance | `--strict-production --json --no-wua` |
| Troubleshooting update offers | Add `--wua` |
| Source-only verification | `--check-policy-source` and `--check-public-pages` |

## Settings / Knobs

| Knob | Source | Meaning |
| --- | --- | --- |
| `--policy-url` | CLI | Override default policy URL or use local file. |
| `WIN11_RELEASE_GUARD_POLICY_URL` | Env | Default policy URL override. |
| `--strict-production` | CLI | Require live signed remote JSON for production-green result. |
| `WIN11_RELEASE_GUARD_STRICT_PRODUCTION` | Env | Enable strict-production preset. |
| `--cache-file` | CLI | Override cache path. |
| `--cache-max-age-hours` | CLI | Fresh cache age. |
| `--stale-cache-max-age-hours` | CLI | Stale cache allowance. |
| `--max-policy-bytes` | CLI/env | Policy fetch/parse size cap. |
| `--wua` / `--no-wua` | CLI | Enable or disable optional WUA probe. |
| `--quality-policy` | CLI | Choose B-release default or broader quality policy. |

## Runtime Clamps / Fallbacks

| Area | Default behavior |
| --- | --- |
| HTTP fetch | Bounded timeout and byte cap. |
| WUA subprocess | Bounded timeout. |
| DISM / PowerShell probes | Bounded timeouts. |
| Panther logs | Bounded tail size. |
| WUA output | History and relevant OS update lists are bounded. |
| Cache fallback | Visible degraded source status. |

## Deprecated / Avoid

| Avoid | Reason |
| --- | --- |
| `--allow-unsigned-policy` in production | Removes signature trust requirement. |
| Runtime HTML fallback | Generator owns Microsoft HTML parsing. |
| Treating stale cache as production-green | Strict-production blocks this. |

## Verify

```powershell
python -m win11_release_guard --diagnose-config
pytest -q tests/test_cache.py tests/test_cli.py
```

## Related Pages

[[Home]] | [[CLI and RMM Usage|CLI-and-RMM-Usage]] | [[Policy Feed and Trust Model|Policy-Feed-and-Trust-Model]]

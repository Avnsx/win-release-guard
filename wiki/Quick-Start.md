# Quick Start

Use this when you want to install the released package, run a human check, and verify the public policy feed quickly.

---

## Install

```powershell
python -m pip install win11_release_guard
```

## Run

| Need | Command |
| --- | --- |
| Human console output | `win11_release_guard --pretty` |
| JSON for RMM/scripts | `win11_release_guard --json-pretty --no-wua` |
| Production-style source gating | `win11_release_guard --strict-production --json-pretty --no-wua` |
| Check signed policy source | `win11_release_guard --check-policy-source` |
| Check public Pages surface | `win11_release_guard --check-public-pages` |

## Local Integrity

```powershell
python -m compileall -q win11_release_guard tools
python -m win11_release_guard --self-test
python -m win11_release_guard --diagnose-config
pytest -q
```

## What To Expect

| Status | Meaning |
| --- | --- |
| `COMPLIANT` | Installed release/build meets the signed policy target and baseline. |
| `FEATURE_UPDATE_REQUIRED` | Existing device is below the broad target release. |
| `QUALITY_UPDATE_REQUIRED` | Device is on target release but below required baseline. |
| `CHECK_INCOMPLETE` | Policy source/trust/freshness was not good enough to decide. |
| `ABOVE_BROAD_TARGET_OR_SPECIAL_RELEASE` | Device is on a release above or outside the broad target semantics. |

## Related Pages

[Home](Home) | [CLI and RMM Usage](CLI-and-RMM-Usage) | [Troubleshooting](Troubleshooting)

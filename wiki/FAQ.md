# FAQ

Short answers for common administrator, maintainer, and agent questions.

---

## Does this install or trigger updates?

No. It evaluates state and emits diagnostics. It does not install, hide, schedule, download, or trigger Windows updates.

## Why is 25H2 the current target for existing devices?

The policy selects the supported broad-fleet existing-device target. Current code/tests treat 25H2 as that target and keep 26H1 out of existing-device target selection because it is new-devices-only.

## What if the local machine shows a stale Windows label?

The guard preserves the raw label for review, but build-family and signed policy mapping drive the result.

## Is WUA required?

No. WUA is optional, read-only diagnostic evidence. Default integration paths can run without it.

## Why does strict-production return `CHECK_INCOMPLETE` from cache?

Strict mode requires fresh live signed remote JSON. Cache and bundled fallback remain visible degraded evidence.

## Are public feed artifacts secret?

No. Policy JSON, signatures, manifests, dashboard files, and public keys are non-secret. Private signing keys and tokens must never be committed.

## What license does the repository use?

The repository uses GPL-3.0. The full license text lives in `LICENSE.txt` and is included in validated clean source archives.

## Do I need a PyPI API token?

No. The current publish workflow uses PyPI Trusted Publishing with GitHub Actions OIDC. Configure PyPI with project `win11_release_guard`, owner `Avnsx`, repository `win11_release_guard`, workflow `pypi-publish.yml`, and environment `pypi`. Do not paste publishing tokens, usernames, passwords, or credentialed repository URLs into workflow YAML.

## Does local wiki source publish automatically?

No. The repository `wiki/` folder is source/staging only. Push the live GitHub Wiki repository separately when explicitly intended.

## Does a Pending Trusted Publisher reserve the package name?

No. If the PyPI name is already owned by someone else, stop and report instead of publishing.

## Is TestPyPI configured?

No. Add it only as a separate lane with its own TestPyPI Trusted Publisher and GitHub Environment such as `testpypi`.

## Can `/api/v1` change?

Fields can be added compatibly. Existing public v1 paths and contract fields should not be removed casually.

## Why is the dashboard age recalculated in the browser?

Static Pages output can become old without re-rendering. The page embeds generated epoch fields and uses browser time to show live feed age.

## Related Pages

[Home](Home) | [Quick Start](Quick-Start) | [Troubleshooting](Troubleshooting)

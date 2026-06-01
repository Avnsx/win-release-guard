# Architecture Insight

This document records the architecture reasoning behind `win11_release_guard`.
It is written as implementation context, not as a product contract. Current
code, tests, workflows, and `AGENTS.md` remain the source of truth.

## Objective

`win11_release_guard` answers two separate questions:

- What Windows 11 build and release is installed locally?
- What release and baseline should existing broad-fleet Windows 11 devices use?

The implementation keeps those questions separate. Local system evidence
describes the installed state. Signed policy data describes the intended broad
target. Secondary local evidence can explain anomalies, but it must not replace
the signed policy verdict.

## Source Hierarchy

The runtime client should prefer evidence in this order:

1. Signed policy JSON from the public Pages feed.
2. Cached signed policy if the live feed is unavailable.
3. Bundled signed last-known-good policy.
4. Local build and edition probes for installed-state detection.
5. WUA, setup, package, and log evidence as explanatory context.

The policy feed is authoritative for release targeting. WUA and local update
history can explain why a build is above baseline or why an update appears in
history, but they must not override the signed policy.

## Local Installed-State Evidence

Local build detection should be build-first. Product names, captions, and
display labels are useful diagnostics but are not reliable primary identity
signals.

Useful local signals:

- `RtlGetVersion` for the running OS build.
- CIM/WMI build fields such as `Win32_OperatingSystem.Version` and
  `BuildNumber`.
- DISM current edition for edition context.
- `ntoskrnl.exe` file version as a build consistency signal.
- Registry build values as raw diagnostics, not as the only truth source.

Local probes should preserve raw administrator-facing values. If a system has a
stale or surprising display label, the value should be shown as observed rather
than hidden.

## Remote Policy Evidence

The production generator uses public Microsoft Release Health HTML and public
Microsoft Update History Atom sources. Runtime clients do not parse Microsoft
HTML in the normal path.

The generated policy should contain:

- schema version
- generation timestamp
- upstream source URLs
- published Pages URLs
- broad target for existing devices
- baseline build
- current release rows
- release history rows
- preview and out-of-band classifications
- excluded or special releases
- signing metadata

This design keeps parser maintenance in the generator and lets deployed clients
consume a stable signed JSON contract.

## Existing-Device Broad Target

The broad target is the release intended for existing devices, not necessarily
the highest release string present in upstream material. A release can be
present in upstream data and still be excluded for in-place updates on existing
24H2 or 25H2 devices.

The policy model therefore has explicit fields for excluded releases and
reasons. The page dashboard should show a curated human summary, while the JSON
can preserve raw upstream wording for auditability.

## WUA Evidence

Windows Update Agent evidence is secondary. It is useful for:

- offered update titles
- installed update history
- KB extraction
- preview update evidence
- result codes and HRESULTs
- localized titles

WUA evidence can identify that a build above the baseline likely came from a
preview or out-of-band update. It must not change the signed policy's broad
target or required baseline.

## Preview and Out-of-Band Builds

A build above the broad baseline is not automatically the new required fleet
baseline. The evaluator should distinguish at least these cases:

- matches current signed baseline
- newer than baseline with policy release-history evidence
- newer than baseline with WUA preview evidence
- newer than baseline with unknown origin
- older than baseline

Pretty output should state when the exact origin is unknown because live policy
or WUA evidence was not used.

## Signing and Trust

The policy feed is public static data. Trust comes from Ed25519 verification,
not from repository privacy or client-side GitHub authentication.

Rules:

- Runtime clients do not authenticate to GitHub.
- Private signing keys are not committed.
- The production private key is stored in the repository Actions secret
  `WIN11_RELEASE_GUARD_POLICY_SIGNING_KEY_B64`.
- Public verification keys are committed.
- The bundled policy bytes and detached signature must be updated together.
- The bundled policy must use the current `win11_release_guard` identity.

## Generator and Pages Deployment

The generator should run in GitHub Actions and publish a Pages artifact. The
workflow should:

- use minimal token permissions
- generate signed policy artifacts
- validate schema and signature before upload
- scan generated output for secret material
- publish `index.html`, policy JSON, signature, manifest, API aliases,
  `robots.txt`, `sitemap.xml`, and `.nojekyll`
- avoid branch-push Pages deployment
- avoid client-side authentication requirements

## Operational Risks

Known risks are operational rather than architectural:

- Scheduled GitHub Actions runs can be delayed or skipped by the platform.
- Upstream Microsoft page structure can change and require generator updates.
- Atom feed classification can miss future naming changes.
- WUA history is localized and noisy.
- Local machines can have stale captions or policy restrictions.

The mitigations are explicit source status, visible warnings, schema validation,
signature verification, cache/bundled fallback, and tests using realistic
fixtures.

## Current Implementation Direction

The current implementation follows this model:

- signed policy first
- local build-first installed-state detection
- WUA secondary evidence only
- public Pages JSON plus detached signature
- Ed25519 verification with committed public keys
- generator-owned upstream parsing
- clean archive and identity checks
- no old prototype entry point

Future changes should preserve those boundaries unless the repository owner
explicitly changes the product architecture.

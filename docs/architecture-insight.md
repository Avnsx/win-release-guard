# Architecture Insight

Detailed architecture context now lives in the GitHub Wiki:

https://github.com/Avnsx/win11_release_guard/wiki/Architecture-Insight

Repository invariants kept here for local agents and tests:

- Signed policy JSON is the runtime source of truth for the broad-fleet target.
- Local build and edition probes describe the installed state.
- WUA, Panther, DISM, setup logs, and package data are secondary evidence only.
- Runtime clients do not scrape Microsoft HTML in the normal path.
- Generator-owned upstream parsing produces the signed public policy feed.
- The public feed is verified with Ed25519 signatures and committed public keys.

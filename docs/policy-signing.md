# Policy Signing

Detailed signing documentation now lives in the GitHub Wiki:

https://github.com/Avnsx/win11_release_guard/wiki/Policy-Feed-and-Signing

Repository invariants kept here for local agents and tests:

- Runtime clients never authenticate to GitHub and never need GitHub tokens.
- Private signing keys are never committed.
- The production private key is stored only as GitHub Actions secret
  `WIN11_RELEASE_GUARD_POLICY_SIGNING_KEY_B64`.
- Trusted public keys are committed in
  `win11_release_guard/data/trusted_policy_keys.json`.
- Signatures carry `key_id`; runtime verification selects the matching public
  key by `key_id`.
- The signed bundled policy JSON must use the current `win11_release_guard`
  identity and must verify against its detached signature.

# Policy Signing

`win11_release_guard` policy feeds are public static JSON plus a detached
Ed25519 signature. Runtime clients never authenticate to GitHub and never need
GitHub tokens.

## Key Model

- Private signing keys are never committed.
- The private key is stored only as GitHub Actions Secret
  `WIN11_RELEASE_GUARD_POLICY_SIGNING_KEY_B64`.
- Trusted public keys are committed in
  `win11_release_guard/data/trusted_policy_keys.json`.
- Signatures carry `key_id`; runtime verification selects the matching public
  key by `key_id`.
- Multiple public keys can remain in `trusted_policy_keys.json` during key
  rotation.

## Generate a New Key

Generate key material into ignored scratch space:

```powershell
python tools/generate_signing_key.py --out-dir .tmp/signing-key
```

The tool writes:

- a generated private key file under `.tmp/signing-key/`
- `.tmp/signing-key/public-key.b64`
- `.tmp/signing-key/trusted_policy_keys.json`

Copy the complete contents of the generated private key file into GitHub
Actions Secret `WIN11_RELEASE_GUARD_POLICY_SIGNING_KEY_B64`.

Do not commit generated private signing key material. Commit only reviewed public
key records in `win11_release_guard/data/trusted_policy_keys.json`.

## Rotate Keys

1. Generate a new key with a new `key_id`.
2. Add the new public key record to
   `win11_release_guard/data/trusted_policy_keys.json` with status `active`.
3. Update the GitHub Actions secret with the new private key.
4. Confirm `python -m win11_release_guard --check-policy-source --policy-url <url>`
   verifies the newly published `.sig`.
5. Keep the previous public key while old signed artifacts or caches may still
   exist; mark it `retiring` or `retired` instead of deleting it immediately.

## Signature Format

New detached signatures are JSON:

```json
{
  "algorithm": "ed25519",
  "key_id": "win11_release_guard-policy-2026-05",
  "signature": "base64-ed25519-signature",
  "signed_at_utc": "2026-05-31T00:00:00+00:00"
}
```

The signature covers the exact bytes of `windows-release-policy.json`. The
signature file itself is not part of the signed payload, so adding metadata such
as `key_id` does not change the policy signature.

The signed bundled policy JSON must use the current `win11_release_guard`
identity and must verify against its detached signature. If the bundled policy
bytes change, replace or regenerate the detached signature in the same change.

Legacy signatures without `key_id` are accepted only through the default trusted
key during the transition.
